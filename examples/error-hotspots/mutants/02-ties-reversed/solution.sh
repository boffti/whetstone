#!/usr/bin/env bash
# Misconception: sort -rn breaks a tie by path, A to Z.
set -euo pipefail

gzip -cdf access.log* |
  awk -F'"' '
    split($2, req, " ") != 3 { next }
    { split($3, after, " ") }
    after[1] ~ /^5[0-9][0-9]$/ { path = req[2]; sub(/[?].*/, "", path); print path }
  ' |
  sort | uniq -c |
  sort -rn |
  awk 'NR <= 3 { print $1, $2 }'
