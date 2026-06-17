#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f .env ]]; then
  echo ".env already exists — refusing to overwrite." >&2
  exit 1
fi
KEY="$(openssl rand -hex 32)"
sed "s|^API_KEY=.*|API_KEY=${KEY}|" .env.example > .env
chmod 600 .env
echo "Wrote .env with a fresh API key (chmod 600). Keep it secret."
