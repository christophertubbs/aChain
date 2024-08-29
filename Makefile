PYENV=venv
PYTHON=$(PYENV)/bin/python3
NAMESPACE_DIR := ./achain/

PACKAGE := achain

.PHONY: help test install uninstall develop clean

help:
	    @echo "aChain makefile commands:"
	    @echo "  install : install from local source code"
	    @echo "  develop : install in editable mode (pip -e) from local source code"
	    @echo "  test : run unit tests"
	    @echo "  uninstall : uninstall aChain"
	    @echo "  clean : delete python virtual environment"
		@echo
		@echo "  utility requirements:"
		@echo "    pip > 21.1"

.DEFAULT_GOAL := help

test: develop
	$(PYTHON) -m pytest -s

install: $(PYENV)/bin/activate has_pip
	$(PYTHON) -m pip install .

uninstall: $(PYENV)/bin/activate has_pip
	$(PYTHON) -m pip uninstall -y $(PACKAGE)

develop: $(PYENV)/bin/activate has_pip
	$(PYTHON) -m pip install --editable .

$(PYENV)/bin/activate:
	test -d $(PYENV) || $(PYTHON) -m venv $(PYENV)
	$(PYTHON) -m pip install --upgrade pip wheel setuptools build pytest
	touch $(PYENV)/bin/activate

has_pip:
	@ $(PYTHON) -c "import pip"

clean:
	rm -rf $(PYENV)