printMsg=printf "\033[36m\033[1m%-15s\033[0m\033[36m %-30s\033[0m\n"

.PHONY: help
## use triple hashes ### to indicate main build targets
help:
	@awk 'BEGIN {FS = ":[^#]*? ### "} /^[a-zA-Z_-]+:[^#]* ### / {printf "\033[1m\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@awk 'BEGIN {FS = ":[^#]*? ## "} /^[a-zA-Z_-]+:[^#]* ## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
.DEFAULT_GOAL := help

UV_PYTHON?=3.11
export UV_PYTHON

PYTEST_ARGS?=''
PYTEST_CMD=uv run pytest ${PYTEST_ARGS}

install: ### Install deps
	uv sync

upgrade-deps: ### Upgrade deps
	uv sync --upgrade

format: ## Format code
	uv run ruff format
	uv run ruff check --fix 
	uv run ruff check --fix --select I

lint: ## Lint code
	uv run ruff check

format-check: ## Check code formatting
	uv run ruff format --check

typecheck: ## Typecheck code
	uv run mypy --check-untyped-defs -p waylay.sdk
	uv run mypy --check-untyped-defs test/*/*.py
	@${printMsg} typecheck OK

code-qa: format-check lint typecheck ### perform code quality checks

test-unit: install
	${PYTEST_CMD} test/unit

test-unit-coverage: install
	${PYTEST_CMD} --cov-report term-missing:skip-covered --cov=src --cov-fail-under=90 test/unit

test-unit-coverage-report: install ### generate html coverage report for the unit tests
	${PYTEST_CMD} --cov-report html:cov_report --cov=src --cov-fail-under=90 test/unit

test-coverage-report: install ### generate html coverage report for the unit and integration tests
	${PYTEST_CMD} --cov-report html:cov_report_all --cov=src --cov-fail-under=90 test/unit test/integration

test-integration: install
	${PYTEST_CMD} test/integration

test-integration-coverage-report: install ### generate html coverage report for the integration tests
	${PYTEST_CMD} --cov-report html:cov_report/integration --cov=src test/integration

test: format code-qa test-unit ### perform all quality checks and tests, except for integration tests

dist-clean:
	rm -fr dist

dist: ci-install dist-clean ### Create dist
	uv build


ci-install:
	uv sync --frozen

ci-install-latest:
	uv sync --upgrade

ci-code-qa: code-qa

## TODO: enable test-unit-coverage
ci-test-unit:
	uv run pytest test/unit

ci-test-integration:
	uv run pytest test/integration

ci-dist: dist


pdoc: # TODO 
	rm -fr ./doc/api/
	uv run pdoc -o ./doc/api \
		waylay.sdk \
		waylay.sdk.config \
		waylay.sdk.config.client \
		waylay.sdk.config.model \
		waylay.sdk.auth \
		waylay.sdk.auth.provider \
		waylay.sdk.auth.model \
		waylay.sdk.auth.interactive \
		waylay.sdk.auth.exceptions \
		waylay.sdk.auth.parse \
		waylay.sdk.client \
		waylay.sdk.plugin \
		waylay.sdk.plugin.client \
		waylay.sdk.plugin.loader \
		waylay.sdk.plugin.base \
		waylay.sdk.api \
		waylay.sdk.api.client \
		waylay.sdk.api.http \
		waylay.sdk.api.exceptions \
		waylay.sdk.api.serialization \
		waylay.sdk.exceptions


test-publish:
	uv tool run twine upload --repository testpypi dist/*
	open https://test.pypi.org/project/waylay-sdk-core

_assert_tagged:
	@ ${VENV_ACTIVATE} && export _PKG_VERSION_SCRIPT='from importlib.metadata import version; print(version("waylay-sdk-core"))' && \
		export _PKG_VERSION=$$(python -c "$${_PKG_VERSION_SCRIPT}") && \
		export _GIT_VERSION=$$(git describe --tags --dirty) && \
	echo "package version: $${_PKG_VERSION}" &&\
	echo "git tag version: $${_GIT_VERSION}" &&\
	if [[ $${_PKG_VERSION} != $${_GIT_VERSION} ]]; \
	then ${printMsg} "Versions do not agree. Tag and invoke _make dist_ first." && exit 1; \
	fi

publish: _assert_tagged
	uv tool run twine upload dist/*
	open https://pypi.org/project/waylay-sdk-core