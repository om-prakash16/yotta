PY ?= python3
.PHONY: install test docs starter full reproduce-starter reproduce-full all
install:; $(PY) -m pip install -r requirements.txt
test:; $(PY) -m pytest -q
docs:; $(PY) -m busroute docs --out docs
starter:; $(PY) -m busroute generate --profile starter --out datasets/starter
full:; $(PY) -m busroute generate --profile full --out datasets/full
reproduce-starter:; $(PY) -m busroute reproduce --profile starter --out docs/starter_repro
reproduce-full:
	$(PY) -m busroute generate --profile full --out datasets/full_run1 --formats csv,json,sql
	$(PY) -m busroute validate --data datasets/full_run1/data --ground-truth datasets/full_run1/ground_truth/ground_truth.csv
	$(PY) scripts/verify_sqlite_seed.py --seed datasets/full_run1/data/seed.sql
	$(PY) -m busroute generate --profile full --out datasets/full_run2 --formats csv,json,sql
	$(PY) scripts/compare_reproducibility.py --first datasets/full_run1 --second datasets/full_run2 --out docs/reproducibility_full.json
all: install test docs starter reproduce-starter
