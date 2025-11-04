# -- Variables -----------------------------------------------------------------

PACKAGE := pyfocas

# -- Rules ---------------------------------------------------------------------

.PHONY: check
check:
	mypy $(PACKAGE)

.PHONY: setup
setup:
	uv venv --allow-existing
	uv sync --all-extras
