LOCALEPATH = invoice/locale
LOCALEDOMAIN = invoice
POTFILE = $(LOCALEPATH)/$(LOCALEDOMAIN).pot

PYTHON ?= python3
RM ?= rm -f

all:
.PHONY: all

build: locale
	$(PYTHON) setup.py build

install: locale
	$(PYTHON) setup.py install
.PHONY: install

locale:
	$(PYTHON) setup.py compile_catalog \
		-d $(LOCALEPATH) -D $(LOCALEDOMAIN)
.PHONY: locale

update_catalog: $(POTFILE)
	$(PYTHON) setup.py update_catalog -i $< \
		-d $(LOCALEPATH) -D $(LOCALEDOMAIN)

$(POTFILE): invoice/templates Documentation/examples
	$(PYTHON) setup.py extract_messages -o $(POTFILE)
extract_messages: $(POTFILE)
.PHONY: extract_messages


clean:
	$(RM) -r \
		build \
		dist \
		*.egg-info \
		$(LOCALEPATH)/*/*/*.mo \
		$(POTFILE)
.PHONY: clean

# vim: tw=80 ts=8 sts=8 sw=8 noet
