# Applicant Tracking System

An internal, staff-only Django web application for hiring teams to manage job openings, candidates, and applications through the hiring process.

## Technology stack

- Python, Django, and SQLite
- uv for package management
- Tailwind CSS with DaisyUI via django-tailwind-cli
- HTMX for partial page updates
- SortableJS for drag-and-drop, saved as a project static file rather than loaded from a CDN
- Ruff for linting and formatting
- pytest with pytest-django for tests

## Architecture

- A single Django app holds the whole domain.
- A custom User model is defined from the start.
- A pipeline rules module holds the stage definitions, the transition rules, `refusal_reason` (the single source of each rule and its message), and `can_transition`, which wraps it. The UI and server share this check, and the server is authoritative.
- A services module holds every operation that changes data, and each operation writes its own stage-change records.
- Views are thin: they check login and permissions, call a service, and render a template or partial.
- Every view requires login. Manager-only actions are checked on the server and hidden in the UI.
- Roles are Django groups created by data migration. Accounts and group membership are managed only in Django Admin.
- `LoginRequiredMiddleware` protects every view by default.
- URLs are named, namespaced under `ats`, and use integer pks.
- Group permissions for new models are granted by data migration.

## Development

- Layout: `config/` is the project, `ats/` is the app, and `tailwind/source.css` is the Tailwind source. Rules are in `ats/pipeline.py`, services in `ats/services.py`, HTMX fragments in `ats/templates/ats/partials/`, and JS (including vendored HTMX and SortableJS) in `ats/static/ats/js/`.
- Run: `uv run python manage.py tailwind runserver`
- Reset to demo data: `uv run python manage.py seed_demo`. This deletes everything except superusers; demo users' password is `demo-password`.
- Check: `uv run ruff check .`, `uv run ruff format .`, and `uv run pytest`
- Shared test fixtures are in `ats/tests/conftest.py`.

## Project documents

- PRD: `prd/applicant-tracking-system.md`
- Implementation plan: `plans/applicant-tracking-system.md`. Its decisions marked **Resolved** override the PRD.
- Prototypes: `prototypes/`. These are throwaway design references that must not be imported by the application, and the PRD overrides them.
