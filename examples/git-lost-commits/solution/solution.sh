#!/usr/bin/env bash
set -euo pipefail

# Stage 1. main's reflog lists its moves newest first; the line after the first reset is where main
# was before it. awk reads every line, so no SIGPIPE under pipefail.
n=$(git reflog show --format='%gs' main | awk '/^reset: moving to/ && !line { line = NR } END { print line }')
git branch rescue "main@{$n}"

# Stage 2. The shared base is where the reset left main; replay what came after it, oldest first.
base=$(git merge-base main rescue)
git cherry-pick "$base..rescue"
