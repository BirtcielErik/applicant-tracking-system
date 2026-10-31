This is a new Django application named Applicant Tracking System. This application is meant to be used by hiring teams to manage job openings, track candidates, and move and track applications through the hiring process from start to finish.

The application has the following requirements:

    1) The system will only be used by internal employees - job candidates will never log in to the system.
    2) Staff need to keep track of candidates and their basic information, as well as lead source (company website, job board, referral, other outside source).
    3) Staff need to be able to create and edit job openings - a job opening can either by open or closed.
    4) Staff need to record when a candidate applies for a job opening - candidates can apply for several different jobs, but may only apply to each specific job one time.
    5) Applications must move through a defined process with the following stages: Applied, Screening, Interview, Final Review, Offer, Hired, Rejected, and Withdrawn.
    6) Staff need an easy way to see where each applicant is in the hiring process and be able to move them between stages without reloading the entire page.
    7) The system needs to keep track of the relevant skills associated with each job opening - each skill may apply to multiple different job openings.
    8) The system needs a way to manage candidate records over time.
    9) The system should have defined rules for what happens once a job opening is closed.

The application must use the following technology stack:

    - Python
    - Django
    - SQLite
    - uv
    - Tailwind CSS with DaisyUI using `django-tailwind-cli`
    - HTMX
    - Ruff
    - pytest