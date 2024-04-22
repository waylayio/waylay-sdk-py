printMsg=printf "\033[36m\033[1m%-15s\033[0m\033[36m %-30s\033[0m\n"

.PHONY: help
## use triple hashes ### to indicate main build targets
help:
	@awk 'BEGIN {FS = ":[^#]*? ### "} /^[a-zA-Z_-]+:[^#]* ### / {printf "\033[1m\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@awk 'BEGIN {FS = ":[^#]*? ## "} /^[a-zA-Z_-]+:[^#]* ## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
.DEFAULT_GOAL := help

VENV_DIR=.venv
VENV_ACTIVATE_CMD=${VENV_DIR}/bin/activate
VENV_ACTIVATE=. ${VENV_ACTIVATE_CMD}

REQ_FILE_BUILD=requirements/requirements.build.$$(bin/pyversion).txt
REQ_FILE=requirements/requirements.$$(bin/pyversion).txt
REQ_FILE_DEV=requirements/requirements.dev.$$(bin/pyversion).txt

PYTEST_ARGS?=''
PYTEST_CMD=${VENV_ACTIVATE} && pytest ${PYTEST_ARGS}

${VENV_ACTIVATE_CMD}:
	python3 -m venv ${VENV_DIR}
	${VENV_ACTIVATE} && make dev-install

install: ${VENV_ACTIVATE_CMD}

assert-venv:
	@if [[ "$$(python -c 'import sys; print(sys.prefix)')" != "$$(pwd)/${VENV_DIR}" ]]; \
	  then ${printMsg} "Please run in the correct python venv: ${VENV_DIR}" "FAILED"; exit 1; fi

clean: dist-clean
	rm -fr ${VENV_DIR}
	rm -fr .*_cache
	rm -fr **/.*_cache
	rm -fr **/__pycache__
	rm -fr src/*.egg-info

exec-dev-dependencies:
	pip install -r "${REQ_FILE_BUILD}"
	pip install -e . --no-deps
	pip install -r "${REQ_FILE}"
	pip install -r "${REQ_FILE_DEV}"
	pip install -e test/plugin
	
exec-upgrade-buildtools:
	pip install --upgrade pip
	pip install --upgrade setuptools
	pip install --upgrade wheel
	pip install --upgrade build

clean-caches:
	find . -name '__pycache__' | xargs -L 1 rm -frv 
	find . -name '.mypy_cache' | xargs -L 1 rm -frv 
	rm -fr .mypy_cache
	rm -fr .pytest_cache
	rm -fr .coverage
	rm -fr .cache
	@${printMsg} "clean-caches" "Cleaned caches for pytest, coverage, type inference, ..."

dist-clean:
	rm -fr dist build

exec-dev-install-pkg:  ## Install waylay-sdk-core with development dependency constraints as specified in the package.
	pip install -e ".[dev]"
	pip install -e test/plugin

exec-dev-install: ### Install a development environment with frozen dependencies'
	make exec-dev-dependencies
	make exec-dev-install-pkg

exec-install-pkg: ### Install waylay-sdk-core with dependency constraints as specified in the package. (e.g. for notebook tests)
	pip install -e .

exec-dist:
	python -m build
	rm -fr build

dev-install: install
	@${VENV_ACTIVATE} && make exec-dev-install

dev-reinstall: clean dev-install ### Remove all dependences and reinstall with frozen dependencies

dist: clean install
	@${VENV_ACTIVATE} && make exec-dist

exec-lint-fix:
	@ruff check --fix

exec-lint:
	@ruff check

exec-typecheck:
	@mypy -p waylay.sdk
	@mypy test/*/*.py
	@${printMsg} typecheck OK

exec-format:
	@ruff format

exec-code-qa: exec-lint exec-typecheck

exec-test: exec-code-qa
	pytest ${PYTEST_ARGS} test/unit

format: install
	${VENV_ACTIVATE} && make exec-format exec-lint-fix

code-qa: install ### perform code quality checks
	${VENV_ACTIVATE} && make exec-code-qa

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

test: format test-unit ### perform all quality checks and tests, except for integration tests


ci-install:
	make exec-dev-dependencies
	make exec-dev-install-pkg

ci-install-latest:
	make exec-upgrade-buildtools
	# latest regular dependencies
	make exec-install-pkg
	# frozen development dependencies
	make exec-dev-dependencies

ci-code-qa: exec-lint exec-typecheck ### perform code quality checks

## TODO: enable test-unit-coverage
ci-test-unit: test-unit 

ci-test-integration: test-integration

ci-dist: dist-clean exec-dist


freeze-dependencies: ## perform a full reinstall procedure and regenerate the 'requirements/requirements[.dev][.pyversion].txt' files
	make clean
	python3 -m venv ${VENV_DIR}
	@${VENV_ACTIVATE} && make exec-freeze-deps


FREEZE_CMD=bin/freeze-dependencies
exec-freeze-deps:
	make exec-upgrade-buildtools
	REQ_PIP_ARGS="--all" REQ_FILE="${REQ_FILE_BUILD}" ${FREEZE_CMD}
	make exec-install-pkg
	REQ_FILE="${REQ_FILE}" REQ_EXCLUDES="${REQ_FILE_BUILD}" ${FREEZE_CMD}
	make exec-dev-install-pkg
	REQ_FILE="${REQ_FILE_DEV}" REQ_EXCLUDES="${REQ_FILE_BUILD} ${REQ_FILE}" ${FREEZE_CMD}


CONDA_INIT=source $$(conda info --base)/etc/profile.d/conda.sh


PYTHON_VERSION?=3.9
PYTHON_VERSIONS=3.9 3.10 3.11 3.12

freeze-deps-conda:
	@-conda env remove -n waylay-sdk-${PYTHON_VERSION}
	@conda create -y -n waylay-sdk-${PYTHON_VERSION} python=${PYTHON_VERSION} 
	@${CONDA_INIT} && conda activate waylay-sdk-${PYTHON_VERSION} && make exec-freeze-deps

install-conda:
	-conda create -y -n waylay-sdk-${PYTHON_VERSION} python=${PYTHON_VERSION} 
	@${CONDA_INIT} && conda activate waylay-sdk-${PYTHON_VERSION} && make exec-dev-install

test-conda:
	@${CONDA_INIT} && conda activate waylay-sdk-${PYTHON_VERSION} && make exec-test

TARGET?=test-conda
_exec_all_python_versions:
	@for ver in ${PYTHON_VERSIONS}; do ${printMsg} "${TARGET}" "$$ver"; PYTHON_VERSION=$$ver make ${TARGET} || exit 1; done
	@${printMsg} "${TARGET}" "DONE: ${PYTHON_VERSIONS}"

freeze-deps-all:  ## freeze dependencies for all python versions
	TARGET=freeze-deps-conda make _exec_all_python_versions

test-conda-all:  ## test on all python versions
	TARGET=test-conda make _exec_all_python_versions

install-conda-all:
	TARGET=install-conda make _exec_all_python_versions

pdoc: # TODO 
	rm -fr ./doc/api/
	${VENV_ACTIVATE} && pip install pdoc
	${VENV_ACTIVATE} && pdoc -o ./doc/api \
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
	${VENV_ACTIVATE} && pip uninstall pdoc -y


test-publish:
	${VENV_ACTIVATE} && pip install twine
	${VENV_ACTIVATE} && python -m twine upload --repository testpypi dist/*
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
	${VENV_ACTIVATE} && pip install twine
	${VENV_ACTIVATE} && python -m twine upload dist/*
	open https://pypi.org/project/waylay-sdk-core