#!/usr/bin/env bash
set -e

ruff format src tests scripts evaluation
ruff check --fix src tests scripts evaluation
echo "Formatting complete."
