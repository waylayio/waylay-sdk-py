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

${VENV_ACTIVATE_CMD}:
	python3 -m venv ${VENV_DIR}
	${VENV_ACTIVATE} && make dev-install

install: ${VENV_ACTIVATE_CMD}

clean:
	rm -fr ${VENV_DIR}
	rm -fr .*_cache
	rm -fr */.*_cache
	rm -fr */src/*.egg-info

install-dependencies:
	pip install -r requirements/requirements.$$(bin/pyversion).txt

install-dev-dependencies:
# need to install the `waylay-sdk` first, because the `waylay_<SERVICE>` packages require it
	pip install -e . --no-deps
	pip install -r requirements/requirements.$$(bin/pyversion).txt
	pip install -r requirements/requirements.dev.$$(bin/pyversion).txt
	pip install -e test/plugin
	
uninstall-dependencies:
	pip uninstall -r requirements/requirements.$$(bin/pyversion).txt -y
	pip uninstall -r requirements/requirements.dev.$$(bin/pyversion).txt -y

clean-eggs:
	find . -name '.eggs' | xargs -L 1 rm -frv 
	find . -name '*.egg-info' | xargs -L 1 rm -frv 
	@${printMsg} "clean-eggs" ".eggs folders cleaned"

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

uninstall-pkg: dist-clean
	pip uninstall waylay-sdk -y
	pip uninstall waylay-sdk-plugin-example -y
	@${printMsg} "uninstall-pkg" "Development packages uninstalled"

full-clean:
	make uninstall-pkg
	make uninstall-dependencies
	make clean-caches
	make clean-eggs

dev-install-pkg:  ## Install waylay-sdk with development dependency constraints as specified in the package.
	pip install -e ".[dev]"
	pip install -e test/plugin

dev-install:  ### Install a development environment with frozen dependencies from 'requirements/requirements.[dev.].txt'
	make ci-upgrade-buildtools
	make install-dev-dependencies
	make dev-install-pkg

install-pkg:  ### Install waylay-sdk with dependency constraints as specified in the package. (e.g. for notebook tests)
	pip install .

dev-reinstall: full-clean  dev-install  ### Remove all dependences and reinstall with frozen dependencies

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

code-qa: install ### perform code quality checks
	${VENV_ACTIVATE} && make exec-code-qa
exec-code-qa: exec-lint-fix exec-format exec-typecheck


test-unit: install
	${VENV_ACTIVATE} && pytest test/unit

test-unit-coverage: install
	${VENV_ACTIVATE} && pytest --cov-report term-missing:skip-covered --cov=src --cov-fail-under=90 test/unit

test-unit-coverage-report: install ### generate html coverage report for the unit tests
	${VENV_ACTIVATE} && pytest --cov-report html:cov_report --cov=src --cov-fail-under=90 test/unit

test-coverage-report: install ### generate html coverage report for the unit and integration tests
	${VENV_ACTIVATE} && pytest --cov-report html:cov_report_all --cov=src --cov-fail-under=90 test/unit test/integration

test-integration: install
	${VENV_ACTIVATE} && pytest test/integration

test-integration-coverage-report: install ### generate html coverage report for the integration tests
	${VENV_ACTIVATE} && pytest --cov-report html:cov_report/integration --cov=src test/integration

test: code-qa test-unit ### perform all quality checks and tests, except for integration tests

upgrade-buildtools:
	pip install --upgrade pip
	pip install --upgrade setuptools
	pip install --upgrade wheel

upgrade-buildtools-latest:
	pip install --upgrade pip==24.0
	pip install --upgrade setuptools==69.1.1
	pip install --upgrade wheel==0.42.0

ci-upgrade-buildtools:
	make ci-upgrade-buildtools-$$(bin/pyversion)

ci-upgrade-buildtools-3.7: upgrade-buildtools

ci-upgrade-buildtools-3.8: upgrade-buildtools-latest

ci-upgrade-buildtools-3.9: upgrade-buildtools-latest

ci-upgrade-buildtools-3.10: upgrade-buildtools-latest

ci-upgrade-buildtools-3.11: upgrade-buildtools-latest

ci-install:
	make ci-upgrade-buildtools
	make install-dev-dependencies 
	make dev-install-pkg

ci-install-latest:
	make ci-upgrade-buildtools
	# latest regular dependencies
	make install-pkg
	# frozen development dependencies
	make install-dev-dependencies

ci-code-qa: exec-lint exec-typecheck ### perform code quality checks

## TODO: enable test-unit-coverage
ci-test-unit: test-unit 

ci-test-integration: test-integration

ci-dist: dist-clean clean-caches
	python -m build
	rm -fr build

freeze-dependencies: ## perform a full reinstall procedure and regenerate the 'requirements/requirements[.dev][.pyversion].txt' files
	make clean
	python3 -m venv ${VENV_DIR}
	@${VENV_ACTIVATE} && make execute_freeze_scripts

make execute_freeze_scripts: 
	make upgrade-buildtools
	# install with dependencies specified in pyproject.toml
	make install-pkg 
	pip uninstall waylay-sdk -y
	bin/freeze-dependencies
	# install with dependencies specified in pyproject.toml (development mode)
	make dev-install-pkg
	bin/freeze-dev-dependencies


pdoc: # TODO 
	rm -fr ./doc/api/
	pdoc -o ./doc/api \
		src/waylay/sdk/client.py \
		src/waylay/sdk/config.py \
		src/waylay/sdk/exceptions.py \
		src/waylay/sdk/auth.py \
		src/waylay/sdk/service.py 
