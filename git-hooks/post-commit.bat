@echo off
REM Windows Git post-commit hook: appends commit subject to project info/CHANGELOG.md
SETLOCAL EnableExtensions EnableDelayedExpansion

:: Find repo root
for /f "delims=" %%R in ('git rev-parse --show-toplevel 2^>nul') do set REPO_ROOT=%%R
if not defined REPO_ROOT (
  exit /b 0
)
pushd "%REPO_ROOT%"

:: Get latest commit subject
for /f "delims=" %%S in ('git log -1 --pretty=%%s 2^>nul') do set COMMIT_SUBJECT=%%S
if not defined COMMIT_SUBJECT (
  popd
  exit /b 0
)

:: Prefer python3 then python
where python3 >nul 2>nul
if %errorlevel%==0 (
  set PY=python3
) else (
  where python >nul 2>nul && set PY=python || set PY=
)
if "%PY%"=="" (
  echo WARNING: no Python available; skipping changelog update.
  popd
  exit /b 0
)

:: Update changelog (do not fail the commit)
%PY% update_changelog.py "%COMMIT_SUBJECT%" || echo Changelog update failed

npopd
exit /b 0
