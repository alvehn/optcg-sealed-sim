.PHONY: help setup fetch cards test lint fmt sim show pool pools sealed

PY := .venv/bin/python
SET ?= OP-18
CARD_LANG ?= english
RAW ?= data/raw/punk-records
GAMES ?= 400
EVENTS ?= 1000
PLAYERS ?= 24
P0 ?= heuristic
P1 ?= heuristic
SEED ?= 0
# Read cards from the local clone made by `make fetch` when it exists, else from GitHub.
LOCAL := $(if $(wildcard $(RAW)/.git),--local $(RAW))
PACK_ID_ARG := $(if $(PACK_ID),--pack-id $(PACK_ID))

help: ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/'

setup: ## create .venv and install
	python3 -m venv .venv
	$(PY) -m pip install -U pip
	$(PY) -m pip install -e ".[dev]"

fetch: ## clone/refresh punk-records into data/raw (gitignored)
	@mkdir -p data/raw
	@if [ -d $(RAW)/.git ]; then git -C $(RAW) pull --ff-only -q; \
	else git clone -q --depth 1 https://github.com/buhbbl/punk-records.git $(RAW); fi
	@git -C $(RAW) log -1 --format='punk-records @ %ci'

cards: ## build data/cards/$(SET).json  (make cards SET=OP-18 [PACK_ID=569118] [CARD_LANG=english])
	$(PY) -m optcg.cli cards --set $(SET) --lang $(CARD_LANG) $(LOCAL) $(PACK_ID_ARG)

test: ## run tests
	$(PY) -m pytest

lint: ## ruff check
	$(PY) -m ruff check src tests

fmt: ## ruff format + fix
	$(PY) -m ruff format src tests
	$(PY) -m ruff check --fix src tests

sim: ## games between two random decks
	$(PY) -m optcg.cli sim --set $(SET) --games $(GAMES) --p0 $(P0) --p1 $(P1)

show: ## print one game's log
	$(PY) -m optcg.cli show --set $(SET) --p0 $(P0) --p1 $(P1)

pool: ## open one sealed pool and show the deck built from it
	$(PY) -m optcg.cli pool --set $(SET) --seed $(SEED)

pools: ## pool statistics over many events  (make pools EVENTS=1000 PLAYERS=24)
	$(PY) -m optcg.cli pools --set $(SET) --events $(EVENTS) --players $(PLAYERS) --seed $(SEED)

sealed: ## games between freshly opened sealed decks
	$(PY) -m optcg.cli sealed --set $(SET) --games $(GAMES) --p0 $(P0) --p1 $(P1)
