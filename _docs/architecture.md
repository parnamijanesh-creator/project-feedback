# System Architecture: Weekly Team Feedback Tool (Django Monolith)

## 1. Executive Summary & Philosophy

This document defines the concrete architecture for the **Weekly Team Feedback Tool** MVP based on [_docs/plan.md](plan.md), using **Option 3: Django Full-Stack Monolith** with **HTMX**, **Alpine.js**, **Django Channels**, and **Celery**.

### Core Architecture Philosophy
- **Unified Language (Python-First):** Single backend and data ecosystem for business logic, asynchronous task execution, and AI/audio processing pipelines.
- **Low Frontend Overhead, High Interactivity:** Server-rendered Django templates enhanced with HTMX for responsive partial updates, Alpine.js for client-side widget state, and SortableJS for drag-and-drop card clustering.
- **Real-Time Collaboration:** ASGI with Django Channels and Redis for broadcasting board phase transitions, card reveals, and synchronized meeting updates.
- **Resilient Media & AI Processing:** Asynchronous Celery workers handle heavy media uploads, speech-to-text transcription (Whisper), and LLM structured extraction without blocking HTTP request threads.

---

## 2. High-Level Architecture Diagram

```
                                  [ Client Browsers ]
                                    (Team & Facilitator)
                                            │
                                            │ HTTP (HTML / HTMX)
                                            │ & WebSockets (ASGI)
                                            ▼
                                   ┌─────────────────┐
                                   │  Reverse Proxy  │ (Nginx / Traefik)
                                   └────────┬────────┘
                                            │
                    ┌───────────────────────┴───────────────────────┐
                    ▼                                               ▼
         [ Django HTTP / WS (Daphne / ASGI) ]           [ Static & Media Assets ]
                    │                                   (Whitenoise / Local or S3)
                    ├───────────────────────┐
                    ▼                       ▼
           [ PostgreSQL 16 ]         [ Redis 7.x ]
            - Core Business Data      - Channels Layer (WS)
            - Retrospective State     - Celery Message Broker
            - Audit & Actions         - Result Backend
                                            │
                                            ▼
                                  [ Celery Worker Pool ]
                                            │
                        ┌───────────────────┴───────────────────┐
                        ▼                                       ▼
             [ Audio / Video Pipeline ]               [ LLM Extraction Engine ]
             - Local / Cloud Whisper                  - Semantic Clustering
             - Transcript Normalization               - Decisions & Action Items
```

---

## 3. Technology Stack

| Layer | Component | Choice | Justification |
| :--- | :--- | :--- | :--- |
| **Language** | Python | 3.11+ | High performance, native typing, standard for AI tooling. |
| **Framework** | Django | 5.x | Batteries-included ORM, auth, admin interface, and robust migrations. |
| **ASGI / Real-Time** | Django Channels + Daphne | Channels 4.x + Redis Layer | Native WebSocket support for live board synchronization. |
| **Frontend Rendering** | Django Templates + HTMX | HTMX 2.x | Server-driven UI updates with zero heavy JS bundling. |
| **Client UI Logic** | Alpine.js & SortableJS | Alpine 3.x + SortableJS | Lightweight reactivity (modals/toggles) and drag-and-drop card clustering. |
| **Styling** | Tailwind CSS | v3.x / v4.x (Standalone CLI) | Utility-first responsive design, fast iteration. |
| **Database** | PostgreSQL | 16+ | Relational integrity, JSONB support for drafts/metadata. |
| **Cache & Broker** | Redis | 7.x | Dual-purpose: Channels WebSocket pub/sub + Celery task broker. |
| **Background Tasks**| Celery | 5.x | Industrial-grade task queue for media and AI workloads. |
| **Media Storage** | Local filesystem / S3 | `django-storages` + MinIO/S3 | Handles audio/video files and generated transcripts. |
| **Speech-to-Text** | Whisper | OpenAI API / `faster-whisper` | Robust multilingual transcription of uploaded recordings. |
| **LLM & Extraction**| OpenAI / Gemini / Anthropic | Instructor / Pydantic v2 | Guaranteed JSON schema outputs for decisions and action items. |

---

## 4. Application Structure (Django Apps)

The project will follow a modular domain-driven Django structure:

```
project_feedback/
├── manage.py
├── config/                         # Project settings & ASGI/WSGI entry points
│   ├── settings/
│   │   ├── base.py
│   │   ├── local.py
│   │   └── production.py
│   ├── asgi.py                     # Protocol routing (HTTP + WebSockets)
│   ├── wsgi.py
│   ├── celery.py                   # Celery instance configuration
│   └── urls.py
│
├── apps/
│   ├── accounts/                   # User authentication & profiles
│   ├── projects/                   # Projects, team memberships, and roles
│   ├── cycles/                     # Feedback cycles & Start/Stop/Continue submissions
│   ├── retrospectives/             # Interactive board, stages, voting & discussion
│   ├── media_processor/            # Audio/video file uploads, Whisper transcription
│   └── ai_insights/                # LLM clustering and action item/decision extraction
│
├── static/
│   ├── css/input.css               # Tailwind source
│   ├── js/retro_board.js           # SortableJS + HTMX WebSocket helpers
│   └── vendor/                     # HTMX, Alpine.js, SortableJS vendors
├── templates/
│   ├── base.html
│   ├── components/                 # Reusable cards, badges, modals
│   ├── projects/
│   ├── cycles/
│   └── retrospectives/
│       ├── board.html              # Main board container
│       ├── stages/                 # Sub-templates for Reveal, Cluster, Vote, Discuss
│       └── summary.html
└── media/                          # Uploaded audio, video, transcripts
```

---

## 5. Domain Models & Database Schema

### 5.1 Projects & Users (`apps.projects`)
```python
class Project(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

class ProjectMember(models.Model):
    class Role(models.TextChoices):
        FACILITATOR = "FACILITATOR", "Facilitator"
        MEMBER = "MEMBER", "Team Member"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)

    class Meta:
        unique_together = ("project", "user")
```

### 5.2 Feedback Cycles & Submissions (`apps.cycles`)
```python
class FeedbackCycle(models.Model):
    class Status(models.TextChoices):
        COLLECTING = "COLLECTING", "Collecting Feedback"
        RETROSPECTIVE = "RETROSPECTIVE", "Retrospective in Progress"
        COMPLETED = "COMPLETED", "Completed"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="cycles")
    facilitator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    week_date = models.DateField(help_text="Target week start date")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COLLECTING)
    created_at = models.DateTimeField(auto_now_add=True)

class FeedbackCard(models.Model):
    class Category(models.TextChoices):
        START = "START", "Start"
        STOP = "STOP", "Stop"
        CONTINUE = "CONTINUE", "Continue"

    cycle = models.ForeignKey(FeedbackCycle, on_delete=models.CASCADE, related_name="cards")
    # For strict anonymity: user is set to NULL if is_anonymous=True upon submission,
    # or retained only in a separate unlinked verification table if needed.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    is_anonymous = models.BooleanField(default=False)
    category = models.CharField(max_length=10, choices=Category.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
```

### 5.3 Retrospective Board, Clusters & Voting (`apps.retrospectives`)
```python
class RetrospectiveSession(models.Model):
    class Stage(models.TextChoices):
        REVEAL = "REVEAL", "Reveal"
        CLUSTER = "CLUSTER", "Cluster"
        VOTE = "VOTE", "Vote"
        DISCUSS = "DISCUSS", "Discuss"
        CONCLUDED = "CONCLUDED", "Concluded"

    cycle = models.OneToOneField(FeedbackCycle, on_delete=models.CASCADE, related_name="retro_session")
    current_stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.REVEAL)
    is_voting_open = models.BooleanField(default=False)
    votes_per_user = models.PositiveSmallIntegerField(default=3)
    created_at = models.DateTimeField(auto_now_add=True)

class TopicCluster(models.Model):
    session = models.ForeignKey(RetrospectiveSession, on_delete=models.CASCADE, related_name="clusters")
    title = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)
    cards = models.ManyToManyField(FeedbackCard, blank=True, related_name="clusters")
    created_at = models.DateTimeField(auto_now_add=True)

class ClusterVote(models.Model):
    session = models.ForeignKey(RetrospectiveSession, on_delete=models.CASCADE, related_name="votes")
    cluster = models.ForeignKey(TopicCluster, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    count = models.PositiveSmallIntegerField(default=1)

    class Meta:
        unique_together = ("session", "cluster", "user")

class DiscussionTopic(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        DISCUSSED = "DISCUSSED", "Discussed"
        SKIPPED = "SKIPPED", "Skipped"
        DEFERRED = "DEFERRED", "Deferred"

    session = models.ForeignKey(RetrospectiveSession, on_delete=models.CASCADE, related_name="discussion_topics")
    cluster = models.OneToOneField(TopicCluster, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True)
    rank = models.PositiveIntegerField(default=0)
```

### 5.4 Meeting Records & AI Extraction (`apps.media_processor` & `apps.ai_insights`)
```python
class MeetingRecord(models.Model):
    class ProcessingStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        TRANSCRIBING = "TRANSCRIBING", "Transcribing"
        EXTRACTING = "EXTRACTING", "Extracting Outcomes"
        READY_FOR_REVIEW = "READY_FOR_REVIEW", "Ready for Facilitator Review"
        FAILED = "FAILED", "Failed"

    cycle = models.OneToOneField(FeedbackCycle, on_delete=models.CASCADE, related_name="meeting_record")
    media_file = models.FileField(upload_to="meeting_recordings/%Y/%m/", null=True, blank=True)
    raw_transcript = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=ProcessingStatus.choices, default=ProcessingStatus.PENDING)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class ActionItem(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        DONE = "DONE", "Done"

    cycle = models.ForeignKey(FeedbackCycle, on_delete=models.CASCADE, related_name="action_items")
    topic = models.ForeignKey(DiscussionTopic, null=True, blank=True, on_delete=models.SET_NULL)
    description = models.CharField(max_length=500)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    is_confirmed = models.BooleanField(default=False)  # Draft until facilitator approves

class Decision(models.Model):
    cycle = models.ForeignKey(FeedbackCycle, on_delete=models.CASCADE, related_name="decisions")
    topic = models.ForeignKey(DiscussionTopic, null=True, blank=True, on_delete=models.SET_NULL)
    description = models.TextField()
    is_confirmed = models.BooleanField(default=False)
```

---

## 6. Real-Time Interaction & Collaborative Board Architecture

The retrospective board requires real-time synchronization between the facilitator and team members:

```
[ Team Member Browser ]           [ Facilitator Browser ]
          │                                  │
          │ HTMX Card Drag Drop (SortableJS) │
          ├─────────────────────────────────>│ HTMX Trigger: Change Stage
          │                                  │ (e.g. Reveal -> Cluster)
          │                                  │
          ▼                                  ▼
[ Django HTTP View / API ]        [ Django HTTP View / API ]
          │                                  │
          ▼                                  ▼
   Update Database                    Update Database
          │                                  │
          └────────────────┬─────────────────┘
                           │
                           ▼
              [ Redis Channels Layer ]
             Group: `retro_{session_id}`
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
  [ WebSocket Consumer ]       [ WebSocket Consumer ]
   (Member Client)              (Facilitator Client)
             │                           │
             ▼                           ▼
   HTMX `hx-swap-oob`          HTMX `hx-swap-oob`
   Re-renders Board Region      Re-renders Board Region
```

### 6.1 Board Stages Workflow
1. **Stage 1: Reveal**
   - Before reveal: Query filters cards to `user=request.user` only.
   - Facilitator clicks **"Reveal Submissions"**: Facilitator view posts to endpoint.
   - Server transitions stage to `REVEAL`, broadcasts WebSocket message.
   - All connected clients swap HTML to render all submissions grouped by Start/Stop/Continue.
2. **Stage 2: Cluster**
   - Facilitator clicks **"Suggest Clusters (AI)"**: Enqueues quick background/inline LLM grouping.
   - UI displays clusters as drop zones.
   - **SortableJS** attaches to cluster columns. On drag end, fires an `htmx.ajax('POST', '/retros/cards/{id}/move/', {values: {cluster_id: target}})` request.
   - Server updates `TopicCluster.cards` and broadcasts update to all session participants via WebSocket.
3. **Stage 3: Vote**
   - Facilitator opens voting.
   - Each participant has 3 votes allocated.
   - Voting takes place via HTMX `hx-post` increment/decrement buttons.
   - **Privacy rule:** During voting, vote counts are masked. When voting closes, the server computes final sums and broadcasts the ranked order.
4. **Stage 4: Discuss**
   - Ordered list of clusters by vote count.
   - Facilitator toggles status (`Discussed`, `Skipped`, `Deferred`).
   - Facilitator / team inputs notes in real-time.

---

## 7. Media & AI Ingestion Pipeline

When a meeting recording (audio/video), transcript file (.vtt/.srt/.txt), or pasted text is submitted:

```
[ User Uploads File / Pastes Text ]
                 │
                 ▼
[ `MeetingUploadView` ] ──> Stores file in `media/meeting_recordings/`
                 │
                 ▼ (Enqueue)
         [ Celery Task Queue ]
                 │
                 ▼
  ┌────────────────────────────────────────────────────────┐
  │ Task 1: `transcribe_meeting_task(meeting_record_id)`   │
  │ - Inspects format (Audio/Video vs raw text)            │
  │ - If media: Extract audio (ffmpeg) -> Whisper API/local│
  │ - Updates `raw_transcript` on `MeetingRecord`          │
  └──────────────────────────┬─────────────────────────────┘
                             │
                             ▼
  ┌────────────────────────────────────────────────────────┐
  │ Task 2: `extract_retrospective_outcomes(record_id)`    │
  │ - Sends prompt with transcript + cluster topics to LLM │
  │ - Uses Instructor/Pydantic to parse JSON output:       │
  │     * Summary                                          │
  │     * Decisions                                        │
  │     * Action items (owner match, due date)             │
  │ - Populates `Decision` & `ActionItem` (is_confirmed=F) │
  │ - Sets status = `READY_FOR_REVIEW`                     │
  └──────────────────────────┬─────────────────────────────┘
                             │
                             ▼
  [ WebSocket Notification to Facilitator: "Review Ready" ]
```

### 7.1 LLM Output Schema (Pydantic / Instructor)
```python
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date

class ExtractedActionItem(BaseModel):
    description: str = Field(description="Action item description")
    suggested_owner_name: Optional[str] = Field(description="Name or handle of owner if mentioned")
    due_date: Optional[date] = Field(description="Target date if mentioned")
    related_topic_title: Optional[str] = Field(description="Associated discussion cluster")

class ExtractedDecision(BaseModel):
    description: str = Field(description="Decision agreed upon by the team")
    related_topic_title: Optional[str] = Field(description="Associated discussion cluster")

class RetrospectiveAnalysis(BaseModel):
    summary: str = Field(description="2-3 paragraph concise summary of the retrospective")
    decisions: List[ExtractedDecision]
    action_items: List[ExtractedActionItem]
```

---

## 8. Privacy & Anonymity Strategy

Adhering strictly to the requirement: *"Anonymous feedback stays anonymous; hidden administrator access would discourage honest feedback."*

1. **Database Layer Anonymization:**
   - When a user checks `Submit anonymously`, the `FeedbackCard.user_id` is set to `NULL` before saving, OR
   - The user reference is held in an encrypted session cookie only until the cycle enters `RETROSPECTIVE` stage, after which the correlation is purged.
   - No hidden audit logs or user foreign keys exist for anonymous cards in the database.
2. **Voting Integrity:**
   - Votes are tracked per user (`ClusterVote.user`) only to enforce the limit of 3 votes per person.
   - Individual vote allocations are never exposed in the UI or summary; only aggregated totals per cluster are displayed.

---

## 9. Local Development & Production Infrastructure

### 9.1 Docker Compose Services
```yaml
services:
  web:
    build: .
    command: daphne -b 0.0.0.0 -p 8000 config.asgi:application
    volumes:
      - .:/app
      - media_volume:/app/media
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgres://postgres:postgres@db:5432/feedback_db
      - REDIS_URL=redis://redis:6379/0
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - db
      - redis

  celery_worker:
    build: .
    command: celery -A config worker -l info --concurrency=2
    volumes:
      - .:/app
      - media_volume:/app/media
    environment:
      - DATABASE_URL=postgres://postgres:postgres@db:5432/feedback_db
      - REDIS_URL=redis://redis:6379/0
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - db
      - redis

  db:
    image: postgres:16-alpine
    environment:
      - POSTGRES_DB=feedback_db
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
  media_volume:
```

---

## 10. Verification & Quality Plan

1. **Unit & Model Tests:**
   - Test anonymity enforcement: verify `user_id` is null on anonymous card creation.
   - Test vote quotas: enforce maximum 3 votes per user in `ClusterVote` validation.
   - Test stage transitions: ensure non-facilitators cannot trigger stage changes.
2. **Integration & Real-Time Tests:**
   - Channels `ChannelsLiveServerTestCase` to test WebSocket connection, room joining, and broadcast events.
   - Test HTMX partial template responses using Django test client.
3. **AI Mocking in Tests:**
   - Mock Whisper API responses and Instructor LLM responses using pre-recorded mock fixtures for reproducible CI/CD execution.
