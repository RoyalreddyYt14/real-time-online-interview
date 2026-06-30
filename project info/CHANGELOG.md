## 2026-06-30

- Added email module, admin features, voice detection improvements, and project updates

# Changelog

## 2026-06-08

- Allow retake only when latest attempt completed; check completed_at instead of hr_done
- Increase MAX_ATTEMPTS to 5
- Added changelog automation script
- Fixed HR voice interview flow so stop/done/finish voice commands correctly advance to the next question.
- Added manual stop handling to prevent microphone restart issues after pressing the HR Stop button.
- Resolved a global `recognition` naming conflict between `static/js/main.js` and `templates/hr.html`.
- Updated HR user guidance text to explicitly mention `finish`, `done`, and `stop`.

## 2026-06-04

- Added recent update notes to `project info/create-skill/README.md`.
- Updated `project info/create-skill/project_components.md` to include:
  - Python runtime version `3.12.18`.
  - Dynamic results timestamp/ID fix.
  - Local timezone conversion for interview time.
  - Admin login fix via `ADMIN_PASSWORD_HASH` import.
  - End-to-end candidate workflow verification.
- Added `CHANGELOG.md` under `project info` for future project documentation.
