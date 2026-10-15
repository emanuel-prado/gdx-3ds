#!/usr/bin/env bash
# Repository-local routing only; never changes remote repositories or global config.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
origin="$(git remote get-url origin)"
case "$origin" in
    git@github.com:emanuel-prado/gdx-3ds.git|https://github.com/emanuel-prado/gdx-3ds.git|https://github.com/emanuel-prado/gdx-3ds) ;;
    *) echo "Refusing setup: origin is not emanuel-prado/gdx-3ds: $origin" >&2; exit 1 ;;
esac
git config --local remote.pushDefault origin
git config --local push.default simple
git config --local push.autoSetupRemote true
git config --local remote.origin.gh-resolved base
if git remote get-url upstream >/dev/null 2>&1; then
    git config --local --replace-all remote.upstream.pushurl DISABLED
    if git config --local --get-all remote.upstream.gh-resolved >/dev/null; then
        git config --local --unset-all remote.upstream.gh-resolved
    fi
fi
echo "Push default and gh default: $origin"
echo "Upstream remains fetchable; its push URL is disabled."
