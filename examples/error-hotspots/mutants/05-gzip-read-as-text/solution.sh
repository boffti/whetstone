#!/usr/bin/env bash
# Misconception: cat reads the gzipped logs as text too.
set -euo pipefail

cat access.log* |
  awk -F'"' '
    split($2, req, " ") != 3 { next }
    { split($3, after, " ") }
    after[1] ~ /^5[0-9][0-9]$/ { path = req[2]; sub(/[?].*/, "", path); print path }
  ' |
  sort | uniq -c |
  sort -k1,1nr -k2,2 |
  awk 'NR <= 3 { print $1, $2 }'
