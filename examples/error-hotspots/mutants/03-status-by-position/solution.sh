#!/usr/bin/env bash
# Misconception: the status is always the ninth field.
set -euo pipefail

gzip -cdf access.log* |
  awk '$9 ~ /^5[0-9][0-9]$/ { path = $7; sub(/[?].*/, "", path); print path }' |
  sort | uniq -c |
  sort -k1,1nr -k2,2 |
  awk 'NR <= 3 { print $1, $2 }'
