#!/usr/bin/env bash
# Misconception: a three-digit number that starts with 5 is the status.
set -euo pipefail

gzip -cdf access.log* |
  grep ' 5[0-9][0-9] ' |
  awk -F'"' 'split($2, req, " ") == 3 { path = req[2]; sub(/[?].*/, "", path); print path }' |
  sort | uniq -c |
  sort -k1,1nr -k2,2 |
  awk 'NR <= 3 { print $1, $2 }'
