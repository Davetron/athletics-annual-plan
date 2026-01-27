# Athletics Annual Plan - Python Backend

FastAPI backend for generating 52-week periodized training plans for track & field athletes.

## Setup

### Prerequisites

- Python 3.11+
- An Anthropic API key

### Installation

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the `backend/` directory:

```env
CLAUDE_API_KEY=sk-ant-your-api-key-here
DATABASE_URL=sqlite+aiosqlite:///./athletics.db
```

### Running the Server

```bash
# Development mode with auto-reload
uvicorn app.main:app --reload --port 8000

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`.

## Running with Frontend

1. Start the backend:
   ```bash
   cd backend
   source venv/bin/activate
   uvicorn app.main:app --reload --port 8000
   ```

2. Start the frontend (in another terminal):
   ```bash
   npx wrangler pages dev src/pages --port 8788
   ```

3. Open `http://localhost:8788` in your browser.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/validate-code` | POST | Validate invite codes |
| `/api/chat` | POST | Claude conversation proxy |
| `/api/generate-plan` | POST | Generate 52-week plan using Claude tool_use |
| `/api/fetch-url` | POST | Fetch federation calendars |
| `/api/search-competitions` | POST | Search competitions via Claude web search |
| `/api/download-excel` | POST | Generate Excel file from plan |

## Default Invite Codes

The database is seeded with these test codes:

- `SPRINT2025` - 100 uses
- `COACH2025` - 50 uses
- `TEST` - 1000 uses

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Settings from environment
│   │
│   ├── routers/
│   │   ├── auth.py          # /api/validate-code
│   │   ├── chat.py          # /api/chat
│   │   ├── plan.py          # /api/generate-plan, /api/download-excel
│   │   └── competitions.py  # /api/search-competitions, /api/fetch-url
│   │
│   ├── services/
│   │   ├── rate_limiter.py     # In-memory rate limiting
│   │   ├── invite_codes.py     # Database operations
│   │   ├── plan_generator.py   # Claude tool schema
│   │   └── excel_generator.py  # openpyxl Excel generation
│   │
│   └── models/
│       ├── database.py      # SQLAlchemy models
│       └── schemas.py       # Pydantic request/response
│
├── tests/
│   └── test_e2e.py          # End-to-end API tests
│
├── requirements.txt
└── README.md
```

## Running Tests

```bash
cd backend
source venv/bin/activate

# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/ -v
```

## Rate Limits

- Chat endpoint: 10 requests/minute per session
- Plan generation: 5 requests/minute per session

## Technology Stack

- **FastAPI** - Modern async Python web framework
- **SQLAlchemy 2.0** - Async ORM with aiosqlite
- **Anthropic SDK** - Claude API integration
- **openpyxl** - Excel file generation
- **Pydantic** - Data validation and settings
