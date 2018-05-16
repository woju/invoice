#
# invoice -- simpler invoicing script
# Copyright (C) 2015-2018 Wojtek Porczyk <woju@invisiblethingslab.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

'''Model for invoice, parser exploitation etc.'''

import configparser as _configparser
import datetime as _datetime
import decimal as _decimal
import fcntl as _fcntl
import json as _json
import logging as _logging
import math as _math
import re as _re
import urllib.request as _urllib_request

import lxml.etree as _lxml_etree

from . import const as _const

_log = _logging.getLogger()

def date_t(date):
    '''Parses dates from draft for configparser'''
    if date == 'today':
        return _datetime.date.today()
    if date == 'last-month':
        return _datetime.date.today().replace(day=1)-_datetime.timedelta(days=1)
    return _datetime.datetime.strptime(date, '%Y-%m-%d').date()

_re_maybe_comma = _re.compile(r'[, ]+')
def set_t(value):
    '''Parses a comma separated set for configparser'''
    return set(_re_maybe_comma.split(value))


def get_configparser():
    '''Initialise a ConfigParser'''
    return _configparser.ConfigParser(
        comment_prefixes='#;',
        inline_comment_prefixes='#',
        default_section=None,
        interpolation=_configparser.ExtendedInterpolation(),
        converters={
            'decimal': _decimal.Decimal,
            'path': _const.CONFIGPATH.__truediv__,
            'date': date_t,
            'set': set_t,
        })


class Customer:
    '''A customer from config'''
    # pylint: disable=too-few-public-methods
    section = 'customer'
    def __init__(self, config):
        self.config = config

        self.address = None
        self.email = None
        self.pgpkey = None

        if self.config.has_option(self.section, 'customer'):
            self.load_section(
                'customer.' + self.config.get(self.section, 'customer'))
        self.load_section(self.section)

        assert self.address is not None

    def load_section(self, section):
        '''Load the customer from config'''
        self.address = self.config.get(section, 'address',
            fallback=self.address)
        self.email = self.config.get(section, 'email',
            fallback=self.email)
        self.pgpkey = self.config.get(section, 'pgpkey',
            fallback=self.pgpkey)


class Line:
    '''One line on the invoice'''
    # pylint: disable=too-many-instance-attributes
    _PRICEOPTS = {'price', 'bprice', 'netto', 'brutto'}

    def __init__(self, config, section, currency):
        _log.debug('%s(config=..., section=%r, currency=%r)',
            type(self).__name__, section, currency)
        self.config = config
        self.section = section

        self.name = None
        self.amount = None
        self.unit = None
        self.vat = None
        self.price = None

        if self.config.has_option(self.section, 'product'):
            self.load_section(
                'product.' + self.config.get(self.section, 'product'),
                currency)
        self.load_section(self.section, currency)

        assert self.name is not None
        assert self.amount is not None
        assert self.unit is not None
        assert self.vat is not None
        assert self.price is not None

    def load_section(self, section, currency):
        '''Load the invoice from config'''
        currency = currency.lower()
        _log.debug('%s.load_section(section=%r, currency=%r) options=%r',
            type(self).__name__, section, currency,
            self.config.options(section))
        self.name = self.config.get(section, 'name',
            fallback=self.name)
        self.amount = self.config.getdecimal(section, 'amount',
            fallback=self.amount)
        self.vat = self.config.getdecimal(section, 'vat',
            fallback=self.vat)

        if self.config.has_option(section, 'unit'):
            (self.unit, self.unit_plural, *_
                ) = self.config.get(section, 'unit').split('|') * 2

        priceopts = {
            '.'.join((opt, currency)) for opt in self._PRICEOPTS}.intersection(
            self.config.options(section))

        _log.debug('priceopts=%r', priceopts)
        if priceopts:
            (priceopt,) = priceopts  # there should be exactly one
            priceattr = priceopt.split('.', 1)[0]
            setattr(self, priceattr, self.config.getdecimal(section, priceopt))

    def set_bprice(self, bprice):
        '''Set price from unit price brutto.'''
        self.price = _decimal.Decimal(_math.floor(
            bprice / (self.vat / 100 + 1) * 100) / 100)

    def set_netto(self, netto):
        '''Set price from line total netto.'''
        self.price = _decimal.Decimal(
            _math.floor(netto / self.amount * 100) / 100)

    def set_brutto(self, brutto):
        '''Set price from line total brutto.'''
        self.price = _decimal.Decimal(_math.floor(
            brutto / (self.vat / 100 + 1) / self.amount * 100) / 100)

    bprice = property(
        lambda self: (self.vat * _decimal.Decimal('.01') + 1) * self.price,
        set_bprice)
    netto = property(
        lambda self: self.price * self.amount,
        set_netto)
    tax = property(
        lambda self: self.vat * _decimal.Decimal('.01') * self.netto)
    brutto = property(
        lambda self: self.netto + self.tax,
        set_brutto)


class Invoice:
    '''Represents whole invoice'''
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-few-public-methods
    section = 'invoice'

    class Features:
        '''Features in the invoice.'''
        def __init__(self, features):
            self._features = {self._normalize(i) for i in features}
        def __getattr__(self, key):
            return self._normalize(key) in self._features
        @staticmethod
        def _normalize(value):
            return value.lower().replace('_', '-')

    @staticmethod
    def _sort_key_line(line):
        return tuple(int(s) if s.isdigit() else s for s in line.split('.'))

    def __init__(self, config, number_state):
        self.config = config

        self.lang = config.get(self.section, 'lang')
        self.currency = config.get(self.section, 'currency')
        self.issued = config.getdate(self.section, 'issued')
        self.delivered = config.getdate(self.section, 'delivered')
        self.grace = config.getint(self.section, 'grace')
        self.prefix = config.get(self.section, 'prefix')

        self.features = self.Features(
            config.getset(self.section, 'features', fallback=set()))
        self.customer = Customer(config)
        self.lines = []

        try:
            self.number = config.get(self.section, 'number')
            number_state.register_number(self.number)
        except _configparser.NoOptionError:
            self.number = number_state.get_number(self.issued)

        for section in sorted(
                (s for s in config.sections() if s.startswith('line.')),
                key=self._sort_key_line):
            self.lines.append(Line(config, section, currency=self.currency))

        self.currency_rate = None
        self.currency_rate_date = None

        if self.is_foreign_currency:
            self._get_currency_rate()

    def _get_currency_rate(self):
        '''Get exchange rate for this invoice'''
        index = _urllib_request.urlopen(
            _const.NBP_URL_INDEX).read().decode('iso-8859-2')
        match = None
        for i in range(1, _const.LONGEST_HOLIDAY + 1):
            date = self.issued - _datetime.timedelta(days=i)
            match = _re.search(date.strftime(r'a\d{3}z%y%m%d'), index)
            if match:
                break
        if not match:
            raise ValueError('no currency rate available')

        xml = _lxml_etree.parse(_urllib_request.urlopen(
            _const.NBP_URL_TABLE.format(timestamp=match.group(0))))
        result = xml.xpath(_const.NBP_XPATH.format(currency=self.currency))
        if len(result) != 1:
            raise TypeError(
                'no such currency or result problem: {!r}, result: {!r}'.format(
                    self.currency, result))

        self.currency_rate = _decimal.Decimal(result[0].text.replace(',', '.'))
        self.currency_rate_date = date

    netto = property(lambda self: sum(line.netto for line in self.lines))
    brutto = property(lambda self: sum(line.brutto for line in self.lines))
    tax = property(lambda self: sum(line.tax for line in self.lines))
    tax_pln = property(lambda self:
        self.tax * self.currency_rate if self.is_foreign_currency else self.tax)

    is_foreign_currency = property(lambda self:
        self.currency.lower() != _const.HOME_CURRENCY.lower())

    deadline = property(lambda self:
        self.issued + _datetime.timedelta(days=self.grace))
    stem = property(lambda self:
        '{}_{}'.format(self.prefix, self.number.replace('/', '_')))


class State(dict):
    '''A persistent state. Remembers previous invoice number.'''
    def __init__(self, path=_const.DEFAULT_STATE):
        super().__init__()
        try:
            self._fd = open(str(path), 'r+')
            _fcntl.flock(self._fd, _fcntl.LOCK_EX)
        except FileNotFoundError:
            self._fd = open(str(path), 'x+')
            _fcntl.flock(self._fd, _fcntl.LOCK_EX)
            self.save()
        else:
            self.update(_json.load(self._fd, object_hook=self._normalize_keys))

    def save(self):
        '''Save the state'''
        self._fd.seek(0)
        _json.dump(self, self._fd)

    def __missing__(self, key):
        return 0

    @staticmethod
    def _normalize_keys(obj):
        for key, value in obj.items():
            yield int(key), value

    def register_number(self, number):
        '''Advise that the number is used.

        If it is consecutive, increment state. If not consecutive, do nothing.
        User should call .save() after successful generation.
        '''
        year, yno = map(int, number.split('/'))
        if yno == self[year] + 1:
            self[year] += 1
            return

        _log.warning('warning: non-consecutive number %s', number)

    def get_number(self, year):
        '''Get next invoice number.

        After calling this function and successful generation, call .save()
        '''
        if isinstance(year, _datetime.date):
            year = year.year
        self[year] += 1
        return '{}/{:02d}'.format(year, self[year])
