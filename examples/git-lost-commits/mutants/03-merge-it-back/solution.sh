#!/usr/bin/env bash
# Misconception: merging rescue back in is the same as putting the commits back.
set -euo pipefail

n=$(git reflog show --format='%gs' main | awk '/^reset: moving to/ && !line { line = NR } END { print line }')
git branch rescue "main@{$n}"
git merge -q --no-edit rescue
