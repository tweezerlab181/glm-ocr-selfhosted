#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

usage() {
  cat <<'USAGE'
Usage:
  scripts/gen_env.sh [--gateway-host HOST_OR_URL]
  scripts/gen_env.sh --client-credentials --gateway-host HOST_OR_URL [--force]

Options:
  --gateway-host HOST_OR_URL  Client gateway host (host:port) or full /ocr URL.
  --client-credentials        Generate client.credentials.env from existing .env.
  --force                     Overwrite existing client.credentials.env.
  -h, --help                  Show this help.
USAGE
}

gateway_host=""
client_credentials_only=0
force=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --gateway-host)
      if [[ $# -lt 2 || -z "$2" ]]; then
        echo "--gateway-host requires a non-empty value." >&2
        exit 2
      fi
      gateway_host="$2"
      shift 2
      ;;
    --client-credentials)
      client_credentials_only=1
      shift
      ;;
    --force)
      force=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

extract_api_key() {
  sed -n 's/^API_KEY=//p' .env | head -n 1
}

write_client_credentials() {
  local key="$1"
  local host="$2"
  local dest="client.credentials.env"

  if [[ -z "$host" ]]; then
    echo "--gateway-host is required to write client.credentials.env." >&2
    exit 2
  fi
  if [[ -f "$dest" && "$force" -ne 1 ]]; then
    echo "client.credentials.env already exists — refusing to overwrite. Use --force." >&2
    exit 1
  fi

  umask 077
  {
    if [[ "$host" == http://* || "$host" == https://* ]]; then
      printf 'OCR_URL=%s\n' "$host"
    else
      printf 'OCR_HOST=%s\n' "$host"
    fi
    printf 'OCR_API_KEY=%s\n' "$key"
  } > "$dest"
  chmod 600 "$dest"
  echo "Wrote client.credentials.env (chmod 600). Copy it to ~/.config/glm-ocr/credentials.env on client machines."
}

if [[ "$client_credentials_only" -eq 1 ]]; then
  if [[ ! -f .env ]]; then
    echo ".env not found — run scripts/gen_env.sh first or create server .env." >&2
    exit 1
  fi
  KEY="$(extract_api_key)"
  if [[ -z "$KEY" ]]; then
    echo ".env does not contain API_KEY." >&2
    exit 1
  fi
  write_client_credentials "$KEY" "$gateway_host"
  exit 0
fi

if [[ -f .env ]]; then
  echo ".env already exists — refusing to overwrite." >&2
  exit 1
fi
KEY="$(openssl rand -hex 32)"
sed "s|^API_KEY=.*|API_KEY=${KEY}|" .env.example > .env
chmod 600 .env
echo "Wrote .env with a fresh API key (chmod 600). Keep it secret."

if [[ -n "$gateway_host" ]]; then
  write_client_credentials "$KEY" "$gateway_host"
fi
