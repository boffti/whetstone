#!/usr/bin/env bash
set -euo pipefail

# Stage 2 reads every access log: gzip -cdf decompresses the .gz ones and passes plain text through,
# and the glob lists only the files that are there.
gzip -cdf access.log* |
  # Split on quotes, not spaces: the request is field 2 and the status starts field 3, however many
  # addresses come before. Only a method, a path and a protocol is a request worth counting.
  awk -F'"' '
    split($2, req, " ") != 3 { next }
    { split($3, after, " ") }
    after[1] ~ /^5[0-9][0-9]$/ { path = req[2]; sub(/[?].*/, "", path); print path }
  ' |
  sort | uniq -c |
  # Count as a number, largest first; then path, A to Z. A bare -r would reverse the tie-break too.
  sort -k1,1nr -k2,2 |
  # awk reads all its input, unlike head, so nothing upstream dies of SIGPIPE under pipefail.
  awk 'NR <= 3 { print $1, $2 }'
