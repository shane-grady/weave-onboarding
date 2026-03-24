# Weave Fabric — Magic Onboarding

Weave Fabric is a mobile-first consumer app that connects everyday apps and turns activity across them into useful memories. This project builds a magic onboarding experience: when a user signs up, the system already knows who they are — their name, where they work, what they do — without the user having to tell it anything.

## How It Works

1. **Connect Gmail** — User authenticates with their Gmail account via OAuth
2. **Research** — An AI agent analyzes Gmail profile, contacts, and web presence to build a personal profile
3. **Reveal** — Discovered insights are presented with a warm, typewriter-style animation

### Architecture

```
Frontend (React + Vite)  →  Backend (FastAPI + LangGraph)  →  Composio (Gmail + Web Search)
                                      ↕
                              Claude Sonnet 4 (AI Model)
```

- **Frontend**: React 19, TypeScript, Tailwind CSS 4, Vite
- **Backend**: FastAPI, Python, LangGraph, LangChain
- **AI Model**: Claude Sonnet 4 (Anthropic)
- **Integration**: Composio (Gmail OAuth, web search, contacts)
- **Storage**: In-memory (MVP)

### Research Pipeline

The agent executes a 3-phase research process:

1. **Identity Anchor** — Gmail profile provides authoritative name + email
2. **Targeted Web Research** — Multiple searches combining name, email, company
3. **Deep Research** — Portfolio sites, social profiles, press mentions, side projects

## Getting Started

### Prerequisites

- Node.js 20.19+ or 22.12+
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Anthropic API key
- Composio account + API key + Gmail auth config

### Backend Setup

```bash
cd poke-backend
cp .env.example .env
# Fill in your API keys in .env

uv sync
uv run python main.py
```

Backend runs at `http://localhost:8000`.

### Frontend Setup

```bash
cd poke-frontend
cp .env.example .env
# Fill in your auth config ID in .env

npm install
npm run dev
```

Frontend runs at `http://localhost:5173`.

### Environment Variables

**Backend** (`poke-backend/.env`):
| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key for Claude |
| `COMPOSIO_API_KEY` | Your Composio platform API key |
| `COMPOSIO_AUTH_CONFIG_ID` | Gmail OAuth auth config ID from Composio |

**Frontend** (`poke-frontend/.env`):
| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | Backend URL (default: `http://localhost:8000`) |
| `VITE_AUTH_CONFIG_ID` | Same Gmail auth config ID from Composio |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/users` | Create a new user |
| `POST` | `/connections/initiate` | Start Gmail OAuth flow |
| `GET` | `/connections/{id}/status` | Check OAuth completion |
| `POST` | `/research/{user_id}` | Trigger user research |
| `GET` | `/research/{user_id}/status` | Poll research progress |
| `GET` | `/health` | Health check |

## Customization

- **Agent prompts**: `poke-backend/server/agent.py` — modify research strategy and output format
- **UI components**: `poke-frontend/src/components/` — ConnectScreen, LoadingScreen, RevealScreen
- **Styling**: `poke-frontend/src/index.css` — colors, animations, typography
- **Tools**: `poke-backend/server/tools.py` — add/remove Composio tools
