# AGENTS.md — Project Guidelines & Agent Directives

## 1. Project Overview & Identity
- **Project Name:** Weekly Team Feedback Tool
- **Goal:** Help project teams collect honest weekly feedback (Start, Stop, Continue), turn submissions into a focused retrospective, and document decisions and action items with AI assistance.
- **Repository:** `parnamijanesh-creator/project-feedback`

---

## 2. Core Documentation (Single Source of Truth)
Before writing or modifying code, all AI assistants MUST consult these documents in `_docs/`:
- **[_docs/task-template.md](_docs/task-template.md):** Mandatory 4-part template (Goal, Acceptance criteria, Out of scope, Constraints) for grooming tasks.
- **[_docs/orchestrator.md](_docs/orchestrator.md):** Main session orchestrator role, subagent lifecycle, and loop directives.
- **Team Roles (in `_docs/team/`):**
  - **[_docs/team/pm.md](_docs/team/pm.md):** Product Manager role (grooming, requirements, acceptance criteria).
  - **[_docs/team/software-engineer.md](_docs/team/software-engineer.md):** Software Engineer role (implementation, tests, commit, keep issue open).
  - **[_docs/team/qa-engineer.md](_docs/team/qa-engineer.md):** QA Engineer role (independent verification, acceptance check, PASS/FAIL verdict).
- **[_docs/progress.md](_docs/progress.md):** Living tracker of completed tasks, active work, and implementation decisions.
- **Reference Specifications (in `_docs/` / `_docs/outdated/`):**
  - `plan.md`: Complete product requirements, core workflows, user roles (Facilitator vs Member).
  - `architecture.md`: Concrete technical architecture, schemas, WebSockets, Celery, Whisper, LLM structured extraction.
  - `tasks.md`: Original 23 backlog tasks.

---

## 3. Team Roles & Execution Protocol

### 3.1 Orchestrator — Main Session (`_docs/orchestrator.md`)
The main session acts as the **Orchestrator**. It manages the overarching issue lifecycle and delegates work to the PM, Software Engineer, and QA Engineer (as specialized personas or subagents).
- **Rules:**
  - The orchestrator does **not** groom, implement, or test directly.
  - **Batch limit:** You can work on up to 5 issues at once. Not more than 5 at a time.
  - **Mandatory grooming:** Do not skip step 2 (PM grooming), even when the task looks obvious.
  - The engineer does not close the issue.
  - QA does not fix the code, only outputs `## QA: PASS` or `## QA: FAIL`.
  - The orchestrator closes the issue only after QA outputs `## QA: PASS`.
- **Lifecycle Loop:**
  1. Pick next open issue from the backlog (up to 5 at a time).
  2. **PM grooms it** (never skip grooming, even if obvious).
  3. **Engineer implements it** (leaves issue open, comments implementation details).
  4. **QA verifies it** (does not touch code, outputs `## QA: PASS` or `## QA: FAIL`).
  5. On `FAIL`: loop back to step 3 with the QA findings as input.
  6. On `PASS`: Orchestrator updates `_docs/progress.md` and closes the GitHub issue.
  7. Repeat until the backlog is empty.

### 3.2 Product Manager (`_docs/team/pm.md`)
- **When:** Task is ungroomed or requirements are ambiguous.
- **Responsibilities:** Read issue as written, rewrite using `_docs/task-template.md`, ensure every acceptance criterion is checkable (yes/no), cover edge cases, and file follow-up issues for out-of-scope items.
- **Rule:** Do NOT write any application code while in PM role.

### 3.3 Software Engineer (`_docs/team/software-engineer.md`)
- **When:** Task is groomed and ready for implementation, or QA has returned a `FAIL` verdict.
- **Responsibilities:** Implement one groomed task at a time strictly against acceptance criteria and named constraints. Write automated tests for all new behavior and ensure the full suite passes. Commit work regularly.
- **Rule:** Do NOT close the GitHub issue. Leave the issue open and post a comment detailing what was implemented.

### 3.4 QA Engineer (`_docs/team/qa-engineer.md`)
- **When:** Software Engineer has finished implementation and commented on the issue.
- **Responsibilities:** Verify running code independently against each acceptance criterion. Run test suite. Evaluate edge cases.
- **Rule:** Do NOT modify any code. Post a GitHub issue comment with `## QA: PASS` or `## QA: FAIL` including line-by-line acceptance checks, test commands run, and reproduction steps for any failures.

---

## 4. Technology Stack Guardrails
- **Backend:** Python 3.11+, Django 5.x, ASGI via Daphne.
- **Database:** PostgreSQL 16+ (Dockerized in dev/prod; SQLite permitted for lightweight unit test runs).
- **Real-Time:** Django Channels 4.x with Redis channel layer (`redis:6379`).
- **Frontend Interactivity:** Server-rendered Django Templates enhanced with **HTMX 2.x**, **Alpine.js 3.x**, and **SortableJS** (for drag-and-drop retro card clustering). Avoid heavy JavaScript frameworks (no React/Vue/Node build pipelines).
- **Styling:** Tailwind CSS (via standalone CLI or CDN for development).
- **Asynchronous Workers:** Celery 5.x with Redis as message broker and result backend.
- **Audio & Media:** ffmpeg for audio extraction, OpenAI / `faster-whisper` for speech-to-text transcription.
- **AI Structured Output:** Pydantic v2 / Instructor with OpenAI, Gemini, or Anthropic models for extracting action items, owners, and decisions.

---

## 5. Session Startup Protocol (MANDATORY FOR EVERY NEW SESSION)
When entering a new session or receiving a new prompt, follow these steps in order:

1. **Check Progress State:**
   - Read `_docs/progress.md` to see which issue is currently active, what has already been built, and recent implementation notes.
2. **Inspect Git & Environment Status:**
   - Run `git status` and `git log -n 3` to verify active branch and latest commits.
3. **Determine Role Persona:**
   - Check the active issue's current lifecycle state or user directive:
     - **Needs grooming:** Adopt **Product Manager** (`_docs/team/pm.md`), groom with `_docs/task-template.md`, and update issue via `gh issue edit`.
     - **Groomed / Ready to build:** Adopt **Software Engineer** (`_docs/team/software-engineer.md`), implement strictly to criteria, write tests, commit, and comment on the issue.
     - **Built / Ready for testing:** Adopt **QA Engineer** (`_docs/team/qa-engineer.md`), verify running code, post `## QA: PASS` or `## QA: FAIL` comment on issue.
4. **Adhere to Architectural Models:**
   - Cross-reference architecture documentation to ensure any new models, views, or endpoints align with established schemas.
5. **Test-Driven Verification:**
   - Run automated tests (`python manage.py test` or `pytest`) to verify tests pass before and after making changes.
6. **Update Progress & GitHub:**
   - On task completion (after QA approval), update `_docs/progress.md`, commit with an issue reference, push to remote, and close the GitHub issue.

---

## 6. Non-Negotiable Product Rules
1. **Anonymity Guarantee:** Anonymous feedback cards MUST be strictly decoupled from user identification at the database level (`user_id = NULL`). Never store or expose author metadata for anonymous submissions.
2. **Private Until Revealed:** Feedback cards cannot be viewed by other teammates until the facilitator triggers the "Reveal" stage.
3. **Masked Voting:** Vote counts remain secret during the voting phase and are only published after the facilitator closes voting.
4. **Draft AI Outputs:** Transcribed decisions and action items generated by AI must remain unconfirmed drafts until explicitly reviewed and approved by the facilitator.
