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
- A pipeline rules module holds the stage definitions and move rules. `refusal_reason` is the entry point for every manual move. The server calls it directly, and the UI reaches it through `can_transition` and `allowed_targets`, but the server is authoritative. Board cards carry `allowed_targets` in `data-allowed-stages`, which `board.js` reads to highlight columns.
- No application enters an in-progress stage while its job is closed or its candidate is archived. Manual moves are refused, and bulk restores skip those applications and report the count.
- A services module holds every in-app operation that changes data, and each operation writes its own stage-change records. `seed_demo` and Django Admin can bypass it, and admin edits to an application's stage skip the rules and write no history.
- Views are thin: they check permissions, call a service, and render a template or partial.
- `LoginRequiredMiddleware` makes every view require login. Manager-only actions are checked on the server and hidden in the UI.
- Roles are Django groups created by data migration, and manager-only permissions are defined on `User.Meta`. Accounts and group membership are managed only in Django Admin, apart from the `seed_demo` demo users.
- URLs are named, namespaced under `ats`, and use integer pks.
- Group permissions for new models are granted by data migration.
- `Candidate` lowercases its email in both `save` and `clean`, so case variants fail validation in forms and the admin.
- Application forms offer only `available_for` choices but validate against all records, so `create_application` gives the refusal message.
- Form classes use `DaisyFormMixin` for field styling.

## Development

- Layout: `config/` is the project, `ats/` is the app, `tailwind/source.css` is the Tailwind source, and `assets/` holds the generated CSS. Rules are in `ats/pipeline.py`, services in `ats/services.py`, forms in `ats/forms.py`, HTMX fragments in `ats/templates/ats/partials/`, and JS (including vendored HTMX and SortableJS) in `ats/static/ats/js/`.
- Run: `uv run python manage.py tailwind runserver`
- Reset to demo data: `uv run python manage.py seed_demo`. This deletes all domain data and non-superuser accounts; demo users' password is `demo-password`.
- Check: `uv run ruff check .`, `uv run ruff format .`, and `uv run pytest`
- Shared test fixtures are in `ats/tests/conftest.py`.

## Project documents

- PRD: `prd/applicant-tracking-system.md`
- Implementation plan: `plans/applicant-tracking-system.md`. Its decisions marked **Resolved** override the PRD.
- Prototypes: `prototypes/`. These are throwaway design references that must not be imported by the application, and the PRD overrides them.
