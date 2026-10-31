# PRD: Applicant Tracking System

## Problem Statement

Hiring teams at the company have no single place to manage their recruiting work. Job openings, candidate contact details, where each candidate came from, and how far each person has progressed in the hiring process are scattered across email, spreadsheets, and memory. As a result:

- Recruiters cannot quickly see where every applicant for a job stands, and moving someone forward means updating several places by hand.
- The same person can end up recorded twice, or be considered for the same job twice.
- There is no reliable history of who moved a candidate, when, or why, and no shared place for notes about a candidate.
- When a job is filled or cancelled, candidates still "in progress" for it are left in limbo.
- Important decisions such as making an offer or confirming a hire are not clearly reserved for the people who should make them.

## Solution

An internal, staff-only web application for hiring teams. Candidates never log in. Staff sign in with accounts created by an administrator and work in one of two roles: **Recruiter** or **Hiring Manager**. Hiring Managers have every Recruiter permission plus the authority to make offers, confirm hires, close and reopen jobs, archive candidates, and undo manager-level decisions.

Staff can:

- Maintain a de-duplicated list of candidates with basic contact information and lead source.
- Create and edit job openings, tag them with skills, and open or close them.
- Record a candidate's application to a job, once per job, with the real application date.
- See every applicant for a job on a **drag-and-drop pipeline board** organized by stage, and move applicants between stages without reloading the page. The server enforces a defined set of transition rules and refuses illegal moves.
- Review a candidate's complete history over time: every application, every stage change (who, when, and why), and an append-only stream of notes.
- Close a job or archive a candidate and have the system resolve in-progress applications automatically and transparently. Both actions can be reversed, with an option to restore the affected applications.

## User Stories

### Accounts and access

1. As a staff member, I want to log in with a username and password, so that only internal employees can access recruiting data.
2. As a staff member, I want to be redirected to the login page when I am not signed in, so that no recruiting data is visible to anonymous visitors.
3. As a staff member, I want to log out, so that nobody else can use my session on a shared computer.
4. As a system administrator, I want to create staff accounts and assign them the Recruiter and/or Hiring Manager role in the admin site, so that new team members can be onboarded without a public signup form.
5. As a system administrator, I want the Recruiter and Hiring Manager roles and their permissions to exist automatically in every new database, so that setup is repeatable and nothing has to be configured by hand.
6. As a staff member who holds both roles, I want to have the combined permissions of both, so that I can do all of my work from one account.
7. As a developer or instructor, I want a command that loads realistic demo users, jobs, candidates, and applications, so that the app can be demonstrated and tested by hand quickly.

### Candidates

8. As a recruiter, I want to create a candidate with first name, last name, email, optional phone, lead source, and optional lead-source detail, so that I have a basic record of each person.
9. As a recruiter, I want lead source to be one of Company Website, Job Board, Referral, or Other, so that reporting on sources is consistent.
10. As a recruiter, I want to add free-text detail to the lead source (for example "Indeed" or "Referred by Maria Lopez"), so that I can remember exactly where a candidate came from.
11. As a recruiter, I want the system to refuse a new candidate whose email already exists, regardless of capitalization, and point me to the existing record, so that the same person is never entered twice.
12. As a recruiter, I want emails stored in lowercase, so that "Jane@X.com" and "jane@x.com" are treated as the same person.
13. As a recruiter, I want to edit a candidate's details, so that I can keep contact information current.
14. As a recruiter, I want to search the candidates list by name or email, so that I can find a person quickly.
15. As a recruiter, I want archived candidates hidden from the candidates list by default, with a toggle to show them, so that the list focuses on active people.
16. As a recruiter, I want a candidate detail page showing contact information, lead source, all of their applications with current stage, their notes, and their full stage history, so that I can understand their entire relationship with the company in one place.

### Candidate notes

17. As a recruiter, I want to add a dated note to a candidate without reloading the page, so that I can record context such as "prefers remote work."
18. As a recruiter, I want each note to show its author and time, so that I know who wrote what and when.
19. As a recruiter, I want to optionally tag a note to one of the candidate's applications, so that job-specific feedback (such as interview feedback) is clearly labelled.
20. As a staff member, I want notes to be permanent (no editing or deleting in the app), so that the candidate's history is trustworthy; mistakes are corrected with a follow-up note.

### Archiving candidates

21. As a hiring manager, I want to archive a candidate instead of deleting them, so that their history is preserved but they no longer clutter day-to-day lists.
22. As a hiring manager, I want archiving to be blocked while the candidate has any application in the Offer stage, so that an outstanding offer is never silently cancelled.
23. As a hiring manager, I want archiving to automatically move the candidate's active applications to Withdrawn, recorded with a "candidate archived" reason, so that no job pipeline shows a hidden candidate as still in progress.
24. As a hiring manager, I want the archive confirmation to tell me how many applications will be withdrawn, so that I understand the effect before confirming.
25. As a hiring manager, I want to unarchive a candidate and optionally restore the applications that the archive withdrew to their previous stages, so that an accidental archive can be fully undone.
26. As a recruiter, I want to be prevented from creating new applications for an archived candidate, so that inactive people are not accidentally put back into a pipeline.
27. As a recruiter, I want archive and unarchive actions to be unavailable to me, so that this decision stays with hiring managers.

### Job openings and skills

28. As a recruiter, I want to create a job opening with a title and optional department, location, and description, so that the team knows what we are hiring for.
29. As a recruiter, I want to edit a job opening's details, so that postings stay accurate.
30. As a recruiter, I want to tag a job opening with the relevant skills, so that everyone knows what the role requires.
31. As a recruiter, I want to add a new skill while editing a job if it does not exist yet, so that I am never blocked by a missing skill.
32. As a recruiter, I want skill names to be unique regardless of capitalization, so that "Python" and "python" do not become two different skills.
33. As a hiring manager, I want to be the only one who can rename or delete skills, so that changes affecting many jobs are made deliberately.
34. As a staff member, I want the jobs list to be my home page, showing open jobs by default with a count of active applicants for each, so that I can see where hiring activity is.
35. As a staff member, I want to filter the jobs list to show closed jobs, so that I can look up past openings.
36. As a staff member, I want each job to record who created it and when it was closed, so that its lifecycle is visible.

### Closing and reopening jobs

37. As a hiring manager, I want to close a job opening, so that it stops receiving applications once the role is filled or cancelled.
38. As a hiring manager, I want closing to be blocked while any application for the job is in the Offer stage, and to be shown which ones, so that outstanding offers are resolved before the job closes.
39. As a hiring manager, I want closing to automatically move every active application (Applied through Final Review) to Rejected, recorded with a "job closed" reason, so that every candidate gets a clear outcome.
40. As a hiring manager, I want the close confirmation to tell me how many applications will be rejected, so that I understand the effect before confirming.
41. As a hiring manager, I want Hired, Rejected, and Withdrawn applications left untouched when a job closes, so that existing outcomes are preserved.
42. As a recruiter, I want closed jobs to refuse new applications, so that nobody is added to a role we are no longer filling.
43. As a hiring manager, I want to reopen a closed job, so that a role can be filled again or an accidental close can be undone.
44. As a hiring manager, I want the reopen dialog to offer to restore the candidates who were rejected by the close to their previous stages, so that an accidental close is undone in one step without touching candidates rejected for normal reasons.
45. As a recruiter, I want close and reopen actions to be unavailable to me, so that this decision stays with hiring managers.

### Applications

46. As a recruiter, I want to add an applicant from a job's pipeline board by picking an existing candidate, so that I can build the pipeline for a job.
47. As a recruiter, I want to apply a candidate to a job from the candidate's page by picking an open job, so that I can work from whichever direction is convenient.
48. As a recruiter, I want the pickers to list only valid choices (open jobs, non-archived candidates, and nothing the candidate has already applied to), so that I cannot create an invalid application.
49. As a recruiter, I want the system to refuse a second application by the same candidate to the same job, so that each candidate applies to each job only once.
50. As a recruiter, I want to enter the date the candidate actually applied, defaulting to today, so that applications entered late still show the correct date.
51. As a recruiter, I want future application dates to be rejected, so that application data stays realistic.
52. As a staff member, I want the system to separately record when an application was entered, so that there is an audit trail of data entry.
53. As a recruiter, I want new applications to start in the Applied stage, so that every applicant enters the process at the beginning.
54. As a recruiter, I want a candidate who "re-applies" to a job they were rejected from or withdrew from to be handled by reopening their existing application, so that the one-application-per-job rule is preserved.

### Pipeline board

55. As a recruiter, I want each job to have a pipeline board with a column for each stage (Applied, Screening, Interview, Final Review, Offer, Hired) plus Rejected and Withdrawn columns, so that I can see at a glance where every applicant stands.
56. As a recruiter, I want each column to show a count of applicants, so that I can see the shape of the pipeline.
57. As a recruiter, I want each card to show the candidate's name, email, lead source and detail, application date, and how long since their last move, so that I have the key facts without opening the candidate.
58. As a recruiter, I want to drag a card to another column to move the applicant to that stage without reloading the page, so that updating the pipeline is fast.
59. As a recruiter, I want columns I am allowed to drop into to be highlighted, and disallowed ones faded, while I drag, so that I know which moves are legal before I drop.
60. As a recruiter, I want an illegal drop to snap back and show me a message explaining why it was refused, so that I understand the rules.
61. As a recruiter, I want the board to refresh with the latest data after every move, so that counts, "last moved" times, and changes made by colleagues are always current.

### Stage transition rules

62. As a recruiter, I want to move an application between any of the active stages (Applied, Screening, Interview, Final Review), forward or backward and by any number of stages, so that I can fast-track strong candidates and correct mistakes.
63. As a hiring manager, I want only hiring managers to be able to move an application from Final Review to Offer, so that offers are a manager decision.
64. As a staff member, I want an offer to be possible only from Final Review, so that candidates are not offered a job before being fully reviewed.
65. As a hiring manager, I want only hiring managers to be able to move an application from Offer to Hired, so that hires are a manager decision.
66. As a staff member, I want Hired to be reachable only from Offer, so that nobody is hired without an offer.
67. As a recruiter, I want to be able to move an application in an active stage or in Offer to Rejected or Withdrawn, so that I can record a candidate declining an offer or being turned down.
68. As a hiring manager, I want only hiring managers to be able to move an application from Offer back to an active stage, so that a recruiter cannot undo a manager's offer.
69. As a hiring manager, I want to be able to move an application out of Hired (to any other stage), so that I can handle a new hire who backs out or correct a mistaken hire.
70. As a recruiter, I want moves out of Hired to be unavailable to me, so that confirmed hires are protected.
71. As a hiring manager, I want Rejected and Withdrawn to be closed outcomes that only a hiring manager can reopen, with reopening returning the application to the stage it was in before, so that rejections are final unless a manager reverses them.
72. As a staff member, I want every stage change, including automatic ones, to be recorded with the from-stage, to-stage, the person, the time, and a reason, so that the pipeline has a complete audit trail.
73. As a staff member, I want blocked move attempts not to be recorded as stage changes, so that the history reflects only what actually happened.
74. As a staff member, I want the server to enforce every transition rule, so that rules cannot be bypassed by manipulating the page.

## Implementation Decisions

### Stack and structure

- Python, Django, SQLite, managed with uv. Tailwind CSS with DaisyUI via django-tailwind-cli. HTMX for partial page updates. Ruff for linting and formatting. pytest (with pytest-django) for tests.
- SortableJS provides drag-and-drop on the pipeline board. It is saved as a static file in the project rather than loaded from a CDN, so its version is fixed and it works offline.
- A single Django app holds all of the domain. Internally it is organized by responsibility:
  - a **pipeline rules module** holds the stage definitions, the transition map, and a single `can_transition(user, application, target)` style check used by both the UI and the server;
  - a **services module** holds every operation that changes data (create application, move application, close job, reopen job, archive candidate, unarchive candidate, add note), and each one writes its stage-change records;
  - **views are thin**: they check login/permissions, call a service, and render a template or partial.
- A **custom User model** is defined from the start (no extra fields required initially) to avoid a painful migration later.

### Roles and permissions

- Two Django groups, **Recruiter** and **Hiring Manager**, plus their permissions, are created by a data migration. The Hiring Manager group holds all Recruiter permissions, and a user may belong to both.
- Custom permissions represent manager-only decisions (for example: make offer, confirm hire, change an offer or hire, reopen application, close/reopen job, archive candidate, rename/delete skill).
- Every view requires login. Manager-only actions are checked on the server and hidden in the UI from users without permission.
- Staff accounts are created and assigned to groups only through Django Admin. There is no signup page and no in-app user management.
- Hard deletes of candidates (and other cleanup such as removing a mis-filed note) happen only through Django Admin.
- A `seed_demo` management command creates demo users in each role, jobs, skills, candidates, and applications across all stages.

### Data model

- **Candidate**: first name, last name, email (required, unique, normalized to lowercase on save/validation), phone (optional), lead source (choices: Company Website, Job Board, Referral, Other), lead-source detail (optional text), archived flag (default false), created/updated timestamps.
- **JobOpening**: title (required), department, location, description (optional), status (Open/Closed, default Open), skills (many-to-many to Skill), created-by user, created/updated timestamps, closed-at timestamp.
- **Skill**: name, unique case-insensitively.
- **Application**: candidate, job opening, current stage, staff-entered application date (defaults to today, must not be in the future), created timestamp. A database-level unique constraint on (candidate, job opening).
- **StageChange**: application, from-stage, to-stage, user who made the change, timestamp, and a reason (normal move, job closed, candidate archived, job reopened, candidate unarchived, application reopened). The "stage before exit" used for reopening is derived from the most recent stage change into Rejected/Withdrawn.
- **CandidateNote**: candidate, author, body, timestamp, optional link to one of that candidate's applications. Append-only in the app.

### Stage transition rules

- Stages: Applied, Screening, Interview, Final Review (the **active** stages), Offer, Hired, and the **exit** stages Rejected and Withdrawn.
- Rules:
  - Active → any other active stage (forward or back, any distance): everyone.
  - Final Review → Offer: hiring manager only. No other stage may move to Offer.
  - Offer → Hired: hiring manager only. No other stage may move to Hired.
  - Offer → any active stage: hiring manager only.
  - Active or Offer → Rejected/Withdrawn: everyone.
  - Hired → any other stage: hiring manager only.
  - Rejected/Withdrawn → reopen to the stage held immediately before the exit: hiring manager only. No other moves out of Rejected/Withdrawn.
  - Moving to the current stage is not a move.
- The same rule function drives the drag highlighting on the board and the server-side check, and the server is authoritative.

### Closing / reopening jobs and archiving / unarchiving candidates

- **Close job** (manager): refused if any of the job's applications is in Offer (listing them). Otherwise, all active-stage applications move to Rejected with reason "job closed," the job is marked Closed with a closed-at time, and no new applications are accepted. Hired, Rejected, and Withdrawn are untouched. A confirmation dialog shows the number of applications that will be rejected.
- **Reopen job** (manager): marks the job Open. An optional checkbox restores applications whose most recent change was the "job closed" rejection to their previous stage, each recorded with a "job reopened" reason.
- **Archive candidate** (manager): refused if any of the candidate's applications is in Offer. Otherwise all active-stage applications move to Withdrawn with reason "candidate archived," and the candidate is hidden from default lists and cannot receive new applications. A confirmation shows the count.
- **Unarchive candidate** (manager): clears the flag. An optional checkbox restores applications withdrawn by the archive to their previous stage.
- Close/reopen and archive/unarchive are normal page actions with confirmation dialogs, not pipeline drags.

### Creating applications

- One shared service creates applications and enforces: job is open, candidate is not archived, no existing application for the pair, and application date not in the future. New applications start in Applied and record an initial stage change.
- Two entry points use it: "Add applicant" on the job's pipeline board (candidate picker with search) and "Apply to job" on the candidate detail page (open-job picker). Pickers exclude invalid choices.

### Pages and HTMX interactions

- Pages: Login; Jobs list (home, open by default, closed filter, active-applicant counts); Job detail with pipeline board; Job create/edit (with skill picker and inline "add skill"); Candidates list (search by name/email, archived hidden by default with toggle); Candidate detail (info, applications, notes, stage history, archive/unarchive); Candidate create/edit.
- **Pipeline move contract**: dropping a card triggers an HTMX POST to an application "move" endpoint with the target stage. The server runs the rule check and, if allowed, saves the stage and writes the stage change. **In every case, allowed or blocked, the response is the full re-rendered board**, so snap-back, counts, and "last moved" stay correct and reflect other users' changes. A blocked move also returns an error message shown as a toast.
- Rejected and Withdrawn columns are always visible on the board so they can be drop targets. During a drag, allowed columns are highlighted and blocked ones faded. Dragging a Rejected/Withdrawn card into its previous stage is treated as a reopen.
- Adding a note is an HTMX form that inserts the new note at the top of the candidate's notes without reloading.
- Styling uses DaisyUI components throughout, including the login page.

### Testing

- pytest with pytest-django, test data from fixtures in a shared conftest (for example recruiter, manager, dual-role user, open job, candidate, applications at each stage) plus small helper functions. No factory library.
- **Rule and service tests** (the majority): each transition rule for each role; close job (blocked by Offer, rejects active, leaves outcomes alone, blocks new applications); reopen job with and without restore; archive/unarchive with and without restore; duplicate application refused; closed job and archived candidate refused; future application date refused; email lowercasing and duplicate email refused; case-insensitive skill uniqueness; stage changes recorded with correct reasons.
- **View tests** with Django's test client: login required everywhere; manager-only actions forbidden to recruiters; the move endpoint returns the board for both allowed and blocked moves and only changes the database when allowed; form validation errors render; pickers exclude invalid choices.
- No browser/end-to-end tests. Drag-and-drop is checked by hand during manual verification.
- Ruff runs over the codebase as linter and formatter.

## Out of Scope

- Candidate-facing features of any kind (portal, public job board, candidate login, applying online).
- Self-signup, in-app user/team management, and password-reset flows beyond what Django provides.
- Résumé or other file uploads.
- Skills on candidates and candidate–job skill matching; required vs. preferred skills.
- Department as its own model, employment type, and salary ranges.
- Editing or deleting notes in the app; editing or deleting candidates in the app (only archiving).
- Backdating individual stage moves; stage moves are always timestamped automatically.
- Reporting dashboards, analytics, and a separate dashboard page.
- Email notifications, calendar/interview scheduling, and integrations with job boards.
- Browser-based automated tests (e.g. Playwright).
- A keyboard or menu alternative to drag-and-drop for moving applicants (can be added later if accessibility requires it).
- Deployment and production database configuration beyond local SQLite.

## Further Notes

- Two throwaway prototypes in the repository's prototypes folder informed these decisions: a stage-transition rules demo and a pipeline-view comparison (Kanban with menu, drag-and-drop Kanban, table). The final design is the drag-and-drop Kanban with the table variant's richer card details. The prototypes are design references only and must not be imported by the application. The transition-rules prototype predates two later rule changes (backward moves of any distance, and managers moving applications out of Hired); this PRD is authoritative.
- The guiding principle across the design is **"never lose history"**: archive instead of delete, append-only notes, a stage-change record for every move (including automatic ones), and recorded reasons that make bulk actions reversible.
- A second guiding principle is **"only a manager can undo a manager decision"**: offers, hires, job closures, archives, and reopenings.
- Known trade-off: drag-only movement is not keyboard accessible. Adding a "Move to…" menu on each card that uses the same endpoint is the planned remedy if needed.
- The natural next step is to break this PRD into implementation phases (e.g. with the prd-to-plan skill), starting with a thin vertical slice: custom user and roles, one job, one candidate, one application, and a single allowed move on the board.
