Git hooks for changelog automation

Files in this folder:

- `post-commit` - POSIX shell script to append commit CHANGELOG lines or subject to `project info/CHANGELOG.md`.
- `post-commit.bat` - Windows batch equivalent for Git on Windows.
- `install-hooks.sh` - Installs hooks into `.git/hooks` (POSIX).
- `install-hooks.bat` - Installs hooks into `.git\hooks` (Windows).

Usage:

- From repo root (POSIX):
  ./git-hooks/install-hooks.sh

- From repo root (Windows):
  git-hooks\install-hooks.bat

Notes:

- The hook will append entries to `project info/CHANGELOG.md` but will not auto-commit the changelog.
- Prefer including `CHANGELOG: ` lines in commit messages for precise entries, e.g.:

  git commit -m "Fix bug X\n\nCHANGELOG: Fix HR voice stop command"

- The script uses `python3` or `python` on PATH to run `update_changelog.py`.
