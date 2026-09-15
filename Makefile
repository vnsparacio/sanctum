PYTHON ?= .venv/bin/python
PREFIX ?= $(CURDIR)/.local
.PHONY: deps build setup doctor up status logs test down uninstall audit

deps:
	npm ci --ignore-scripts
	uv venv --python 3.12 .venv
	uv pip install --python .venv/bin/python -r gate/runtime/requirements.txt
build:
	$(PYTHON) -B scripts/build.py
setup doctor up status logs down uninstall:
	$(PYTHON) -B scripts/release_operator.py $@ --prefix "$(PREFIX)"
test:
	$(PYTHON) -B scripts/test.py
audit:
	$(PYTHON) -B scripts/audit.py
