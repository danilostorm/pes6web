PYTHON ?= python3
.PHONY: test inspect bootstrap decrypter serve

test:
	$(PYTHON) -m unittest discover -s tests -v

inspect:
	@test -n "$(DISC)" || (echo 'Usage: make inspect DISC=/path/to/extracted_disc'; exit 2)
	$(PYTHON) tools/inspect_psp.py "$(DISC)"

bootstrap:
	bash scripts/bootstrap.sh

decrypter:
	bash scripts/build-decrypter.sh

serve:
	bash scripts/serve.sh
