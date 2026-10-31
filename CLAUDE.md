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
- A pipeline rules module holds the stage definitions, the transition map, and the `can_transition` check. The UI and server share this check, and the server is authoritative.
- A services module holds every operation that changes data, and each operation writes its own stage-change records.
- Views are thin: they check login and permissions, call a service, and render a template or partial.
- Every view requires login. Manager-only actions are checked on the server and hidden in the UI.
- Roles are Django groups created by data migration. Accounts and group membership are managed only in Django Admin.

## Project documents

- PRD: `prd/applicant-tracking-system.md`
- Implementation plan: `plans/applicant-tracking-system.md`. Its decisions marked **Resolved** override the PRD.
- Prototypes: `prototypes/`. These are throwaway design references that must not be imported by the application, and the PRD overrides them.
