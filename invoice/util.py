#!/usr/bin/python3 -O

import calendar
import datetime
import decimal
import re
import urllib.request

import lxml.etree

#: for how long the NBP may pause publishing rate tables
LONGEST_HOLIDAY = 14


def last_day_of_month(now=None):
    if now is None:
        now = datetime.date.today()
    return datetime.date(
        now.year, now.month, calendar.monthrange(now.year, now.month)[1])

def get_currency_rate(currency, date):
    index = urllib.request.urlopen('https://www.nbp.pl/kursy/xml/dir.txt'
        ).read().decode('iso-8859-2')
    m = None
    for i in range(LONGEST_HOLIDAY): # pylint: disable=unused-variable
        # kolejność jest dobra, bo bierzemy z wczoraj, albo wcześniej
        date = date - datetime.timedelta(days=1)
        m = re.search(date.strftime(r'a\d{3}z%y%m%d'), index)
        if m:
            break
    if not m:
        raise ValueError('no rate available')

    uri = 'https://www.nbp.pl/kursy/xml/{}.xml'.format(m.group(0))
    xpath = '/tabela_kursow/pozycja/kod_waluty[text() = {!r}]' \
        '/../kurs_sredni'.format(currency)
    xml = lxml.etree.parse(urllib.request.urlopen(uri))
    result = xml.xpath(xpath)
    if len(result) != 1:
        raise TypeError(
            'no such currency or result problem: {!r}, result: {!r}'.format(
                currency, result))
    return decimal.Decimal(result[0].text.replace(',', '.')), date


