#!/usr/bin/env bash
# Misconception: main can simply be reset to rescue.
set -euo pipefail

n=$(git reflog show --format='%gs' main | awk '/^reset: moving to/ && !line { line = NR } END { print line }')
git branch rescue "main@{$n}"
git reset -q --hard rescue
