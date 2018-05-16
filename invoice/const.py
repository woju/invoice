#
# invoice -- simple invoicing script
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

# pylint: disable=missing-docstring

import pathlib as _pathlib
import posixpath as _posixpath

#: path to a config/state directory in user's home
CONFIGPATH = _pathlib.Path.home() / '.invoice'

#: path to a directory where invoices will be generated
INVOICEPATH = _pathlib.Path.home() / 'Invoices'

_PACKAGEPATH = _pathlib.Path(__file__).parent

_PREFIXEN = [
    CONFIGPATH,
    _pathlib.Path('/usr/local/share/invoice'),
    _pathlib.Path('/usr/share/invoice'),
    _PACKAGEPATH,
]

#: path to jinja2 templates
TEMPLATEPATHS = [prefix / 'templates' for prefix in _PREFIXEN]

#: path to a directory where invoices will be generated
GETTEXTPATH = _PACKAGEPATH / 'locale'

#: options passed to ConTeXt
CONTEXTOPTS = [
    '--batch',
    '--noconsole',
    '--path={}'.format(','.join(str(prefix / 'context')
        for prefix in _PREFIXEN)),
]

#: configuration file
DEFAULT_CONFIG = CONFIGPATH / 'invoice.cfg'

#: state file
DEFAULT_STATE = CONFIGPATH / 'state'

#: the template
USER_TEMPLATE = 'invoice.tex'

#: the template, if not configured
DEFAULT_TEMPLATE = 'invoice-plain.tex'

#: for how long the NBP may pause publishing rate tables
LONGEST_HOLIDAY = 14

#: home currency
HOME_CURRENCY = 'PLN'

# do not touch those
_NBP_URL_BASE = 'https://www.nbp.pl/kursy/xml/'
NBP_URL_INDEX = _posixpath.join(_NBP_URL_BASE, 'dir.aspx?tt=A')
NBP_URL_TABLE = _posixpath.join(_NBP_URL_BASE, '{timestamp}.xml')
NBP_XPATH = ('/tabela_kursow/pozycja/kod_waluty[text() = {currency!r}]/'
    '../kurs_sredni')
