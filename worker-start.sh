#!/usr/bin/env bash
# Worker startup script with proper PYTHONPATH configuration
# This script sets the Python import path to include the project root
# allowing relative imports to work correctly when the worker is started
# from the project root directory. Uses uv run to activate project environment.

export PYTHONPATH="${PYTHONPATH}:$(pwd)"
uv run python -m worker.main
