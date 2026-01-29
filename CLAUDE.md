# Athletics Annual Plan

Web app for generating 52-week periodized training plans for track & field athletes.

## Architecture

This is a **two-server architecture**:

1. **Frontend** (`src/pages/`) - Static site served by Cloudflare Pages (dev: wrangler on port 8788)
2. **Backend** (`backend/`) - FastAPI Python server (dev: uvicorn on port 8000)

The frontend makes API calls to the backend. In development, `src/pages/scripts/config.js` routes requests to `localhost:8000`.

## Running Locally

**You must run BOTH servers in separate terminals:**

### Terminal 1: Backend (FastAPI)
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### Terminal 2: Frontend (Wrangler)
```bash
npm run dev
# Or: npx wrangler pages dev src/pages --kv INVITE_CODES --port 8788
```

Then open http://localhost:8788

### When Claude starts servers in background

When running servers via Claude Code, backend logs are written to `backend.log` in the project root. After starting the backend, Claude should print:

```
To view backend logs:
less +F backend.log
```

The user can run this in a separate terminal to watch logs. Press `Ctrl+C` to stop following and scroll, then `Shift+F` to resume following.

### Test Invite Codes
- `SPRINT2025` - 100 uses
- `COACH2025` - 50 uses
- `TEST` - 1000 uses (best for development)

## Testing

### Backend Tests
```bash
cd backend
source venv/bin/activate
pytest tests/ -v
```

### Frontend
No automated tests. Manual testing via the browser.

## Key Files

### Frontend (`src/pages/`)
- `app.html` - Main application page (3-step wizard)
- `scripts/app.js` - Application controller, step navigation, API calls
- `scripts/spreadsheet.js` - Excel preview using xlsx-preview library
- `scripts/config.js` - API base URL (localhost:8000 in dev, worker in prod)
- `styles/main.css` - All styles including dark theme

### Backend (`backend/app/`)
- `main.py` - FastAPI entry point, CORS config
- `routers/plan.py` - `/api/generate-plan`, `/api/download-excel`
- `routers/competitions.py` - `/api/search-competitions`
- `routers/auth.py` - `/api/validate-code`
- `services/excel_generator.py` - openpyxl Excel generation (styling source of truth)
- `services/plan_generator.py` - Claude tool_use schema for plan generation

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/validate-code` | Validate invite codes |
| `POST /api/generate-plan` | Generate 52-week plan via Claude |
| `POST /api/download-excel` | Generate styled Excel file from plan |
| `POST /api/search-competitions` | Search competitions via Claude |

## Dependencies

### Backend
- Python 3.11+
- FastAPI, uvicorn
- anthropic SDK (Claude API)
- openpyxl (Excel generation)
- SQLAlchemy + aiosqlite

### Frontend
- No build step (vanilla JS modules)
- CDN dependencies: ExcelJS, xlsx-preview, marked, DOMPurify

## Environment Variables

Backend requires `backend/.env`:
```
CLAUDE_API_KEY=sk-ant-...
DATABASE_URL=sqlite+aiosqlite:///./athletics.db
```

Frontend uses `/.dev.vars` for wrangler (KV binding for invite codes).
