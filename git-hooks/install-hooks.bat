@echo off
REM Install hooks into .git\hooks\
for /f "delims=" %%R in ('git rev-parse --show-toplevel 2^>nul') do set REPO_ROOT=%%R
if not defined REPO_ROOT (
  echo No git repository found. Run this from the repo root.
  exit /b 1
)
set HOOK_DIR=%REPO_ROOT%\.git\hooks
if not exist "%HOOK_DIR%" mkdir "%HOOK_DIR%"
copy /Y "git-hooks\post-commit" "%HOOK_DIR%\post-commit" >nul 2>&1 || copy /Y "git-hooks\post-commit.bat" "%HOOK_DIR%\post-commit.bat" >nul 2>&1
echo Hooks copied to %HOOK_DIR%
echo Note: Review the CHANGELOG.md after commits; hooks do not auto-commit changes.
