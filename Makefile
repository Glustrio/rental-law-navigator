PY := .venv/bin/python
STARTER_FOLDER := https://drive.google.com/drive/folders/1XJxcpU2DcCzmd6nqNFIIMb03BJBe65ag

.PHONY: all setup starter geocode supplement extract consolidate outputs site serve test lint

all: geocode supplement extract consolidate outputs

setup:
	python3 -m venv .venv
	$(PY) -m pip install -q -r requirements.txt

starter:
	.venv/bin/gdown --folder $(STARTER_FOLDER) -O starter

geocode:
	$(PY) -m navigator.geocode

supplement:
	$(PY) -m navigator.supplement

extract:
	$(PY) -m navigator.extract

consolidate:
	$(PY) -m navigator.consolidate

outputs:
	$(PY) -m navigator.plain_language
	$(PY) -m navigator.lookups
	$(PY) -m navigator.changes
	$(PY) -m navigator.build_site

serve:
	cd site && python3 -m http.server 8000

test:
	$(PY) -m pytest -q tests

lint:
	.venv/bin/ruff check navigator tests
