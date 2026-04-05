.PHONY: install test lint format coverage clean

install:
	pip install -e . pytest coverage ruff black pre-commit

test:
	pytest -q

lint:
	ruff check src/ tests/
	black --check src/ tests/

format:
	ruff check src/ tests/ --fix
	black src/ tests/

coverage:
	coverage run -m pytest -q
	coverage report -m

clean:
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
