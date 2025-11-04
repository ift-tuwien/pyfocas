# -- Variables -----------------------------------------------------------------

PACKAGE := pyfocas

# -- Rules ---------------------------------------------------------------------

.PHONY: check
check:
	uv run mypy $(PACKAGE)

.PHONY: setup
setup:
	uv venv --allow-existing
	uv sync --all-extras

.PHONY: test
test:
	uv run pytest
