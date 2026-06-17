#!/usr/bin/env bash
set -euo pipefail
HOST="${1:-127.0.0.1:8080}"
source .env
echo "== health =="
curl --noproxy '*' -fsS "http://${HOST}/health"; echo
for f in tests/fixtures/sample.png tests/fixtures/sample.pdf; do
  echo "== ${f} =="
  out="$(curl --noproxy '*' -fsS -H "X-API-Key: ${API_KEY}" -F "file=@${f}" "http://${HOST}/ocr")"
  echo "$out" | python3 -c 'import sys,json; b=json.load(sys.stdin); assert b["markdown"].strip(), "empty markdown"; print("ok:", b["pages"], "pages,", b["elapsed_sec"], "s")'
done
echo "VERIFY OK"
