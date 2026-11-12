#!/usr/bin/env bash
# Misconception: sort -r puts the biggest count first.
set -euo pipefail

gzip -cdf access.log* |
  awk -F'"' '
    split($2, req, " ") != 3 { next }
    { split($3, after, " ") }
    after[1] ~ /^5[0-9][0-9]$/ { path = req[2]; sub(/[?].*/, "", path); failed[path]++ }
    END { for (path in failed) print failed[path], path }
  ' |
  sort -k1,1r -k2,2 |
  awk 'NR <= 3'
