#!/usr/bin/env bash
set -euo pipefail

pip install --user uv
cd apps/core && uv sync && cd ../..

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example - fill in the empty values."
fi
