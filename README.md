# Weekly Team Feedback Tool

A team collaboration platform to collect weekly feedback (Start, Stop, Continue), facilitate focused retrospectives, and document decisions and action items with AI assistance.

## Architecture & Design
Built as a Django monolith following the architecture documented in `_docs/architecture.md`:
- **Backend:** Python 3.11+, Django 5.x, ASGI via Daphne
- **Database:** PostgreSQL (production / Docker) with SQLite support for lightweight local testing
- **Real-Time:** Django Channels with Redis channel layer
- **Frontend:** Server-rendered Django Templates with HTMX 2.x, Alpine.js 3.x, and SortableJS
- **Async Workers & AI:** Celery, Redis, Whisper transcription, and LLM structured extraction

---

## Getting Started

### Prerequisites
- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) (recommended) or standard Python `venv` + `pip`

### 1. Environment Setup

Clone the repository and navigate to the project root:
```bash
git clone https://github.com/parnamijanesh-creator/project-feedback.git
cd project-feedback
```

Create and activate a virtual environment (Python 3.11+):
```bash
# Using uv (recommended)
uv venv --python 3.11 .venv
source .venv/bin/activate

# Or using standard python3
python3.11 -m venv .venv
source .venv/bin/activate
```

Install dependencies from `pyproject.toml`:
```bash
# Using uv
uv pip install -e ".[dev]"

# Or using pip
pip install -e ".[dev]"
```

### 2. Database Migrations

Apply initial Django migrations:
```bash
python manage.py migrate
```

### 3. Run Development Server

Start the local Django server:
```bash
python manage.py runserver
```

The application will be accessible at `http://127.0.0.1:8000/`.

### 4. Health Check Endpoint

Verify the baseline service is operational:
```bash
curl http://127.0.0.1:8000/health/
```
Expected response:
```json
{"status": "healthy"}
```

---

## Running Automated Tests

Run the test suite using Django's built-in test runner:
```bash
python manage.py test
```

Or using `pytest`:
```bash
pytest
```

---

## Project Structure

```text
.
├── config/                     # Configuration and entry points
│   ├── settings/
│   │   ├── base.py             # Shared settings across all environments
│   │   ├── local.py            # Local development settings (default)
│   │   └── production.py       # Production hardened settings
│   ├── asgi.py                 # ASGI application (Daphne/Channels)
│   ├── wsgi.py                 # WSGI application
│   ├── urls.py                 # Root URL routing
│   └── views.py                # Core project views (health check)
├── tests/                      # Automated smoke and integration tests
├── static/                     # Static assets (CSS/JS/images)
├── templates/                  # Server-rendered HTML templates
├── manage.py                   # Django management script
├── pyproject.toml              # Unified dependency management & project metadata
└── README.md                   # Setup guide and instructions
```
