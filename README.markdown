# Invoice generator for ITL and friends

Simple, file-and-editor-oriented, beautiful invoice generator.

## installation and configuration

```
sudo apt-get install \
    python3-babel \
    python3-jinja2 \
    python3-lxml \
    context
sudo make install
mkdir -p ~/Invoices ~/.invoice ~/.invoice/templates

# copy example files and adapt to your needs (more documentation in comments)
cp Documentation/examples/invoice.cfg ~/.invoice/
cp Documentation/examples/invoice.tex ~/.invoice/templates/
#vim <...>

# this is the number of last invoice; the next one in 2018 will be "2018/124"
echo '{"2018": 123}' > ~/.invoice/state

# now, once per invoice (or per client), get the draft, adapt and voila
cp Documentation/examples/draft.cfg ~/Invoices/draft1.cfg
cp Documentation/examples/draft.cfg ~/Invoices/draft2.cfg
#vim <...>

# NOTE: this command is most likely NOT INVARIANT
# (if you run the command multiple times, you'll get so many invoices)
invoice ~/Invoice/draft1.cfg

# and the result is hopefuly in ~/Invoices/Invoice_<NUMBER>.pdf

# also see:
invoice --help
```

## invariant generation

To have invariant generation, you have to explicitly spell the number:
```
invoice -o invoice/number=2018/456 ~/Invoices/draft1.cfg
```
or, alternatively, have number specified in draft:
```
[invoice]
number = 2018/456
```

## hacking

After changing `{% trans %}` blocks (or after introducing those in your template
and copying your template for processing to `Documentation/examples/`), run:
```
make update_catalog
```
And then edit `invoice/locale/**/invoice.po`.

And of course after messing with Python:
```
pylint3 invoice
```
