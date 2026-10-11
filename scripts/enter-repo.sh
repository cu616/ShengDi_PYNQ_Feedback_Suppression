#!/usr/bin/env bash
# Source this file to change the current Git Bash directory.
_shengdi_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$_shengdi_root" || return 1
unset _shengdi_root
pwd
git rev-parse --show-toplevel
git remote -v
git status --short --branch
