#!/usr/bin/env bash
set -euo pipefail

interval="${1:-10}"
if ! [[ "$interval" =~ ^[1-9][0-9]*$ ]]; then
  echo "Usage: $0 [refresh-seconds]" >&2
  exit 2
fi

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command="cd \"$repo_dir\" && docker compose exec -T postgres psql -U portal -d portal -c \"WITH pdf_urls AS (SELECT DISTINCT normalized->>'artifact_url' AS url FROM listings WHERE lower(split_part(normalized->>'artifact_url', '?', 1)) LIKE '%.pdf') SELECT count(*) FILTER (WHERE a.storage_key IS NOT NULL) AS stored, count(*) FILTER (WHERE a.error IS NOT NULL AND a.storage_key IS NULL) AS failed, count(*) FILTER (WHERE a.storage_key IS NULL AND a.error IS NULL) AS pending FROM pdf_urls p LEFT JOIN pdf_artifacts a ON a.url = p.url;\""

exec watch -n "$interval" "$command"
