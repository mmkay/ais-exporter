# This makefile has been created to help developers perform common actions.
# Most rules assumes it is operating in a virtual environment where the python
# command links to a Python3 executable.

# Define the specific version of Python you want Make to use when creating
# a virtual environment.
PYTHON := python3

# Do not remove this block. It is used by the 'help' rule when
# constructing the help output.
# help:
# help: aisexporter Makefile help
# help:


# help: help                  - display this makefile's help information
.PHONY: help
help:
	@grep "^# help\:" Makefile | grep -v grep | sed 's/\# help\: //' | sed 's/\# help\://'


# help: venv                  - create a virtual environment for development
.PHONY: venv
venv:
	@rm -Rf venv
	@$(PYTHON) -m venv venv --prompt d1090exp
	@/bin/bash -c "source venv/bin/activate && pip install pip --upgrade && pip install -r requirements.dev.txt"
	@/bin/bash -c "source venv/bin/activate && pip install -e ."
	@echo "Enter virtual environment using:\n\n\t$ source venv/bin/activate\n"


# help: clean                 - clean all files using .gitignore rules
.PHONY: clean
clean:
	@git clean -X -f -d


# help: test                  - run tests
.PHONY: test
test:
	@python -m unittest discover -s tests


# help: test-verbose          - run tests [verbosely]
.PHONY: test-verbose
test-verbose:
	@python -m unittest discover -s tests -v


# help: coverage              - perform test coverage checks
.PHONY: coverage
coverage:
	@coverage erase
	@rm -f .coverage.unit
	@COVERAGE_FILE=.coverage.unit coverage run -m unittest discover -s tests -v
	@coverage combine
	@coverage report
	@coverage html
	@coverage xml


# help: style                 - perform code style formatting
.PHONY: style
style:
	@isort . --profile black
	@black src/aisexporter setup.py tests


# help: check-style           - perform code format compliance check
.PHONY: check-style
check-style:
	@isort . --check-only --profile black
	@black --check src/aisexporter setup.py tests


# help: check-types           - check type hint annotations
.PHONY: check-types
check-types:
	@cd src; mypy -p aisexporter --ignore-missing-imports


# help: check-lint            - run static analysis checks
.PHONY: check-lint
check-lint:
	@pylint --rcfile=.pylintrc aisexporter setup.py tests


# help: container             - build Docker container
.PHONY: container
container: dist
	@docker build -t clawsicus/aisexporter .


# help: checks                - perform all checks
.PHONY: checks
checks: check-style check-lint check-types test


# help: dist                  - create a wheel distribution package
.PHONY: dist
dist:
	@rm -rf dist
	@python setup.py bdist_wheel


# help: dist-upload           - upload a wheel distribution package
.PHONY: dist-upload
dist-upload: dist
	@twine upload dist/aisexporter-*-py3-none-any.whl


# Keep these lines at the end of the file to retain nice help
# output formatting.
# help:
