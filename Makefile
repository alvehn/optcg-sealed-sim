.PHONY: setup cards test lint fmt sim show

PY := .venv/bin/python
SET ?= OP-17
GAMES ?= 400
P0 ?= heuristic
P1 ?= heuristic

setup:
	python3 -m venv .venv
	$(PY) -m pip install -U pip
	$(PY) -m pip install -e ".[dev]"

cards:
	$(PY) -m optcg.cli cards --set $(SET)

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check src tests

fmt:
	$(PY) -m ruff format src tests
	$(PY) -m ruff check --fix src tests

sim:
	$(PY) -m optcg.cli sim --set $(SET) --games $(GAMES) --p0 $(P0) --p1 $(P1)

show:
	$(PY) -m optcg.cli show --set $(SET) --p0 $(P0) --p1 $(P1)
