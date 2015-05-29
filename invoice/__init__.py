#!/usr/bin/python3 -O

# invoice.py -- simple invoice database
# Copyright (C) 2014-2015  Wojtek Porczyk <wojciech@porczyk.eu>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

__version__ = '1.0-alpha'

import argparse
import calendar
import cmd
import datetime
import decimal
import io
import math
import os
import pdb
import pprint
import re
import shlex
import subprocess
import sys
import urllib.request

import babel.numbers

import dateutil.parser
#import gnupg
import jinja2
import lxml.etree


COLOURS = {
    'bold':     '1',
    'black':    '30',
    'red':      '31',
    'green':    '32',
    'yellow':   '33',
    'blue':     '34',
    'magenta':  '35',
    'cyan':     '36',
    'white':    '37',
    'bblack':   '1;30',
    'bred':     '1;31',
    'bgreen':   '1;32',
    'byellow':  '1;33',
    'bblue':    '1;34',
    'bmagenta': '1;35',
    'bcyan':    '1;36',
    'bwhite':   '1;37',
}



class Config:
    def __init__(self, configpath=None, invoicespath=None):
        self.configpath = configpath or os.path.expanduser('~/.invoice')
        self.invoicespath = invoicespath or os.path.expanduser('~/Invoices')

    dbfilename = property(
        lambda self: os.path.join(self.configpath, 'test.sqlite3'))

    def get_data(self, key, default=False):
        if not isinstance(key, str):
            key = os.path.join(*key)

        try:
            return open(os.path.join(self.configpath, key)).read()
        except:
            if default is False:
                raise KeyError('No such data: {!r}'.format(key))
            else:
                return default

    def get_invoice_file(self, number, ext):
        number = tuple(reversed(number.split('/')))
        filename = 'WZJP_{}.{}'.format('_'.join(number), ext.lstrip('.'))
        return os.path.join(self.invoicespath, filename)

config = Config()

env = jinja2.Environment(
    extensions=['jinja2.ext.i18n'],
    loader=jinja2.FileSystemLoader(
        os.path.join(os.path.dirname(__file__), '..', 'templates'))
)
env.filters['colour'] = lambda value, colour: \
    '\x1b[{}m{}\x1b[0m'.format(COLOURS.get(colour, colour), value)

def filter_texdate(value):
    value = value.strftime('%e.%m.%Y')
    return r'\color[white]{0}' + value[1:] if value.startswith(' ') else value

env.filters['texdate'] = filter_texdate

env.filters['escapetex'] = lambda value: str(value) \
    .replace('$', '\\$') \
    .replace('\xa0', '~') \

def format_currency(value, currency):
    tokens = babel.numbers.format_currency(value, currency, locale='pl_PL').split('\xa0')
    return '{}\xa0{}'.format(''.join(tokens[:-1]), tokens[-1])
env.filters['format_currency'] = format_currency
del format_currency
    

env.globals['address'] = config.get_data('address')
env.globals['float'] = float


# vim: ts=4 sts=4 sw=4 et
