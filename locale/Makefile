PYBABEL = ./pybabel
DOMAIN = invoice

locale:
	$(PYBABEL) compile -d . -D $(DOMAIN)

clean:
	$(RM) */*/*.mo invoice.pot

update: invoice.pot
	$(PYBABEL) update -d . -D $(DOMAIN) -i $<

.PHONY: all clean update

invoice.pot: babel.cfg ../templates
	$(PYBABEL) extract -o $@ -F $< ..

# vim: ts=8 sts=8 sw=8 noet
