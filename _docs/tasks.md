# Backlog Tasks: Weekly Team Feedback Tool

## 1. Initial Project Setup and Smoke Test
Goal: Initialize a clean Django 5.x project with dependency management and a passing automated smoke test.
Description: Configure a baseline Django 5.x project structure with an ASGI entry point, modular settings, and dependency definitions in pyproject.toml or requirements.txt. Add a simple health-check endpoint returning a 200 OK status and a passing automated unit test to verify the test runner works properly. Provide a README documenting the environment setup and instructions for running the test suite.

## 2. Containerized Local Development Environment
Goal: Provide a complete Docker Compose environment running Django with Daphne, PostgreSQL, and Redis.
Description: Create a Dockerfile and a docker-compose.yml file configuring web (ASGI via Daphne), db (PostgreSQL), and redis services with persistent volume mounts. Include a sample environment configuration file (.env.example) with sensible local defaults for database and broker connection strings. Validate that all services boot cleanly and that the Django test suite runs successfully inside the container.

## 3. User Authentication and Session Management
Goal: Implement user registration, login, logout, and session management using Django's built-in authentication system.
Description: Configure Django's standard authentication framework with custom templates styled using Tailwind CSS. Provide functional views for user registration with email and password, login with credential validation, and logout with appropriate redirect handling. Add test cases verifying password validation rules, session cookie persistence, and redirection of unauthenticated requests.

## 4. Projects and Team Membership Management
Goal: Allow users to create projects and manage team members with Facilitator and Member roles.
Description: Implement the `Project` and `ProjectMember` models supporting Facilitator and Member role assignments for authenticated users. Build project creation and detail views where project creators can invite or add registered users to a project roster. Write tests verifying that project memberships and role permissions are correctly enforced across views.

## 5. Feedback Cycle Creation and Facilitator Controls
Goal: Enable facilitators to initiate weekly feedback cycles and view cycle history on the project dashboard.
Description: Create the `FeedbackCycle` model linked to a project, tracking status through Collecting, Retrospective, and Completed phases with a target week date. Build a project dashboard view listing active and previous feedback cycles along with an action button for facilitators to launch a new cycle. Include unit tests confirming that only project facilitators can create or open new cycles.

## 6. Feedback Card Models and Anonymity Logic
Goal: Implement the data model for Start, Stop, and Continue feedback cards with privacy-preserving anonymity support.
Description: Define the `FeedbackCard` model with Category choices (Start, Stop, Continue), text content, an anonymous flag, and cycle foreign keys. Implement model methods and query managers that enforce strict author decoupling for anonymous entries so user IDs are not saved or exposed. Write unit tests ensuring anonymous cards cannot be traced back to user accounts and that author attribution persists for standard cards.

## 7. Feedback Submission Interface with HTMX
Goal: Build an interactive feedback form allowing team members to create, edit, and delete Start, Stop, and Continue cards.
Description: Build a three-column feedback submission view where users can independently add multiple cards under Start, Stop, and Continue categories using HTMX. Include in-place editing and deletion controls for draft cards while restricting view queries to only display cards created by the active user. Add integration tests verifying that users can modify their own feedback and cannot view cards submitted by other teammates.

## 8. Retrospective Session Model and Reveal Stage
Goal: Allow the facilitator to start a retrospective session and reveal all submitted feedback cards simultaneously.
Description: Create the `RetrospectiveSession` model linked to a feedback cycle and build the facilitator board view that initializes the retrospective in the Reveal stage. Provide an action for the facilitator to reveal all collected cards at once, displaying them grouped into Start, Stop, and Continue columns. Include tests verifying that card content becomes visible to all project members upon reveal while anonymous cards remain authorless.

## 9. AI-Assisted Thematic Card Clustering Service
Goal: Generate automated suggestions that group revealed feedback cards into thematic clusters using an LLM.
Description: Create the `TopicCluster` model and build a backend service that sends revealed card texts to an LLM with structured output instructions. Generate suggested cluster titles along with card mappings to group similar ideas together automatically. Write tests with mocked LLM API responses to verify cluster generation, correct database mapping, and graceful error handling on API failure.

## 10. Manual Cluster Organization and Editing
Goal: Allow team members and facilitators to create, rename, delete, and manage clusters on the retrospective board.
Description: Implement endpoints and HTMX partial templates to allow creating new cluster containers, editing cluster titles inline, and deleting empty clusters. Provide a dedicated unclustered cards pool so cards removed from deleted clusters return to an accessible holding area. Write tests ensuring cluster CRUD operations persist correctly in the database and enforce project membership checks.

## 11. Drag-and-Drop Card Clustering with SortableJS
Goal: Enable users to drag cards between clusters and the unclustered pool with instant persistence via HTMX.
Description: Integrate SortableJS into the cluster board templates to make cluster columns and unclustered card containers interactive drop targets. Configure drop event handlers that trigger HTMX POST requests sending card IDs and target cluster IDs to a backend move endpoint. Add tests verifying that card-to-cluster associations update reliably in the database when move requests are received.

## 12. Secret Voting on Discussion Clusters
Goal: Allow team members to cast up to three stackable votes across clusters with vote totals hidden while voting is open.
Description: Implement the `ClusterVote` model and an HTMX voting widget where each member can distribute exactly three votes across clusters in any combination. Maintain vote secrecy by hiding live counts during the active voting stage, and expose total tallies only when the facilitator closes voting. Add unit tests verifying the three-vote maximum constraint per user and the masking of live counts.

## 13. Voting Close and Ranked Discussion Agenda
Goal: Conclude voting, calculate final vote tallies, and rank clusters into an ordered retrospective discussion agenda.
Description: Create the `DiscussionTopic` model and build a facilitator endpoint to close the voting phase and generate ranked discussion topics from cluster totals. Render the discussion agenda ordered from highest to lowest vote count with tie-breaking rules and tie counts displayed. Write tests verifying that closing voting calculates tallies accurately and populates discussion topics in proper priority order.

## 14. Interactive Discussion Management and In-Meeting Notes
Goal: Enable facilitators to advance through topics and allow participants to record status changes, notes, and decisions.
Description: Build the discussion stage interface where the facilitator can mark each topic as Discussed, Skipped, or Deferred. Add input fields to record shared meeting notes and draft decisions linked to individual discussion topics in real time using HTMX. Write unit tests ensuring topic status transitions and associated notes persist accurately in the database.

## 15. Django Channels Setup and Retrospective WebSocket Consumer
Goal: Configure Django Channels with Redis to manage WebSocket connections and room groups for retrospective sessions.
Description: Configure ASGI routing and the Redis channel layer in the Django settings for real-time WebSocket communication. Implement a `RetrospectiveConsumer` that authenticates incoming WebSocket connections, joins cycle-specific room groups, and handles disconnections cleanly. Add automated tests verifying WebSocket handshake authentication, room subscription, and channel layer message handling.

## 16. Client-Side Real-Time Board Synchronization
Goal: Broadcast board stage transitions, card cluster moves, and voting events live across all connected clients.
Description: Connect the retrospective template to the WebSocket consumer using the HTMX WebSocket extension or lightweight JavaScript event listeners. Dispatch channel group broadcasts from backend views whenever stage changes occur or cards are moved, triggering instant HTML swaps on connected clients. Write end-to-end or channel tests confirming that stage transitions and card movements propagate across multiple connected client sessions.

## 17. Meeting Record Ingestion (Upload Media and Paste Text)
Goal: Allow facilitators to upload meeting recordings, transcript files, or paste raw meeting transcript text.
Description: Implement the `MeetingRecord` model with file fields, text fields, and processing status tracking linked to a feedback cycle. Build an upload view supporting audio and video files (mp3, mp4, wav, m4a), transcript files (vtt, srt, txt), and a direct pasted-text input area. Write unit tests verifying upload validation for allowed file extensions, file size constraints, and database record creation.

## 18. Celery Task Infrastructure and Media Audio Extraction
Goal: Set up the Celery background worker and implement audio extraction from uploaded video files using ffmpeg.
Description: Configure Celery with Redis as the message broker and result backend within the Django project settings. Implement a background task that inspects newly uploaded meeting records and extracts a standardized mono audio track using ffmpeg when video files are uploaded. Write unit tests with mocked ffmpeg system commands to verify task dispatching and file extraction logic.

## 19. Asynchronous Whisper Speech-to-Text Transcription
Goal: Transcribe extracted meeting audio files in the background using the Whisper API and update meeting records.
Description: Implement a Celery task that takes extracted audio files, chunks audio if necessary, and calls the Whisper API to generate full text transcripts. Store the resulting transcript text on the `MeetingRecord` model and update the status to indicate transcription completion or record failure details. Add tests with mocked Whisper API responses verifying transcript storage, status progression, and error handling.

## 20. AI Structured Extraction for Decisions, Actions, and Summary
Goal: Extract draft decisions, action items with owners and due dates, and an executive summary from meeting transcripts.
Description: Implement the `ActionItem` and `Decision` models and create a Celery task that parses the meeting transcript against discussion topics using an LLM. Use structured outputs (via Instructor or Pydantic) to extract draft action items with suggested owners and due dates alongside an executive summary. Write tests with mocked LLM outputs verifying that extracted items are saved in an unconfirmed draft state.

## 21. Facilitator Outcome Review and Confirmation Interface
Goal: Provide an interface for facilitators to review, edit, confirm, or reject draft AI-generated decisions and action items.
Description: Build a review view displaying draft summary text, decisions, and action items with inline edit and delete controls. Allow facilitators to adjust descriptions, assign verified team members as owners, set due dates, and mark validated items as confirmed. Add tests verifying that only confirmed items become active and unconfirmed drafts are excluded from final output.

## 22. Published Retrospective Summary View
Goal: Display a permanent, read-only retrospective summary including topics, notes, decisions, actions, and original submissions.
Description: Implement the retrospective summary view showing the confirmed meeting summary, prioritized topics with notes, confirmed decisions, action items, and original feedback cards. Restrict view access to project members and render a clean, printable layout styled with Tailwind CSS. Include tests confirming that unconfirmed drafts are hidden and that anonymous feedback cards retain their anonymity on the summary.

## 23. Project Action Items Dashboard and Status Updates
Goal: Allow team members to view and update open action items directly from the project dashboard.
Description: Build an action items panel on the main project page that lists all open and completed actions associated with recent feedback cycles. Enable assigned owners to toggle action status between Open and Done using an HTMX request that updates the item in place. Write tests verifying that users can update their assigned action items and that status transitions reflect accurately on the project dashboard.
