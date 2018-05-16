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

'''Rendering facilities, jinja etc.'''

import gettext as _gettext

import jinja2 as _jinja2
import babel.numbers as _bnumbers

from . import const as _const


def filter_escapetex(value):
    '''Filter for jinja2: escape tex characters.

    This is at best incomplete.
    '''
    return str(value).replace('$', '\\$')

def filter_texdate(value):
    '''Filter for jinja2: replace leading space with white zero'''
    value = value.strftime('%e.%m.%Y')
    return r'\color[white]{0}' + value[1:] if value.startswith(' ') else value

def assertfunc(value):
    '''Global for jinja2: assert'''
    assert value

def get_jinja2_environment(lang):
    '''Get configured jinja2 environment'''

    env = _jinja2.Environment(
        extensions=['jinja2.ext.i18n'],
        loader=_jinja2.FileSystemLoader(list(map(str, _const.TEMPLATEPATHS))))

    env.filters['escapetex'] = filter_escapetex
    env.filters['texdate'] = filter_texdate
    env.globals['float'] = float
    env.globals['home_currency'] = _const.HOME_CURRENCY
    env.globals['assert'] = assertfunc

    env.filters['format_currency'] = _bnumbers.format_currency
    env.filters['format_decimal'] = _bnumbers.format_decimal
    env.globals['get_currency_symbol'] = _bnumbers.get_currency_symbol

    env.install_gettext_translations(_gettext.translation(
            'invoice', str(_const.GETTEXTPATH),
            languages=[lang], fallback=True),
        newstyle=True)

    return env
