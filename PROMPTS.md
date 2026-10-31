# PROMPTS.md — AI Usage Log

This file is the record of AI use on this codebase. At the end of every
agent session, direct the agent to write the session log with this prompt:

> Append a session log to PROMPTS.md at the repo root, under today's date,
> newest entry at the top. Record every prompt I gave you this session, in
> order, including any corrections. End the entry with a short summary:
> the outcome, any places where I deviated from a recommended answer or
> asked follow-up questions, and anything that went sideways.

Two rules:

- Entries are added only by that prompt, never unprompted.
- New entries go at the top. Never rewrite or delete an old entry — the
  log is part of your work, and an honest log of a session that went
  sideways is worth more than a tidy one.

Each entry has this shape:

    ## YYYY-MM-DD — <one-line summary>

    ### Prompts
    1. ...

    ### Summary
    - **Outcome:** what was built and what was kept
    - **Deviations:** recommendations overridden, follow-up questions asked
    - **Sideways:** failures, wrong turns, and how they were caught

## 2026-10-29 — Grill-me design interview, two prototypes, and PRD for the ATS

### Prompts
1. `/grill-me @project-idea.md`
2. B
3. B, and yes - one person can hold both roles
4. A, and store email in lowercase
5. B, and yes keep it on the candidate
6. A, and agree with the archive and delete rules
7. `/prototype Please prototype the stage transition rules from the most recent question in the grill-me interview`
8. C, but allow a manager to move an applicant out of Hired, and also allow all users to move applicants back multiple stages at a time
9. A
10. D
11. C
12. C
13. A, and agree with the skill permissions
14. A
15. `/prototype Can you show me the three different options you are offering so I can compare them?`
16. B's menu, with C's extra detail on each card
17. Option 2
18. A
19. A
20. A, and the core pages look correct
21. A, agree with candidate-level notes and application tag
22. A, and agree with the custom User model
23. A
24. B
25. `/to-prd`
26. Write this session log to PROMPTS.md according to its instructions.

### Summary
- **Outcome:** An 18-question design interview (plus follow-ups 6b and 7b) settled roles, the data model, stage-transition rules, job-close and candidate-archive behavior, the pipeline UI, the HTMX move contract, account management, the page list, app structure, and the testing strategy. Two throwaway prototypes were built in `prototypes/`: `stage-transitions.html` (a logic demo of the transition rules) and `pipeline-view.html` (three pipeline layouts compared using DaisyUI and SortableJS). The PRD was written to `prd/applicant-tracking-system.md` with 74 user stories. Nothing was committed.
- **Deviations:**
  - Q1 (roles): chose B (Recruiter and Hiring Manager roles) over the recommended C (single role with Django Admin for dangerous actions).
  - Q2 (permissions): chose B (recruiters can create and edit jobs) over the recommended A.
  - Q6 (transitions): chose C but changed it so a manager can move applicants out of Hired, and everyone can move applicants back multiple stages. This prompted follow-up question 6b about who can leave Offer and Hired; A was chosen.
  - Q11 (pipeline UI): asked for a visual prototype of the three options, then chose drag-and-drop with the table's richer card detail over the recommended Kanban with a move menu (SortableJS is added outside the required stack).
  - Asked for prototypes twice (Q6 and Q11) instead of answering from the text.
  - All other answers followed the recommendation, sometimes with small agreed additions (lowercase emails, the skill-permission tweak, the custom User model).
- **Sideways:**
  - The reply "B's menu" was ambiguous because variant B had no menu. Claude asked which option was meant before recording it, and the answer was Option 2 (drag-and-drop).
  - The Q2 permission matrix left recruiters unable to add skills while letting them create jobs. This was caught at Q9 and fixed so anyone can add a skill inline, and only managers can rename or delete one.
  - The stage-transitions prototype was not updated after the Q6 rule changes, so it shows outdated rules. The PRD notes that it is the authoritative version.
  - Claude opened both prototypes in the browser but never visually checked that they render correctly.