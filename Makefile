# -- Rules ---------------------------------------------------------------------

.PHONY: setup
setup:
	uv venv --allow-existing
	uv sync --all-extras
