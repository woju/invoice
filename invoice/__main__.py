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

import argparse
import configparser
import io
import logging
import os
import pathlib
import subprocess
import sys

from . import const
from . import model
from . import render

argparser = argparse.ArgumentParser()  # pylint: disable=invalid-name

argparser.add_argument('--config', '-f', metavar='PATH',
    action='append',
    type=pathlib.Path,
    help='load alternative config (default: {!s})'.format(const.DEFAULT_CONFIG))

argparser.add_argument('--option', '-o', metavar='SECTION/OPTION=VALUE',
    action='append',
    help='directly set an option (unsafe)')

argparser.add_argument('--output', '-O', metavar='PATH',
    type=pathlib.Path,
    help='directory to create output file (default: %(default)s)')

argparser.add_argument('--template', '-t', metavar='TEMPLATE',
    help='use alternative template')

argparser.add_argument('--verbose', '-v',
    dest='loglevel',
    action='append_const', const=-10,
    help='increase verbosity')

argparser.add_argument('--quiet', '-q',
    dest='loglevel',
    action='append_const', const=+10,
    help='decrease verbosity')

argparser.add_argument('file', metavar='DRAFTPATH',
    nargs='?',
    type=argparse.FileType('r'),
    help='draft file path (default: stdin)')

argparser.set_defaults(
    option=[],
    output=const.INVOICEPATH,
    loglevel=[logging.WARNING],
    file=sys.stdin,
)

def main(args=None):
    args = argparser.parse_args(args)
    logging.basicConfig(format='%(message)s', level=sum(args.loglevel))
    if not args.config:
        args.config = [const.DEFAULT_CONFIG]

    config = model.get_configparser()

    for path in args.config:
        with path.open() as file:
            config.read_file(file)

    config.read_file(args.file)
    state = model.State()

    for option in args.option:
        option, value = option.split('=', 1)
        section, option = option.split('/', 1)

        try:
            config.add_section(section)
        except configparser.DuplicateSectionError:
            pass

        config.set(section, option, value)

    invoice = model.Invoice(config, state)

    templates = [const.USER_TEMPLATE, const.DEFAULT_TEMPLATE]
    if args.template is not None:
        templates.insert(0, args.template)

    env = render.get_jinja2_environment(invoice.lang)
    template = env.select_template(templates)
    # pylint: disable=no-member
    filepath = (args.output / invoice.stem
        ).with_suffix(os.path.splitext(template.name)[1])
    texdata = template.render(invoice=invoice, args=args, config=config)
    # pylint: enable=no-member

    logging.info('writing %s', filepath)
    with open(str(filepath), 'x') as file:
        file.write(texdata)

    logging.info('compiling')
    try:
        subprocess.check_call(
            ['context', *const.CONTEXTOPTS, filepath.name],
            cwd=str(filepath.parent))

    except subprocess.CalledProcessError:
        logging.exception('context failed')
        return 1

    else:
        state.save()

    finally:
        for suffix in ('.tuc', '.log'):
            try:
                filepath.with_suffix(suffix).unlink()
            except OSError:
                pass


if __name__ == '__main__':
    sys.exit(main())
