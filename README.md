# Athletics Annual Plan

A web application for generating 52-week periodized training plans for track and field athletics. Built on Cloudflare's free tier.

## Features

- **AI-Powered Planning**: Chat with Claude to refine your training plan
- **52-Week Structure**: Complete periodization from General Prep through Competition
- **Excel Export**: Download professionally formatted spreadsheets
- **Invite Code System**: Control access with managed invite codes

## Architecture

- **Frontend**: Static HTML/CSS/JS on Cloudflare Pages
- **Backend**: Cloudflare Pages Functions for API
- **Storage**: Cloudflare KV for invite codes
- **Excel**: Browser-side generation using ExcelJS (CDN)
- **AI**: Claude API (proxied through Pages Functions)

## Setup

### Prerequisites

- [Node.js](https://nodejs.org/) 18+
- [Wrangler CLI](https://developers.cloudflare.com/workers/wrangler/install-and-update/)
- Cloudflare account (free tier works)
- Anthropic API key

### 1. Install Dependencies

```bash
npm install
```

### 2. Create KV Namespace

```bash
# Create KV namespace
npx wrangler kv:namespace create INVITE_CODES
```

Copy the namespace ID from the output and update `wrangler.toml`:

```toml
[[kv_namespaces]]
binding = "INVITE_CODES"
id = "your-namespace-id-here"
```

### 3. Set API Key Secret

For local development, create a `.dev.vars` file:

```
CLAUDE_API_KEY=your-api-key-here
```

For production, set the secret:

```bash
npx wrangler pages secret put CLAUDE_API_KEY --project-name athletics-annual-plan
# Enter your Anthropic API key when prompted
```

### 4. Create Invite Codes

First create the Pages project (needed for the manage-codes script):

```bash
# Create initial deployment
npm run deploy
```

Then create invite codes:

```bash
# Create a code with unlimited uses
npm run codes create SPRINT2025

# Create a code with limited uses
npm run codes create CLUB2025 --max-uses 50

# List all codes
npm run codes list
```

### 5. Local Development

```bash
npm run dev
```

Visit http://localhost:8788

Note: You'll need to create a test invite code first, or temporarily bypass validation for local testing.

### 6. Deploy

```bash
npm run deploy
```

## Project Structure

```
athletics-annual-plan/
├── src/
│   ├── pages/              # Static HTML pages (served by Pages)
│   │   ├── index.html      # Landing page with invite code
│   │   ├── app.html        # Main application
│   │   └── _routes.json    # Pages routing config
│   ├── styles/
│   │   └── main.css        # All styles
│   └── scripts/
│       ├── app.js          # Main application controller
│       ├── chat.js         # Chat interface with Claude
│       ├── excel.js        # Excel generation with ExcelJS
│       └── system-prompt.js # Claude system prompt
├── functions/
│   └── api/
│       ├── chat.js         # POST /api/chat - Claude proxy
│       └── validate-code.js # POST /api/validate-code
├── scripts/
│   └── manage-codes.js     # CLI for invite code management
├── wrangler.toml           # Cloudflare Pages configuration
└── package.json
```

## Invite Code Management

```bash
# Create codes
npm run codes create <CODE>
npm run codes create <CODE> --max-uses 10

# List all codes
npm run codes list

# View code details
npm run codes info <CODE>

# Activate/deactivate
npm run codes activate <CODE>
npm run codes deactivate <CODE>

# Delete a code
npm run codes delete <CODE>
```

## Training Plan Structure

The generated Excel plan includes:

| Row | Content |
|-----|---------|
| Month | Timeline headers |
| Week | Numbers 1-52 |
| Competitions | Events and importance ratings |
| Phases | Color-coded (Orange/Yellow/Green/Grey) |
| Technical | Technical focus areas |
| Physical | Physical development focus |
| Blocks | Training block names |
| Training Load | 0-4 scale with colors |

### Phase Colors

- **Orange**: General Prep phases
- **Yellow**: Special Prep phases
- **Green**: Competition phases
- **Grey**: Taper/Recovery phases

### Training Load Scale

- **4** (Red): High load
- **3** (Orange): Medium-high
- **2** (Yellow): Medium
- **1** (Green): Low/taper
- **0** (White): Rest/competition

## Environment Variables

| Variable | Description |
|----------|-------------|
| `CLAUDE_API_KEY` | Anthropic API key (set as Pages secret) |
| `CORS_ORIGIN` | Allowed origin for CORS (optional) |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/validate-code` | POST | Validate invite code, returns session ID |
| `/api/chat` | POST | Proxy messages to Claude API |

## License

MIT
