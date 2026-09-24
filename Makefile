PYTHON ?= .venv/bin/python
PREFIX ?= $(CURDIR)/.local
.PHONY: deps build ensure-build setup doctor up status logs start stop format format-check lint test test-gate test-gate-js test-gate-python test-reliability test-mcp test-plugins test-release test-agents down uninstall audit verify-source

deps:
	npm ci --ignore-scripts
	uv venv --python 3.12 --allow-existing .venv
	uv pip install --python .venv/bin/python -r gate/runtime/requirements.txt
	uv pip install --python .venv/bin/python -r requirements-dev.txt
build:
	$(PYTHON) -B scripts/build.py
ensure-build:
	$(PYTHON) -B scripts/build.py --if-needed
setup doctor up status logs down uninstall:
	$(PYTHON) -B scripts/release_operator.py $@ --prefix "$(PREFIX)"
start stop:
	./sanctum $@ --prefix "$(PREFIX)"
format:
	$(PYTHON) -m black .
format-check:
	$(PYTHON) -m black --check .
lint:
	$(PYTHON) -m ruff check .
test: ensure-build
	$(PYTHON) -B scripts/test.py all
test-gate:
	$(PYTHON) -B scripts/test.py gate
test-gate-js:
	$(PYTHON) -B scripts/test.py gate-js
test-gate-python:
	$(PYTHON) -B scripts/test.py gate-python
test-reliability: ensure-build
	$(PYTHON) -B scripts/test.py reliability
test-mcp:
	$(PYTHON) -B scripts/test.py mcp
test-plugins:
	$(PYTHON) -B scripts/test.py plugins
test-release: ensure-build
	$(PYTHON) -B scripts/test.py release
test-agents:
	$(PYTHON) -B scripts/test.py agents
audit:
	$(PYTHON) -B scripts/audit.py
verify-source: ensure-build
	$(PYTHON) -B -c 'from scripts.release_operator import verify; verify(); print("Source manifest and runtime pins verified.")'
