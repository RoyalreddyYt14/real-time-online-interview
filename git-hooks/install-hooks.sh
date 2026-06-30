#!/bin/sh
# Install git hooks from git-hooks/ into .git/hooks/
set -e
ROOT=$(git rev-parse --show-toplevel 2>/dev/null || true)
if [ -z "$ROOT" ]; then
  echo "No git repository found in this folder. Run inside the repository root."
  exit 1
fi

HOOK_DIR="$ROOT/.git/hooks"
mkdir -p "$HOOK_DIR"

cp -v "$(pwd)/git-hooks/post-commit" "$HOOK_DIR/post-commit" || true
cp -v "$(pwd)/git-hooks/post-commit.bat" "$HOOK_DIR/post-commit.bat" || true

chmod +x "$HOOK_DIR/post-commit" || true

echo "Installed hooks to $HOOK_DIR"

echo "Note: The hook updates CHANGELOG.md but does not auto-commit it. Review and commit the file if desired."
