#!/usr/bin/env bash
# Is a deployed site discoverable? The files crawlers and people look for must
# exist and must not be the SPA shell, which answers 200 text/html for every
# missing path. Run by .github/workflows/deploy.yml after every publish.
#
#   scripts/check-discoverable.sh https://example.com
set -u
base="${1%/}"
fail=0

check() {
  local path="$1" want="$2" out code type
  out=$(curl -sS -L -o /dev/null -w '%{http_code} %{content_type}' --retry 3 --retry-delay 5 "$base$path") || out="000 none"
  code="${out%% *}"
  type="${out#* }"
  if [ "$code" != "200" ] || [[ "$type" == text/html* ]] || [[ "$type" != *"$want"* ]]; then
    echo "FAIL $path -> $code $type (want $want)"
    fail=1
  else
    echo "ok   $path -> $type"
  fi
}

check /sitemap.xml xml
check /robots.txt text/plain
check /llms.txt text/plain
check /humans.txt text/plain
check /site.webmanifest json

if ! curl -sS -L "$base/robots.txt" | grep -qi '^sitemap:'; then
  echo "FAIL /robots.txt has no Sitemap: line"
  fail=1
fi

exit "$fail"
