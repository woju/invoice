#!/usr/bin/python3 -O
# pylint: disable=unused-argument,no-self-use,attribute-defined-outside-init

import argparse
import cmd
import datetime
import decimal
import os
import pdb
import shlex
import subprocess

import dateutil.parser
import sqlalchemy.orm.exc

import invoice
import invoice.db

class ArgCmd(cmd.Cmd):
    def parseline(self, line):
        """Parse the line into a command name and a string containing
        the arguments.  Returns a tuple containing (command, args, line).
        'command' and 'args' may be None if the line couldn't be parsed.

        If there is attribute parser_*, args are returned as
        argparse.Namespace as parsed by respective parser.
        """

        line = line.strip()
        if not line:
            return None, None, line
        elif line[0] == '?':
            line = 'help ' + line[1:]
        elif line[0] == '!':
            if hasattr(self, 'do_shell'):
                line = 'shell ' + line[1:]
            else:
                return None, None, line
        i, n = 0, len(line)
        while i < n and line[i] in self.identchars:
            i = i+1
        command, arg = line[:i], line[i:].strip()
        try:
            arg = getattr(self, 'parser_'+command).parse_args(shlex.split(arg))
        except AttributeError:
            pass
        except SystemExit:
            return command, None, line
        return command, arg, line

    def onecmd(self, line):
        """Interpret the argument as though it had been typed in response
        to the prompt.

        This may be overridden, but should not normally need to be;
        see the precmd() and postcmd() methods for useful execution hooks.
        The return value is a flag indicating whether interpretation of
        commands by the interpreter should stop.

        """
        command, arg, line = self.parseline(line)
        if not line:
            return self.emptyline()
        if arg is None:
            return False
        if command is None:
            return self.default(line)
        self.lastcmd = line
        if line == 'EOF':
            self.lastcmd = ''
        if command == '':
            return self.default(line)
        else:
            try:
                func = getattr(self, 'do_' + command)
            except AttributeError:
                return self.default(line)
            return func(arg)

    def do_help(self, arg):
        'Show this help'
        if arg:
            if not hasattr(self, 'do_' + arg):
                self.stdout.write('No such command: {}\n'.format(arg))
                return
            if hasattr(self, 'parser_' + arg):
                self.stdout.write(getattr(self, 'parser_'+arg).format_help())
                return
            if getattr(self, 'do_'+arg).__doc__:
                self.stdout.write(getattr(self, 'do_'+arg).__doc__ + '\n')
                return
            self.stdout.write('No help for {}.\n'.format(arg))
        else:
            self.stdout.write('Available commands:\n')
            for command in sorted(name[3:]
                    for name in self.get_names() if name.startswith('do_')):
                if command == 'EOF':
                    continue
                description = None
                if hasattr(self, 'parser_' + command):
                    description = getattr(self, 'parser_' + command).description
                if not description:
                    description = getattr(self, 'do_' + command).__doc__
                    if description and '\n' in description:
                        description = description[description.find('\n')]
                if description:
                    self.stdout.write(
                        '  {:10s} {}\n'.format(command, description))
                else:
                    self.stdout.write('  {:10s}\n'.format(command))
            self.stdout.write('\nType `help COMMAND` or `COMMAND -h`'
                ' to get help about a particular command.\n\n')

    def do_pdb(self, arg):
        'Break to PDB debugger.'
        pdb.set_trace()

    @staticmethod
    def cmderror(parser, msg):
        try:
            parser.error(msg)
        except SystemExit:
            pass


class CmdProduct(ArgCmd):
    def preloop(self):
        self.prompt = 'product {}> '.format(self.product.code)

    parser_show = argparse.ArgumentParser(prog='show',
        description='Show product summary.')
    def do_show(self, args):
        print(str(self.product))

    parser_name = argparse.ArgumentParser(prog='name',
        description='Change product name.')
    parser_name.add_argument('name', help='New name')
    def do_name(self, args):
        self.product.name = args.name

    parser_unit = argparse.ArgumentParser(prog='unit',
        description='Change unit of measurement.')
    parser_unit.add_argument('unit', help='New unit')
    def do_unit(self, args):
        self.product.unit = args.unit

    parser_price = argparse.ArgumentParser(prog='price',
        description='Change unit price.')
    parser_price.add_argument('currency', help='Currency')
    parser_price.add_argument('price', help='New price')
    def do_price(self, args):
        self.product.set_price(args.currency, args.price)

    parser_bprice = argparse.ArgumentParser(prog='bprice',
        description='Change price to match given brutto unit price.')
    parser_bprice.add_argument('currency', help='Currency')
    parser_bprice.add_argument('bprice', help='New brutto price')
    def do_bprice(self, args):
        self.product.set_bprice(args.currency, args.bprice)

    parser_vat = argparse.ArgumentParser(prog='vat',
        description='Change VAT rate.')
    parser_vat.add_argument('vat', help='New vat')
    def do_vat(self, args):
        self.product.vat = args.vat

    parser_set = argparse.ArgumentParser(prog='set',
        description='Set attribute.')
    parser_set.add_argument('attr', choices=['name', 'unit', 'vat'],
        help='Attribute to change')
    parser_set.add_argument('value', help='New value')
    def do_set(self, args):
        setattr(self.product, args.attr, args.value)

    # TODO def complete_set

    parser_save = argparse.ArgumentParser(prog='save',
        description='Exit to parent menu saving changes.')
    def do_save(self, args):
        invoice.db.session.commit()
        return True

    parser_discard = argparse.ArgumentParser(prog='discard',
        description='Exit to parent menu discarding changes.')
    def do_discard(self, args):
        invoice.db.session.rollback()
        return True

    def do_EOF(self, args):
        self.stdout.write('\nChoose `discard` or `save`; ^D does not work.\n')


class CmdProducts(ArgCmd):
    prompt = 'products> '

    parser_ls = argparse.ArgumentParser(prog='ls',
        description='List all products.')
    def do_ls(self, args):
        self.stdout.write(invoice.env.get_template('products.txt').render(
            products=invoice.db.session.query(invoice.db.Product)))

    parser_show = argparse.ArgumentParser(prog='show',
        description='Show product summary.')
    parser_show.add_argument('code', help='Product code')
    def do_show(self, args):
        self.stdout.write(str(invoice.db.session.query(
            invoice.db.Product).filter_by(code=args.code).one()) + '\n')

    def complete_show(self, text, line, begidx, endidx):
        return sorted(code + ' '
            for code, in invoice.db.session.query(invoice.db.Product.code)
            if code.startswith(text))

    parser_add = argparse.ArgumentParser(prog='add',
        description='Add new product to the database')
    parser_add.add_argument('--unit', '-u', default='szt.',
        help='Unit of measurement [default: %(default)s]')

#   group = parser_add.add_mutually_exclusive_group(required=True)
#   group.add_argument('--price', '-p', type=float,
#       help='Unit price netto')
#   group.add_argument('--bprice', '-P', type=float,
#       help='Unit price brutto')
#   del group

    parser_add.add_argument('--vat', '-v', type=decimal.Decimal, default=23,
        help='VAT factor in %% [default: 23]')
    parser_add.add_argument('code', metavar='CODE',
        help='Product code')
    parser_add.add_argument('name', metavar='NAME',
        help='Product name')

    def do_add(self, args):
        if not args.code:
            self.cmderror(self.parser_add, 'code must not be empty')
            return

        try:
            invoice.db.session.add(invoice.db.Product(code=args.code,
                name=args.name, unit=args.unit, vat=args.vat))
        except Exception as e:
            invoice.db.session.rollback()
            self.stdout.write('{}: {!s}\n'.format(e.__class__.__name__, e))
        else:
            invoice.db.session.commit()

    parser_del = argparse.ArgumentParser(prog='del',
        description='Delete product from database.')
    parser_del.add_argument('code', help='Product code')
    def do_del(self, args):
        'del <code> -- delete product from the database'
        try:
            invoice.db.session.delete(invoice.db.session.query(
                invoice.db.Product).filter_by(code=args.code).one())
        except Exception as e:
            invoice.db.session.rollback()
            self.stdout.write('{}: {!s}\n'.format(e.__class__.__name__, e))
        else:
            invoice.db.session.commit()
    complete_del = complete_show

    parser_open = argparse.ArgumentParser(prog='open',
        description='Open a product for editing.')
    parser_open.add_argument('code', help='Product code')
    def do_open(self, args):
        cli = CmdProduct()
        try:
            cli.product = invoice.db.session.query(
                invoice.db.Product).filter_by(code=args.code).one()
        except sqlalchemy.orm.exc.NoResultFound:
            self.cmderror(self.parser_open,
                'no such product: {!r}\n'.format(args.code))
            return

        try:
            cli.cmdloop()
        except Exception: # as e:
            invoice.db.session.rollback()
            raise
#           self.stdout.write('{}: {!s}\n'.format(e.__class__.__name__, e))
    complete_open = complete_show

    parser_exit = argparse.ArgumentParser(prog='exit',
        description='Return to parent menu.')
    def do_exit(self, args):
        return True

    def do_EOF(self, args):
        self.stdout.write('\n')
        return True


class CmdInvoice(ArgCmd):
    def preloop(self):
        self.prompt = 'invoice {}> '.format(self.invoice.number)

    parser_show = argparse.ArgumentParser(prog='show',
        description='Show current invoice (equivalent to `ls`'
            ' with header and footer)')
    def do_show(self, args):
        self.stdout.write(str(self.invoice) + '\n')

    parser_ls = argparse.ArgumentParser(prog='ls',
        description='List invoice contents (equivalent to `show`'
            ' without header and footer).')
    def do_ls(self, args):
        self.stdout.write(invoice.env.get_template('invoice.txt').render(
            invoice=self.invoice, short=True) + '\n')

    parser_add = argparse.ArgumentParser(prog='add',
        description='Add new line to invoice')

    group = parser_add.add_mutually_exclusive_group()
    group.add_argument('--price', '-p', type=decimal.Decimal,
        help='Unit price netto')
    group.add_argument('--bprice', '-P', type=decimal.Decimal,
        help='Unit price brutto')
    group.add_argument('--netto', '-n', type=decimal.Decimal,
        help='Total price netto')
    group.add_argument('--brutto', '-b', type=decimal.Decimal,
        help='Total price brutto')
    del group

    parser_add.add_argument('--vat', '-v', type=decimal.Decimal,
        help='VAT factor')
    parser_add.add_argument('product', metavar='PRODUCT',
        help='Product code')
    parser_add.add_argument('amount', metavar='AMOUNT', type=decimal.Decimal,
        help='Amount (in respective units)')

    def do_add(self, args):
        if not args.product:
            self.cmderror(self.parser_add, 'product must not be empty')
            return

        if not args.amount:
            self.cmderror(self.parser_add, 'amount must not be empty')
            return

        self.invoice.add_line(args.product, args.amount,
            price=args.price, bprice=args.bprice, netto=args.netto,
            brutto=args.brutto, vat=args.vat)

    parser_del = argparse.ArgumentParser(prog='del',
        description='Delete invoice line.')
    parser_del.add_argument('line', metavar='LINE', type=int,
        help='Line number.')
    def do_del(self, args):
        del self.invoice.lines[args.line - 1]

    def do_modify(self, args):
        pass

    parser_set = argparse.ArgumentParser(prog='set',
        description='Set attribute.')
    parser_set.add_argument('attr', choices=[
            'currency',
            'customer',
            'deadline',
            'delivered',
            'grace',
            'issued',
            ],
        help='Attribute to change')
    parser_set.add_argument('value', help='New value')
    def do_set(self, args):
        attr = args.attr
        if attr in ('currency', 'customer'):
            attr = attr + '_code'

        value = args.value
        if attr in ('delivered', 'issued'):
            value = dateutil.parser.parse(value)

        if attr == 'grace':
            value = int(value)
        setattr(self.invoice, attr, value)

    # TODO def complete_set

    parser_finalise = argparse.ArgumentParser(prog='finalise',
        description='Finalise invoice.')
    def do_finalise(self, args):
        self.invoice.finalise()
        return self.do_save(args)

    parser_finalize = parser_finalise
    do_finalize = do_finalise

    parser_products = argparse.ArgumentParser(prog='products',
        description='List products.')
    def do_products(self, args):
        self.stdout.write(invoice.env.get_template('products.txt').render(
            products=invoice.db.session.query(invoice.db.Product)))

    parser_save = argparse.ArgumentParser(prog='save',
        description='Exit to parent menu saving changes.')
    def do_save(self, args):
        invoice.db.session.commit()
        return True

    parser_discard = argparse.ArgumentParser(prog='discard',
        description='Exit to parent menu discarding changes.')
    def do_discard(self, args):
        invoice.db.session.rollback()
        return True

    def do_EOF(self, args):
        self.stdout.write(
            '\nChoose `discard`, `save` or `finalise`; ^D does not work.\n')

#   def do_debug(self, args):
#       pprint.pprint(self.invoice)
#       pprint.pprint(list(self.invoice))


class CmdInvoices(ArgCmd):
    intro = '''invoice {}  Copyright (C) 2014-2015  Wojtek Porczyk

  This program comes with no warranty. This is free software,
  and you are welcome to redistribute it under certain conditions.
  See GPL-3 for details.
'''.format(invoice.__version__)
    prompt = 'invoice> '

    parser_ls = argparse.ArgumentParser(prog='ls',
        description='List invoices.')
    def do_ls(self, args):
        self.stdout.write(invoice.env.get_template('invoices.txt').render(
            invoices=invoice.db.session.query(invoice.db.Invoice)) + '\n')

    parser_products = argparse.ArgumentParser(prog='products',
        description='Edit products.')
    def do_products(self, args):
        'products -- edit products database'
        CmdProducts().cmdloop()

    parser_show = argparse.ArgumentParser(prog='show',
        description='Show invoice.')
    parser_show.add_argument('number', metavar='NUMBER',
        help='Invoice number.')
    def do_show(self, args):
        self.stdout.write(str(invoice.db.session.query(
            invoice.db.Invoice).filter_by(number=args.number).one()) + '\n')

    def complete_show(self, text, line, begidx, endidx):
        return sorted(number + ' '
            for number, in invoice.db.session.query(invoice.db.Invoice.number)
            if number.startswith(text))

    parser_open = argparse.ArgumentParser(prog='open',
        description='Open invoice for editing.')
    parser_open.add_argument('number', metavar='NUMBER',
        help='Invoice number.')
    def do_open(self, args):
        inv = invoice.db.session.query(
            invoice.db.Invoice).filter_by(number=args.number).one()
        if inv.finalised:
            self.stdout.write(
                'Invoice {0} is finalised. Editing is not possible.\n'
                'Try `show {0}` or `tex {0}`.\n\n'.format(inv.number))
            return
        cli = CmdInvoice()
        cli.invoice = inv
        cli.cmdloop()
    complete_open = complete_show

    parser_unfinalise = argparse.ArgumentParser(prog='unfinalise',
        description='Unfinalise invoice.')
    parser_unfinalise.add_argument('number', metavar='NUMBER',
        help='Invoice number.')
    def do_unfinalise(self, args):
        inv = invoice.db.session.query(
            invoice.db.Invoice).filter_by(number=args.number).one()
        inv.unfinalise()
        invoice.db.session.commit()
    complete_unfinalise = complete_show

    parser_new = argparse.ArgumentParser(prog='new',
        description='Create new invoice')
    parser_new.add_argument('--delivered', '-d', metavar='YYYY-MM-DD',
        dest='delivered',
        type=dateutil.parser.parse, default=datetime.date.today(),
        help='Date of delivery')
    parser_new.add_argument('--issued', '-i', metavar='YYYY-MM-DD',
        dest='issued',
        type=dateutil.parser.parse, default=datetime.date.today(),
        help='Date of issue')
    parser_new.add_argument('--customer', '-c', default='ALX',
        help='Customer identificator')
    parser_new.add_argument('number', metavar='NUMBER',
        help='Number of the invoice')
    parser_new.add_argument('currency', metavar='CURRENCY',
        help='Currency of the invoice')
    parser_new.add_argument('spec', metavar='SPEC', nargs='*', default=[],
        help='Line specification in format'
            ' <code>,<amount>[,{price|bprice|netto|brutto}=<x>][,vat=<x>]')

    def do_new(self, args):
        inv = invoice.db.Invoice(
            number=args.number,
            currency_code=args.currency,
            customer_code=args.customer,
            delivered=args.delivered,
            issued=args.issued)
        for spec in args.spec:
            inv.add_line_from_spec(spec)

        invoice.db.session.add(inv)
        invoice.db.session.flush()

        cli = CmdInvoice()
        cli.invoice = inv
        cli.cmdloop()

    parser_del = argparse.ArgumentParser(prog='del',
        description='Delete an invoice from the database.')
    parser_del.add_argument('number', metavar='NUMBER',
        help='Invoice number.')
    def do_del(self, args):
        'del <code> -- delete invoice from the database'
        invoice.db.session.delete(invoice.db.session.query(
            invoice.db.Invoice).filter_by(number=args.number).one())
        invoice.db.session.commit()
    complete_del = complete_show

    parser_pdf = argparse.ArgumentParser(prog='pdf',
        description='Create PDF using ConTeXt.')
    parser_pdf.add_argument('number', metavar='NUMBER',
        help='Invoice number.')
    parser_pdf.add_argument('locale', metavar='LOCALE',
        nargs='?', choices=('pl_PL', 'en_GB'),
        help='Invoice language.')
    def do_pdf(self, args):
        inv = invoice.db.session.query(
            invoice.db.Invoice).filter_by(number=args.number).one()
        texfile = invoice.config.get_invoice_file(inv.number, '.tex')

        open(texfile, 'w').write(inv.tex(args.locale))
        result = subprocess.call(
            ['context', '--batch', '--noconsole', texfile],
            cwd=invoice.config.invoicespath)

        try:
            os.unlink(invoice.config.get_invoice_file(inv.number, '.tuc'))
        except:
            pass
        try:
            os.unlink(invoice.config.get_invoice_file(inv.number, '.log'))
        except:
            pass

        if result:
            self.stdout.write('Creating PDF failed.\n\n')
            return False

    complete_pdf = complete_show

    parser_display = argparse.ArgumentParser(prog='tex',
        description='Display PDF.')
    parser_display.add_argument('number', metavar='NUMBER',
        help='Invoice number.')
    def do_display(self, args):
        if self.do_pdf(args) is False:
            return
        inv = invoice.db.session.query(
            invoice.db.Invoice).filter_by(number=args.number).one()
        pdffile = invoice.config.get_invoice_file(inv.number, '.pdf')
        subprocess.call(['evince', pdffile])
    complete_display = complete_show

#   parser_sign = argparse.ArgumentParser(prog='sign',
#       description='Create signed invoice.')
#   parser_sign.add_argument('number', metavar='NUMBER',
#       help='Invoice number.')
#   def do_sign(self, args):
#       invoice = Invoice(args.number).load(_db).load_lines(_db)
#       try:
#           asc = str(gnupg.GPG().sign(str(invoice) + '\n', clearsign=True))
#       except:
#           self.stdout.write('Signing failed.\n\n')
#           return

#       filename = config.get_invoice_file(invoice.number, '.asc')
#       open(filename, 'w').write(asc)
#       self.stdout.write(asc + '\n')
#   complete_sign = complete_show

    parser_customers = argparse.ArgumentParser(prog='customers',
        description='List customers.')
    def do_customers(self, args):
        self.stdout.write(invoice.env.get_template('customers.txt').render(
            customers=invoice.db.session.query(invoice.db.Customer)))

    parser_mail = argparse.ArgumentParser(prog='mail',
        description='Mail PDF with invoice to the contact e-mail address.')
    parser_mail.add_argument('number', metavar='NUMBER',
        help='Invoice number.')
    def do_mail(self, args):
        # TODO integrate with customers from LDAP
        # TODO qubes-rpc
        if self.do_pdf(args) is False:
            return
        inv = invoice.db.session.query(
            invoice.db.Invoice).filter_by(number=args.number).one()
        pdffile = invoice.config.get_invoice_file(inv.number, '.pdf')
        subprocess.call(['mutt',
            '-s', 'Faktura VAT ' + inv.number,
            '-a', pdffile,
            '--', inv.customer.mail])
    complete_mail = complete_show

    parser_init = argparse.ArgumentParser(prog='init',
        description='Initialise database.')
    def do_init(self, args):
#       with open(os.path.expanduser(config.dbfilename), 'ab'):
#           pass
        invoice.db.init()

    parser_exit = argparse.ArgumentParser(prog='exit',
        description='Exit from invoice shell.')
    def do_exit(self, args):
        return True

    def do_EOF(self, args):
        self.stdout.write('\n')
        return True

#   def do_debug(self, args):
#       pprint.pprint(Invoices(_db, index=True))


def main():
    import readline
    readline.set_completer_delims(
        ''.join(c for c in readline.get_completer_delims() if c not in '-/'))
    CmdInvoices().cmdloop()

if __name__ == '__main__':
    main()

# vim: ts=4 sts=4 sw=4 et
