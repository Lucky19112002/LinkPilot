#!/usr/bin/env bash
set -euo pipefail

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if git ls-files | grep -E '^(\.venv/|logs/|dist/|coverage\.xml$|\.coverage$|\.pytest_cache/)' >/dev/null; then
    echo "Release audit failed: generated artifacts are tracked"
    exit 1
  fi
else
  for path in .venv logs dist coverage.xml .coverage .pytest_cache; do
    if [ -e "$path" ]; then
      echo "Release audit failed: remove $path before publishing source"
      exit 1
    fi
  done
fi

FILES=$(git ls-files 2>/dev/null || find . -path ./.git -prune -o -path ./build/linkpilot -prune -o -path ./.venv -prune -o -path ./dist -prune -o -type f -print)

if echo "$FILES" | grep -E '(^|/)(\.env|.*\.(key|pem))$' >/dev/null; then
  echo "Release audit failed: secret-like tracked file found"
  exit 1
fi

if echo "$FILES" | grep -vE '^(tests/|test_smoke.py$|build/security_audit.sh$)' | xargs grep -InE '(BEGIN .*PRIVATE KEY|github_pat_|ghp_|sk-[A-Za-z0-9]{20,})'; then
  echo "Release audit failed: secret-like text found"
  exit 1
fi

echo "Release audit passed"
