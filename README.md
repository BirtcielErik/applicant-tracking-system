# Applicant Tracking System

An internal, staff-only Django application for hiring teams to manage job openings, candidates, and applications through the hiring process.

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py tailwind build
```

The first Tailwind build downloads the Tailwind CLI, which includes DaisyUI. `migrate` creates the Recruiter and Hiring Manager groups and their permissions.

## Running the app

```sh
uv run python manage.py tailwind runserver
```

This starts Django and rebuilds the CSS when templates change. The app is at <http://127.0.0.1:8000/>.

## Accounts and roles

There is no signup page. Sign in to <http://127.0.0.1:8000/admin/> as the superuser to create staff accounts, then add each one to the Recruiter group, the Hiring Manager group, or both.

## Tests and linting

```sh
uv run pytest
uv run ruff check .
uv run ruff format .
```
