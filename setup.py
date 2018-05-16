#!/usr/bin/env python3

import pathlib
import setuptools

from babel.messages import frontend as babel

from invoice import __version__

setuptools.setup(
    name='invoice',
    version=__version__,
    author='Wojtek Porczyk',
    author_email='woju@invisiblethingslab.com',
    description='Invoice generator',
    license='GPL3+',
    url='https://github.com/woju/invoice',
    packages=setuptools.find_packages(),
    package_data={
        'invoice': ['templates/*', 'locale/*/*/*.mo'],
    },
    data_files=[
        ('share/doc/invoice', ['README.markdown']),
        ('share/doc/invoice/examples', [str(path)
            for path in pathlib.Path('Documentation/examples').glob('*')]),
    ],
    entry_points={'console_scripts': ['invoice = invoice.__main__:main']},
    cmdclass={
        'compile_catalog': babel.compile_catalog,
        'extract_messages': babel.extract_messages,
        'init_catalog': babel.init_catalog,
        'update_catalog': babel.update_catalog,
    },

    message_extractors={
        'invoice': [
            ('**.py', 'python', None),
            ('templates/**.tex', 'jinja2', {'silent': 'false'}),
        ],
        'Documentation/examples': [
            ('**.tex', 'jinja2', {'silent': 'false'}),
        ],
    },
)

# vim: tw=80 ts=4 sts=4 sw=4 et
