# Makefile
# ...project commands...
PY := python -m

setup:
	pip install -r requirements.txt
	pre-commit install

lint:
	pre-commit run --all-files

test:
	pytest -q

crawl:
	$(PY) cli crawl

analyze:
	$(PY) cli analyze

docker-build:
	docker build -t cardfinder:latest ./docker
