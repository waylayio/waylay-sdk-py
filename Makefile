printMsg=printf "\033[36m\033[1m%-15s\033[0m\033[36m %-30s\033[0m\n"

.PHONY: help
## use triple hashes ### to indicate main build targets
help:
	@awk 'BEGIN {FS = ":[^#]*? ### "} /^[a-zA-Z_-]+:[^#]* ### / {printf "\033[1m\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@awk 'BEGIN {FS = ":[^#]*? ## "} /^[a-zA-Z_-]+:[^#]* ## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
.DEFAULT_GOAL := help

install-hooks:
	bin/install-hooks

install-dependencies:
	pip install -r requirements/requirements.$$(bin/pyversion).txt

install-dev-dependencies:
# need to install the `waylay` first, because the `waylay_<SERVICE>` packages require it
	pip install -e . --no-deps
	pip install -r requirements/requirements.$$(bin/pyversion).txt
	pip install -r requirements/requirements.dev.$$(bin/pyversion).txt

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
	@pip freeze | grep '^-e' | sed -e "s/^.*#egg=\(.*\)/\1/" | xargs -L 1 pip uninstall -y
	@${printMsg} "uninstall-pkg" "Development packages uninstalled"

full-clean:
	make uninstall-pkg
	make uninstall-dependencies
	make clean-caches
	make clean-eggs

dev-install-pkg:  ## Install waylay-py with development dependency constraints as specified in the package.
	pip install -e ".[dev]"

dev-install:  ### Install a development environment with frozen dependencies from 'requirements/requirements.[dev.].txt'
	make ci-upgrade-buildtools
	make install-dev-dependencies
	make dev-install-pkg
	make install-hooks

install-pkg:  ### Install waylay-py with dependency constraints as specified in the package. (e.g. for notebook tests)
	pip install .

install:  ### install waylay with frozen dependencies
	make install-dependencies
	make install-pkg

dev-reinstall: full-clean  dev-install  ### Remove all dependences and reinstall with frozen dependencies

lint:
	@pylint -E src test/*/*.py
	@${printMsg} lint OK

lint-minimal:
	@pylint -E src test/*/*.py --confidence=INFERENCE
	@${printMsg} lint-minimal OK

codestyle:
	@pycodestyle src test/*/*.py
	@${printMsg} codestyle OK

typecheck:
	@mypy -p waylay 
	@mypy test/*/*.py
	@${printMsg} typecheck OK

docstyle:
	@pydocstyle src test/*/*.py
	@${printMsg} docstyle OK

code-qa: codestyle docstyle lint typecheck ### perform code quality checks

test-integration-cleanup-models:
	pytest test/integration -m cleanup --log-cli-level=INFO

pre-commit: codestyle

format: 
	autopep8 . && docformatter --config setup.cfg .

test-unit:
	@pytest test/unit -m "not (sklearn or pytorch or tensorflow or xgboost or cleanup)"

test-unit-coverage:
	@pytest --cov-report term-missing:skip-covered --cov=src --cov-fail-under=90 test/unit

test-unit-coverage-report: ### generate html coverage report for the unit tests
	@pytest --cov-report html:cov_report --cov=src --cov-fail-under=90 test/unit

test-coverage-report: ### generate html coverage report for the unit and integration tests
	@pytest --cov-report html:cov_report_all --cov=src --cov-fail-under=90 test/unit test/integration -m "not byoml_integration"

test-integration:
	@pytest test/integration -m "not byoml_integration"

test-integration-coverage-report: ### generate html coverage report for the integration tests
	@pytest --cov-report html:cov_report/integration --cov=src test/integration

test: code-qa test-unit ### perform all quality checks and tests, except for integration tests

upgrade-buildtools:
	pip install --upgrade pip
	pip install --upgrade setuptools
	pip install --upgrade wheel

upgrade-buildtools-latest:
	pip install --upgrade pip==23.2.1
	pip install --upgrade setuptools==68.2.2
	pip install --upgrade wheel==0.41.2

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

ci-code-qa: code-qa

## TODO: enable test-unit-coverage
ci-test-unit: test-unit 

ci-test-integration: test-integration

ci-dist: dist-clean clean-caches
	python -m build
	rm -fr build

freeze-dependencies: ## perform a full reinstall procedure and regenerate the 'requirements/requirements[.dev][.pyversion].txt' files
	make full-clean
	@if [ "`pip freeze | wc -l | xargs`" != "0" ]; then \
		echo "`pip freeze | wc -l | xargs` packages still installed, please use a clean python environment"; \
		exit 1; \
	fi
	make upgrade-buildtools
	# install with dependencies specified in setup.py
	make install-pkg 
	pip uninstall waylay -y
	bin/freeze-dependencies
	# install with dependencies specified in setup.py (development mode)
	make dev-install-pkg
	bin/freeze-dev-dependencies


pdoc: # TODO 
	rm -fr ./doc/api/
	pdoc -o ./doc/api \
		src/waylay/client.py \
		src/waylay/config.py \
		src/waylay/exceptions.py \
		src/waylay/auth.py \
		src/waylay/service/base.py 
