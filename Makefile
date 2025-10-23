# Makefile for GPU Scheduler Development

.PHONY: help install install-dev test test-unit test-integration test-e2e coverage clean lint format type-check

help:
	@echo "GPU Scheduler Development Commands"
	@echo "=================================="
	@echo "install          - Install package dependencies"
	@echo "install-dev      - Install package + development dependencies"
	@echo "test             - Run all tests"
	@echo "test-unit        - Run unit tests only"
	@echo "test-integration - Run integration tests only"
	@echo "test-e2e         - Run end-to-end tests only"
	@echo "coverage         - Run tests with coverage report"
	@echo "lint             - Run linters (ruff, flake8)"
	@echo "format           - Format code with black and isort"
	@echo "type-check       - Run mypy type checking"
	@echo "clean            - Clean up generated files"
	@echo "clean-test       - Clean test artifacts"

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	pip install -e .

test:
	pytest

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

test-e2e:
	pytest tests/e2e/ -v

test-fast:
	pytest -m "not slow"

coverage:
	pytest --cov=scheduler --cov-report=html --cov-report=term-missing
	@echo "Coverage report generated in htmlcov/index.html"

coverage-xml:
	pytest --cov=scheduler --cov-report=xml

lint:
	@echo "Running ruff..."
	ruff check scheduler/ tests/
	@echo "Running flake8..."
	flake8 scheduler/ tests/

format:
	@echo "Running black..."
	black scheduler/ tests/
	@echo "Running isort..."
	isort scheduler/ tests/

format-check:
	black --check scheduler/ tests/
	isort --check scheduler/ tests/

type-check:
	mypy scheduler/

clean: clean-test clean-pyc clean-build

clean-test:
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -f coverage.xml

clean-pyc:
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete
	find . -type f -name '*.pyo' -delete

clean-build:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info

# Development workflow
dev: install-dev format lint type-check test

# CI workflow
ci: lint type-check coverage-xml

# Quick validation
check: format-check lint type-check test-fast
