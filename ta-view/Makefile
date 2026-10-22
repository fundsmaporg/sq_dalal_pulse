.PHONY: demo test batch cards
PORT ?= 8000

demo:
	@echo "Open http://localhost:$(PORT)"
	uvicorn taview.api:app --host 127.0.0.1 --port $(PORT)

test:
	pytest -q

batch:
	python -m taview.batch --horizons swing,medium,long

cards:
	pip install -q playwright && playwright install chromium
