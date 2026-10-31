# Plan: Applicant Tracking System

> Source PRD: [prd/applicant-tracking-system.md](../prd/applicant-tracking-system.md)

## Architectural decisions

Durable decisions that apply across all phases. Where this section resolves a contradiction or gap in the PRD (marked **Resolved**), this plan is authoritative.

- **Stack**: Python, Django, SQLite, uv, Tailwind CSS with DaisyUI via django-tailwind-cli, HTMX, Ruff, pytest with pytest-django. SortableJS is saved as a static file in the project, not loaded from a CDN.
- **Owning app**: one Django app, `ats`, holds the whole domain, including the custom User model. The project package is `config`.
- **Internal structure**:
  - A pipeline rules module holds the stage definitions, the transition map, and `can_transition(user, application, target)`, used by both the UI and the server.
  - A services module holds every operation that changes data and writes its stage changes.
  - Views are thin: they check login and permissions, call a service, and render a template or partial.
- **URLs**: named, namespaced under `ats`, and using integer pks (no slugs).

  | Path | Purpose |
  | --- | --- |
  | `/login/`, `/logout/` | Authentication |
  | `/` | Jobs list (home) |
  | `/jobs/new/`, `/jobs/<pk>/edit/` | Job create and edit |
  | `/jobs/<pk>/` | Job detail with pipeline board |
  | `/jobs/<pk>/close/`, `/jobs/<pk>/reopen/` | Close and reopen a job |
  | `/jobs/<pk>/applications/new/` | Add applicant from the board |
  | `/applications/<pk>/move/` | HTMX move endpoint; always returns the full board |
  | `/candidates/`, `/candidates/new/` | Candidates list and create |
  | `/candidates/<pk>/`, `/candidates/<pk>/edit/` | Candidate detail and edit |
  | `/candidates/<pk>/archive/`, `/candidates/<pk>/unarchive/` | Archive and unarchive |
  | `/candidates/<pk>/notes/` | HTMX add note |
  | `/candidates/<pk>/applications/new/` | Apply to job from the candidate page |
  | `/skills/` | Skill management (manager-only rename and delete) |
  | `/admin/` | Django Admin |

- **Models**:
  - `User`: custom, subclasses `AbstractUser`, no extra fields initially.
  - `Candidate`: unique lowercase email, lead source choices, archived flag.
  - `JobOpening`: status Open/Closed, FK to `User` (created by), closed-at, M2M to `Skill`.
  - `Skill`: name, unique case-insensitively.
  - `Application`: FK to `Candidate`, FK to `JobOpening`, current stage, application date, created timestamp. Database unique constraint on (candidate, job opening).
  - `StageChange`: FK to `Application`, from-stage (blank for the initial record), to-stage, FK to `User`, timestamp, reason.
  - `CandidateNote`: FK to `Candidate`, FK to `User` (author), body, timestamp, optional FK to `Application`.
- **Stage change reasons**: normal move, job closed, candidate archived, job reopened, candidate unarchived, application reopened, and application created. **Resolved**: "application created" is added because no PRD reason fits the required initial record.
- **Stages**: Applied, Screening, Interview, Final Review (**active**), Offer, Hired, and Rejected, Withdrawn (**exit**). The **in-progress** stages are the active stages plus Offer and Hired.
- **Transition rules**:

  | From | To | Who |
  | --- | --- | --- |
  | Active | Any other active stage | Everyone |
  | Final Review | Offer | Manager |
  | Offer | Hired | Manager |
  | Offer | Any active stage | Manager |
  | Active or Offer | Rejected or Withdrawn | Everyone |
  | Hired | Any other stage, including Offer | Manager |
  | Rejected or Withdrawn | The stage held immediately before the exit | Manager |

  - Moving to the current stage is not a move, and any pair not listed is refused.
  - **Resolved**: Hired → Offer is allowed for managers, as the way to correct a mistaken hire. "Only from Final Review" governs forward progress into Offer.
  - **Resolved**: a reopen is a restore, so it is exempt from "Offer only from Final Review" and "Hired only from Offer". An application that exited from Offer or Hired reopens to that stage.
  - The stage to reopen to is derived from the most recent stage change into Rejected or Withdrawn.
- **In-progress guard (Resolved)**: no application may enter an in-progress stage while its job is closed or its candidate is archived.
  - Manual moves and reopens that would break this are refused with an explanatory message.
  - Bulk restores skip those applications and report how many were skipped.
  - Moves into Rejected or Withdrawn stay allowed.
- **Authorization**:
  - Every view requires login. There is no signup page; accounts and group membership are managed only in Django Admin.
  - The Recruiter and Hiring Manager groups are created by data migration. Hiring Manager holds every Recruiter permission, and a user in both groups has the union.
  - All manager-only custom permissions (make offer, confirm hire, change an offer or hire, reopen application, close/reopen job, archive candidate, rename/delete skill) exist from Phase 1.
  - Recruiter-level views check standard model permissions, so an account with no role cannot change data. Each phase that adds a model grants its permissions to the groups by data migration.
  - Manager-only actions are checked on the server and hidden in the UI.
- **Pipeline move contract**: a drop sends an HTMX POST with the target stage. The server runs the rule check and, if allowed, saves the stage and writes the stage change. The response is always the full re-rendered board, with an error toast added for a blocked move.
- **Testing**: pytest with shared fixtures in a conftest plus small helpers, no factory library, no browser tests. Most tests target rules and services, with view tests using Django's test client. Ruff lints and formats the codebase.
- **Demo data**: `seed_demo` is introduced in Phase 2 and extended by each later phase that adds data worth demonstrating. **Resolved**: it resets the application, deleting all data and non-superuser accounts before loading the demo set, so running it repeatedly must not fail or create duplicates.

---

## Phase 1: Authenticated shell

**User stories**: 1, 2, 3, 4, 5, 6

### What to build

The project foundation and the first path through it. Stand up the stack and the `ats` app with the custom User model in its first migration. Create both groups and all manager-only permissions by data migration. A staff member created in the admin can log in on a DaisyUI-styled page, reach a protected placeholder home page in a shared layout, and log out. Anonymous visitors are redirected to login.

### Acceptance criteria

- [ ] The project runs through uv, and the Tailwind/DaisyUI build works through django-tailwind-cli
- [ ] Ruff and pytest are configured, and both pass
- [ ] The custom User model is `AUTH_USER_MODEL` from the first migration
- [ ] A fresh database has the Recruiter and Hiring Manager groups and all manager-only permissions, with no manual setup
- [ ] Hiring Manager holds every Recruiter permission, and a dual-role user has the combined permissions
- [ ] An admin can create a user and assign roles in Django Admin, and there is no public signup page
- [ ] Login, logout, and the anonymous redirect work, and the login page uses DaisyUI

---

## Phase 2: Tracer bullet — board with one kind of move

**User stories**: 7, 55, 56, 58, 61, 62, 72

### What to build

The thinnest end-to-end path through the pipeline. Add `Candidate`, `JobOpening`, `Application`, and `StageChange`, all editable in Django Admin. Start the rules module with active-to-active moves, and the services module with the move operation. The job detail page shows the board with all eight columns and a count on each. Dragging a card between active stages posts to the move endpoint, which saves the stage, records the stage change, and returns the re-rendered board without a page reload. `seed_demo` creates users in each role plus jobs, candidates, and applications across the stages.

### Acceptance criteria

- [ ] The board shows Applied, Screening, Interview, Final Review, Offer, Hired, Rejected, and Withdrawn columns, each with a count
- [ ] Dragging a card between active stages, forward or backward by any distance, updates the database without a full page reload
- [ ] The response is the full board, so counts and colleagues' changes are current after every move
- [ ] Each move records from-stage, to-stage, user, timestamp, and the "normal move" reason
- [ ] The unique constraint on (candidate, job opening) exists at database level
- [ ] SortableJS is served from project static files
- [ ] `seed_demo` populates a working demo and can be run more than once
- [ ] The move endpoint and board require login
- [ ] Service and view tests cover the behavior above

---

## Phase 3: Server-enforced transition rules

**User stories**: 60, 63, 64, 65, 66, 67, 68, 69, 70, 71, 73, 74

### What to build

The complete transition table and in-progress guard in the rules module, enforced by the move service and the existing move endpoint. A refused drop returns the board, so the card snaps back, and adds a toast explaining why. Dragging a Rejected or Withdrawn card into its previous stage performs a reopen. This phase is verified by logging in as each role and attempting the same drags.

### Acceptance criteria

- [ ] Every rule in the transition table is enforced by `can_transition` and tested for Recruiter, Hiring Manager, and dual-role users
- [ ] Unlisted moves, such as Applied → Offer or Screening → Hired, are refused for every role
- [ ] Hired → Offer is allowed for managers and refused for recruiters
- [ ] A manager reopen returns the application to the stage held before the exit, including Offer or Hired, with the "application reopened" reason
- [ ] Rejected or Withdrawn cards cannot move anywhere except the previous stage, and only a manager can do it
- [ ] The in-progress guard refuses moves and reopens on a closed job or for an archived candidate, and still allows moves into Rejected or Withdrawn
- [ ] A blocked move leaves the stage unchanged, writes no stage change, returns the board, and shows a toast with the reason
- [ ] A hand-crafted POST cannot bypass any rule
- [ ] Moving to the current stage is not a move and records nothing

---

## Phase 4: Drag feedback and rich cards

**User stories**: 57, 59

### What to build

Make the board show the rules before a drop. Each card carries its allowed target stages, computed by the same `can_transition` check for the signed-in user, and columns are highlighted or faded while it is dragged. Cards gain the full set of details. No rules change in this phase. The README gains the manual drag-and-drop checklist.

### Acceptance criteria

- [ ] During a drag, allowed columns are highlighted and blocked columns faded, and both return to normal afterward
- [ ] The highlighted set for each card matches `can_transition` for the signed-in user's role
- [ ] Highlighting still works after the board is re-rendered by a move
- [ ] Each card shows candidate name, email, lead source and detail, application date, and time since last move
- [ ] The README contains a manual drag-and-drop checklist covering both roles
- [ ] View tests confirm the rendered allowed targets differ correctly by role

---

## Phase 5: Candidate management

**User stories**: 8, 9, 10, 11, 12, 13, 14

### What to build

In-app candidate records. Staff can list, search by name or email, create, and edit candidates, with the lead source choices and optional detail. Emails are stored in lowercase, and a duplicate is refused regardless of capitalization, with a link to the existing record. A minimal candidate detail page gives the links somewhere to land; Phase 9 fills it out.

### Acceptance criteria

- [ ] Staff can create and edit a candidate with first name, last name, email, optional phone, lead source, and optional detail
- [ ] Lead source is limited to Company Website, Job Board, Referral, and Other
- [ ] Emails are stored in lowercase through both forms and the admin
- [ ] A duplicate email is refused regardless of capitalization, and the error links to the existing candidate
- [ ] The list searches by name or email
- [ ] Form validation errors render, and an account with no role cannot create or edit
- [ ] Service and view tests cover the above

---

## Phase 6: Job management

**User stories**: 28, 29, 34, 35, 36

### What to build

In-app job openings. The placeholder home page becomes the jobs list: open jobs by default, a closed filter, and a count of active applicants per job. Staff can create and edit jobs, which link to their boards. Each job shows who created it and when it was closed. Status is changed only through the admin until Phase 10.

### Acceptance criteria

- [ ] Staff can create and edit a job with a title and optional department, location, and description
- [ ] A new job records the creating user and starts Open
- [ ] `/` lists open jobs by default, and a filter shows closed jobs
- [ ] Applicant counts include active stages only
- [ ] Each job displays its creator and, where set, its closed-at time
- [ ] The home page avoids a query per job for its counts
- [ ] Service and view tests cover the above

---

## Phase 7: Skills

**User stories**: 30, 31, 32, 33

### What to build

Add `Skill` and its relationship to jobs. The job form gets a skill picker with inline "add skill", so a missing skill never blocks an edit. Skill names are unique regardless of capitalization. Managers can rename and delete skills on a skill management page. Job pages show their skills, and `seed_demo` tags its jobs.

### Acceptance criteria

- [ ] Staff can tag a job with skills on create and edit
- [ ] A new skill can be added inline from the job form without losing the form's other input
- [ ] "Python" and "python" cannot both exist, and adding an existing name in another case reuses the existing skill
- [ ] The uniqueness rule is enforced at database level
- [ ] Rename and delete are refused on the server for recruiters and hidden from them
- [ ] Managers can rename and delete skills, and the change is reflected on affected jobs
- [ ] Service and view tests cover the above

---

## Phase 8: Creating applications

**User stories**: 46, 47, 48, 49, 50, 51, 52, 53, 54

### What to build

One shared service creates applications and two entry points use it: "Add applicant" on the board, with a searchable candidate picker, and "Apply to job" on the candidate page, with an open-job picker. New applications start in Applied with an initial stage change. A candidate re-applying to a job they exited is handled by reopening the existing application, and the UI says so instead of creating a second one.

### Acceptance criteria

- [ ] The service refuses closed jobs, archived candidates, duplicates, and future application dates, whichever entry point is used
- [ ] Pickers list only valid choices: open jobs, non-archived candidates, and nothing already applied to
- [ ] Application date defaults to today and accepts past dates
- [ ] Created timestamp is recorded separately from the application date
- [ ] New applications start in Applied, with a stage change having a blank from-stage and the "application created" reason
- [ ] When a candidate has an exited application for a job, the duplicate refusal explains that a manager can reopen it
- [ ] After adding from the board, the new card appears in Applied
- [ ] Service tests and picker view tests cover the above

---

## Phase 9: Candidate detail and notes

**User stories**: 16, 17, 18, 19, 20

### What to build

The full candidate detail page and `CandidateNote`. The page shows contact information, lead source, all applications with their current stage, the notes stream, and complete stage history. Adding a note is an HTMX form that inserts it at the top without a reload. A note can optionally be tagged to one of that candidate's applications. Notes have no edit or delete path in the app, and removing a mis-filed note happens only in Django Admin. `seed_demo` adds sample notes.

### Acceptance criteria

- [ ] The detail page shows contact details, lead source, applications with current stage, notes, and full stage history with who, when, and why
- [ ] Adding a note inserts it at the top of the stream without a page reload
- [ ] Each note shows its author and time
- [ ] A note can be tagged to an application, and the tag is displayed
- [ ] A note cannot be tagged to another candidate's application, even with a hand-crafted POST
- [ ] An empty note is refused and the error renders
- [ ] The app has no route for editing or deleting a note
- [ ] Service and view tests cover the above

---

## Phase 10: Close and reopen jobs

**User stories**: 37, 38, 39, 40, 41, 42, 43, 44, 45

### What to build

Close and reopen as manager-only page actions with confirmation dialogs. Closing is blocked while any application is in Offer, and lists them. Otherwise all active-stage applications move to Rejected with the "job closed" reason, and the job is marked Closed with its closed-at time. Reopening marks it Open and can optionally restore applications whose most recent change was the "job closed" rejection, skipping any the in-progress guard forbids.

### Acceptance criteria

- [ ] Closing is refused while any application is in Offer, and the page lists those applications
- [ ] The close confirmation shows the number of applications that will be rejected
- [ ] Closing moves all active-stage applications to Rejected with the "job closed" reason and records closed-at
- [ ] Hired, Rejected, and Withdrawn applications are untouched by closing
- [ ] Closed jobs refuse new applications and disappear from the job picker
- [ ] Reopening without restore marks the job Open and changes no applications
- [ ] Reopening with restore returns only applications whose most recent change was the "job closed" rejection, with the "job reopened" reason
- [ ] Applications rejected for normal reasons are never restored
- [ ] Restore skips candidates archived since the close and reports the number skipped
- [ ] Close and reopen are refused on the server for recruiters and hidden from them
- [ ] Each close or reopen applies all of its changes together, or none on failure
- [ ] Service and view tests cover the above

---

## Phase 11: Archive and unarchive candidates

**User stories**: 15, 21, 22, 23, 24, 25, 26, 27

### What to build

Archive and unarchive as manager-only page actions with confirmation dialogs. Archiving is blocked while any application is in Offer. Otherwise active-stage applications move to Withdrawn with the "candidate archived" reason, and the candidate is hidden from default lists and pickers. Unarchiving clears the flag and can optionally restore applications whose most recent change was the archive withdrawal, skipping any the in-progress guard forbids. The candidates list gains a toggle to show archived people.

### Acceptance criteria

- [ ] Archiving is refused while any application is in Offer
- [ ] The archive confirmation shows the number of applications that will be withdrawn
- [ ] Archiving moves all active-stage applications to Withdrawn with the "candidate archived" reason and leaves other stages untouched
- [ ] Archived candidates are hidden from the candidates list by default, appear with the toggle on, and are excluded from pickers
- [ ] Archived candidates cannot receive new applications
- [ ] Unarchiving without restore clears the flag and changes no applications
- [ ] Unarchiving with restore returns only applications whose most recent change was the archive withdrawal, with the "candidate unarchived" reason
- [ ] Restore skips applications whose job has since closed and reports the number skipped
- [ ] Archive and unarchive are refused on the server for recruiters and hidden from them
- [ ] The app has no route for deleting a candidate, and history is preserved through archive and unarchive
- [ ] Each archive or unarchive applies all of its changes together, or none on failure
- [ ] Service and view tests cover the above
