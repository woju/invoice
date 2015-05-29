#!/usr/bin/python3 -O
# pylint: disable=no-init,too-few-public-methods

import datetime
import decimal
import gettext
import math
import os

import sqlalchemy
import sqlalchemy.ext.declarative
import sqlalchemy.orm
import sqlalchemy.orm.collections
import sqlalchemy.orm.exc
import sqlalchemy.types

from sqlalchemy import Table
from sqlalchemy import Column

from sqlalchemy import Boolean
from sqlalchemy import CHAR
from sqlalchemy import Date
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import Unicode

from sqlalchemy import ForeignKey

Base = sqlalchemy.ext.declarative.declarative_base()

import invoice
import invoice.util

class Currency(Base):
    __tablename__ = 'currencies'
    code = Column(CHAR(3), primary_key=True)
    sign = Column(Unicode(8), nullable=False)
    name = Column(Text(), nullable=False)


features_association = Table('invoice_features', Base.metadata,
    Column('invoice_no', ForeignKey('invoices.number')),
    Column('feature_code', ForeignKey('features.code'))
)


class Feature(Base):
    __tablename__ = 'features'
    code = Column(String(8), primary_key=True)
    description = Column(Text())


class Product(Base):
    __tablename__ = 'products'
    code = Column(String(8), primary_key=True)
    name = Column(String(64), nullable=False)
    unit = Column(String(8))
    vat = Column(Numeric(2), default=23, nullable=False)

    prices = sqlalchemy.orm.relationship('Price', cascade='all, delete-orphan',
        collection_class=sqlalchemy.orm.collections.attribute_mapped_collection(
            'currency_code'))

    def set_price(self, currency, price):
        price = decimal.Decimal(price)
        try:
            self.prices[currency].price = price
        except KeyError:
            session.add(Price(
                product_code=self.code, currency_code=currency, price=price))
        session.flush()

    def set_bprice(self, currency, bprice):
        bprice = decimal.Decimal(bprice)
        try:
            self.prices[currency].bprice = bprice
        except KeyError:
            price = Price(product_code=self.code, currency_code=currency)
            price.bprice = bprice
            session.add(price)
        session.flush()


    def __repr__(self):
        return ('<{0.__class__.__name__} {0.code!r} name={0.name!r}'
            ' unit={0.unit!r} vat={0.vat!r}>').format(self)

    def __str__(self):
        return invoice.env.get_template('product.txt').render(product=self)


class Price(Base):
    __tablename__ = 'prices'
    product_code = Column(ForeignKey('products.code',
        onupdate='CASCADE', ondelete='CASCADE'), primary_key=True)
    currency_code = Column(ForeignKey('currencies.code',
        onupdate='CASCADE', ondelete='RESTRICT'), primary_key=True)
    price = Column(Numeric(4),
        nullable=False)

    product = sqlalchemy.orm.relationship('Product')
    currency = sqlalchemy.orm.relationship('Currency')

    def set_bprice(self, bprice):
        # pylint: disable=no-member
        self.price = math.floor(
            decimal.Decimal(bprice) / (self.product.vat / 100 + 1) * 100) \
            / 100
        session.flush()

    bprice = property(lambda self: (
            (self.product.vat * decimal.Decimal('.01') + 1) * self.price),
        set_bprice)


class Customer(Base):
    __tablename__ = 'customers'
    code = Column(String(16), primary_key=True)
    short = Column(String(64), nullable=False)
    address = Column(String(256), nullable=False)
    email = Column(String(128), nullable=False)


class Invoice(Base):
    __tablename__ = 'invoices'

    number = Column(String(16), primary_key=True)

    currency_code = Column(ForeignKey('currencies.code',
        onupdate='CASCADE', ondelete='RESTRICT'), nullable=False)
    customer_code = Column(ForeignKey('customers.code',
        onupdate='CASCADE', ondelete='RESTRICT'), nullable=False)
    delivered = Column(Date(),
        default=invoice.util.last_day_of_month, nullable=False)
    issued = Column(Date(),
        default=invoice.util.last_day_of_month, nullable=False)
    grace = Column(Integer(),
        default=15, nullable=False)
    finalised = Column(Boolean(),
        default=False, nullable=False)

    currency = sqlalchemy.orm.relationship('Currency')
    customer = sqlalchemy.orm.relationship('Customer')
    lines = sqlalchemy.orm.relationship('Line',
        cascade='all, delete-orphan')
    features = sqlalchemy.orm.relationship('Feature',
        secondary=features_association)

    deadline = property(lambda self:
        (self.issued + datetime.timedelta(days=self.grace)))


    netto = property(lambda self: sum(line.netto for line in self.lines))
    tax = property(lambda self: sum(line.tax for line in self.lines))
    brutto = property(lambda self: sum(line.brutto for line in self.lines))

    def _get_currency_rate(self):
        if hasattr(self, '_currency_rate'):
            return
        self._currency_rate, self._currency_rate_date = \
            invoice.util.get_currency_rate(self.currency_code, self.delivered)

    @property
    def currency_rate(self):
        self._get_currency_rate()
        return self._currency_rate

    @property
    def currency_rate_date(self):
        self._get_currency_rate()
        return self._currency_rate_date

    @property
    def tax_pln(self):
        if self.currency_code == 'PLN':
            return self.tax
        return self.tax * self.currency_rate

    def add_line(self, product, amount, **kwargs):
        if not isinstance(product, Product):
            product = session.query(Product).filter_by(code=product).one()

        line = Line(invoice_no=self.number,
            product_code=product.code,
            amount=decimal.Decimal(amount),
            price=product.prices[self.currency_code].price,
            currency=self.currency,
            vat=product.vat)

        for k, v in kwargs.items():
            if v is None:
                continue
            setattr(line, k, v)

        self.lines.append(line) # pylint: disable=no-member
        session.flush()

    def add_line_from_spec(self, spec):
        tokens = spec.strip().split(',')
        product = tokens[0]
        amount = decimal.Decimal(tokens[1])

        kwargs = dict()
        for token in tokens[2:]:
            k, v = token.split('=', 1)
            kwargs[k] = decimal.Decimal(v)

        self.add_line(product, amount, **kwargs)

    def finalise(self):
        self.finalised = True

    def unfinalise(self):
        self.finalised = False

    # TODO
    def set_deadline(self, deadline):
        pass

    def tex(self, locale=None):
        if locale is None:
            locale = 'pl_PL'
        trans = gettext.translation('invoice', 'locale', languages=[locale], fallback=True)

        # pylint: disable=no-member
        invoice.env.install_gettext_translations(trans, newstyle=True)
        ret = invoice.env.get_template('invoice.tex').render(invoice=self)
        invoice.env.uninstall_gettext_translations(trans)
        return ret

    def __str__(self):
        return invoice.env.get_template('invoice.txt').render(invoice=self)

    def __repr__(self):
        return ('<{0.__class__.__name__} {0.number!r}'
            ' customer_code={0.customer_code!r}'
            ' delivered={0.delivered!r}'
            ' issued={0.issued!r}'
            ' grace={0.grace!r}'
            ' count={1!r}'
            ' netto={0.netto!r}'
            ' tax={0.tax!r}'
            ' brutto={0.brutto!r}'
            ' finalised={0.finalised!r}>').format(self, len(self.lines))


class Line(Base):
    # PRIMARY KEY is sort of stupid, it is there because sqlalchemy requires it
    __tablename__ = 'lines'
    invoice_no = Column(ForeignKey('invoices.number',
        onupdate='CASCADE', ondelete='CASCADE'), primary_key=True)
    product_code = Column(ForeignKey('products.code',
        onupdate='CASCADE', ondelete='RESTRICT'), primary_key=True)
    amount = Column(Numeric(),
        nullable=False)
    price = Column(Numeric(4),
        primary_key=True)
    currency_code = Column(ForeignKey('currencies.code',
        onupdate='CASCADE', ondelete='RESTRICT'), primary_key=True)
    vat = Column(Numeric(2),
        primary_key=True)

    product = sqlalchemy.orm.relationship('Product')
    currency = sqlalchemy.orm.relationship('Currency')

    def set_bprice(self, bprice):
        self.price = decimal.Decimal(math.floor(
            bprice / (self.vat / 100 + 1) * 100) / 100)
        session.flush()

    def set_netto(self, netto):
        self.price = decimal.Decimal(
            math.floor(netto / self.amount * 100) / 100)
        session.flush()

    def set_brutto(self, brutto):
        self.price = decimal.Decimal(math.floor(
            brutto / (self.vat / 100 + 1) / self.amount * 100) / 100)
        session.flush()

    bprice = property(
        lambda self: (self.vat * decimal.Decimal('.01') + 1) * self.price,
        set_bprice)
    netto = property(
        lambda self: self.price * self.amount,
        set_netto)
    tax = property(
        lambda self: self.vat * decimal.Decimal('.01') * self.netto)
    brutto = property(
        lambda self: self.netto + self.tax,
        set_brutto)

    def __repr__(self):
        return ('<{0.__class__.__name__} {0.product_code!r}'
            ' invoice={0.invoice_no!r}'
            ' amount={0.amount!r}'
            ' price={0.price!r}'
            ' currency={0.currency_code!r}'
            ' vat={0.vat!r}>').format(self)


engine = sqlalchemy.create_engine(
    'sqlite:///{}'.format(os.path.expanduser(invoice.config.dbfilename)))
Session = sqlalchemy.orm.sessionmaker(bind=engine)
session = Session()

def init():
    Base.metadata.create_all(engine)
    session.add(Currency(code='PLN'))
    session.add(Currency(code='EUR'))
    session.add(Currency(code='USD'))
    session.add(Feature(code='28b', description='Odwrotne obciążenie'))
    session.commit()

# vim: ts=4 sts=4 sw=4 et
