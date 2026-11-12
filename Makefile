PY := .venv/bin/python
DBT := .venv/bin/dbt --project-dir dbt --profiles-dir dbt

.PHONY: setup download ingest dq dbt analysis scorecard corpus audit eval app test all

setup:
	uv venv --python 3.12 .venv && uv pip install -e ".[dev,dbt,llm]"

download:
	$(PY) -m olac.ingest.download

ingest:
	$(PY) -m olac.ingest.ccac
	$(PY) -m olac.ingest.intl
	$(PY) -m olac.ingest.funding

dq:
	$(PY) -m olac.dq

dbt:
	$(DBT) build

analysis:
	$(PY) -m olac.analysis.index
	$(PY) -m olac.analysis.trends

scorecard:
	$(PY) -m olac.scorecard.crawl
	$(PY) -m olac.scorecard.score

corpus:
	$(PY) -m olac.audit.corpus

audit:
	$(PY) -m olac.audit.extract --backend rules
	$(PY) -m olac.audit.its

eval:
	$(PY) -m olac.audit.evaluate

app:
	.venv/bin/streamlit run app/streamlit_app.py

test:
	.venv/bin/pytest -q

all: download ingest dq dbt analysis scorecard corpus audit eval
