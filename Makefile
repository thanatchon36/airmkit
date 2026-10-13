# airmkit — development and reproduction targets.
#
# `make setup` once, then `make quick` while working (≤5 min) and `make reproduce` to rebuild
# every number, table and figure in the paper from the committed sources (≤60 min, no hosted API).
#
# Long targets run under `caffeinate -i` on macOS so a sleeping laptop cannot truncate a run.

PY := .venv/bin/python
PIP := .venv/bin/python -m pip
AIRM := .venv/bin/airm
PYTEST := .venv/bin/python -m pytest
RUFF := .venv/bin/ruff
MYPY := .venv/bin/mypy
EXPERIMENT_ENV := PYTHONPATH=experiments
EXAMPLE := examples/synthetic_bank
EXAMPLE_OUT := $(EXAMPLE)/output
NOSLEEP := $(shell command -v caffeinate >/dev/null 2>&1 && echo "caffeinate -i")
PANDOC := $(shell command -v pandoc 2>/dev/null)
PDF_ENGINE := $(firstword $(foreach e,tectonic xelatex pdflatex typst weasyprint, \
	$(if $(shell command -v $(e) 2>/dev/null),$(e),)))

.DEFAULT_GOAL := help
.PHONY: help setup quick test lint format schemas example experiments collect paper docs \
	reproduce clean publish

help: ## Show this help
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "} {printf "  \033[1m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Create .venv with uv and install the package with every extra
	uv venv -p 3.11
	uv pip install -e ".[dev,report,experiments,ollama]"
	@echo "Ollama is optional: RQ3 needs `ollama serve` and a model ≤4B (qwen3.5:0.8b by default)."

lint: ## ruff check + ruff format --check + mypy --strict
	$(RUFF) check src tests experiments
	$(RUFF) format --check src tests experiments
	$(MYPY)

format: ## Apply ruff formatting
	$(RUFF) format src tests experiments
	$(RUFF) check --fix src tests experiments

test: ## Full test suite with coverage
	$(PYTEST) tests/ --cov=airm --cov-report=term-missing

quick: ## Lint, fast tests and the worked example — the ≤5 min pre-commit gate
	$(RUFF) check src tests experiments
	$(MYPY)
	$(PYTEST) tests/ -q -m "not slow and not ollama"
	$(MAKE) example

schemas: ## Export JSON Schemas for every format to schemas/
	$(AIRM) schemas --out schemas

example: ## Run the toolkit end-to-end on the synthetic bank and write the audit pack
	$(AIRM) assess -r $(EXAMPLE)/ai-inventory.yaml
	$(AIRM) check -r $(EXAMPLE)/ai-inventory.yaml \
		--trail $(EXAMPLE)/evidence/trail.jsonl || true
	$(AIRM) report -r $(EXAMPLE)/ai-inventory.yaml \
		--vendors $(EXAMPLE)/third-party-assessments.yaml \
		--trail $(EXAMPLE)/evidence/trail.jsonl \
		-o $(EXAMPLE_OUT)
	@echo "Audit pack in $(EXAMPLE_OUT); start with 00-board-summary.md"

experiments: ## Run RQ1-RQ5 (RQ3 needs Ollama) and write results/ and figures
	$(NOSLEEP) $(EXPERIMENT_ENV) $(PY) experiments/rq1_automatability.py
	$(NOSLEEP) $(EXPERIMENT_ENV) $(PY) experiments/rq2_autonomy.py
	$(NOSLEEP) $(EXPERIMENT_ENV) $(PY) experiments/rq3_guardrails.py
	$(NOSLEEP) $(EXPERIMENT_ENV) $(PY) experiments/rq4_crosswalk.py
	$(NOSLEEP) $(EXPERIMENT_ENV) $(PY) experiments/rq5_cost.py

collect: ## Merge the per-RQ results into results/summary.json
	$(EXPERIMENT_ENV) $(PY) experiments/collect.py

paper: collect ## Render the paper, exec summary and posts, then build paper/paper.pdf
	$(EXPERIMENT_ENV) $(PY) experiments/render_paper.py
ifeq ($(PANDOC),)
	@echo "pandoc not found: paper/paper.md is rendered; install pandoc for PDF/DOCX."
else
	cd paper && $(PANDOC) paper.md -o paper.docx --toc
ifeq ($(PDF_ENGINE),)
	@echo "No LaTeX/typst engine found; writing paper/paper.html instead of paper.pdf."
	@echo "For a PDF: brew install tectonic (or basictex), then re-run make paper."
	cd paper && $(PANDOC) paper.md -o paper.html --standalone --toc --embed-resources
else
	cd paper && $(PANDOC) paper.md -o paper.pdf --toc --pdf-engine=$(PDF_ENGINE)
endif
endif

docs: ## Build the mkdocs site, regenerating the clause index first
	$(AIRM) clauses --format markdown -o docs/clause-index.md
	.venv/bin/mkdocs build --strict

reproduce: ## Rebuild every artefact in the paper from the committed sources
	$(MAKE) lint
	$(MAKE) test
	$(MAKE) schemas
	$(MAKE) example
	$(MAKE) experiments
	$(MAKE) paper
	@git --no-pager diff --stat -- results schemas paper docs || true
	@echo "If the diff above is empty, this clone reproduces the published run."

clean: ## Remove build, cache and generated example output
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	rm -rf $(EXAMPLE_OUT) site paper/paper.pdf paper/paper.html paper/paper.docx
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

publish: ## Build the sdist and wheel, check them, and print the release steps
	rm -rf dist
	$(PIP) install --quiet --upgrade build twine
	$(PY) -m build
	$(PY) -m twine check dist/*
	@echo
	@echo "Built dist/. Publishing happens in CI on a tag, via PyPI trusted publishing:"
	@echo "  git tag -a v0.1.0 -m 'airmkit 0.1.0' && git push origin v0.1.0"
	@echo "To upload by hand instead: .venv/bin/python -m twine upload dist/*"
