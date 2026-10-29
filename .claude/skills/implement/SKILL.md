---
name: implement
description: Implement one approved phase from a PRD and plan using feedback loops.
argument-hint: "@prd/<feature>.md @plans/<feature>.md implement phase <N>"
disable-model-invocation: true
---

# Implement

## 1. Understand the Phase

Read the referenced PRD and plan. Explore the codebase to understand the relevant files,
patterns, and conventions. If the request does not identify a phase, ask which one.

Implement only that phase. Do not begin the next one.

## 2. Implement the Phase

Run the `/tdd` skill and follow its instructions. After the user confirms the results of tdd, implement the rest of the phase's requirements using the normal process.

## 3. Run Feedback Loops

Run the linter and format check. Once both pass, run the full test suite. Do not move on until the full suite is green.

## 4. Manual Verification

Answer the following question: "How do I manually verify this feature in the browser?". Stop and wait for the user to run through the manual verification process. Do not move on until the user has confirmed that the manual checks pass.

## 5. Finish the Phase

Follow the following steps in this order:

1) Update PROMPTS.md using the format specified in that file
2) Commit the completed phase - the commit message should follow this format: "<feature> feature - Implement Phase <N>"
3) Push the commit to GitHub