# DepMigrant AI

**Autonomous Dependency Migration Engineer**

DepMigrant AI inspects Python repositories, prepares dependency-migration plans, and can report verification evidence. Repository command execution is disabled by default because a copied working directory is not an operating-system sandbox.

## Features

- **Repository Inspection**: Analyze Python projects (pip, uv, pyproject.toml, requirements files)
- **Migration Planning**: Generate structured plans with breaking changes, affected files, and risks
- **Baseline Testing**: Captures pre-migration state when execution is explicitly enabled
- **Model-Driven Migration**: Use NVIDIA Nemotron via Nebius for intelligent code modifications
- **Guarded Execution**: Repository command execution is blocked by default
- **Failure Diagnosis**: Classifies command errors and proposes minimal repairs
- **Controlled Repair Loop**: Bounded repair attempts when execution is explicitly enabled
- **Independent Verification**: Evidence-based verification using test results
- **Comprehensive Reporting**: Human-readable and machine-readable reports

## Architecture

```
depmigrant-ai/
├── apps/
│   └── web/                 # Next.js frontend dashboard
├── services/
│   └── api/                 # FastAPI backend
├── tests/
│   ├── unit/
│   ├── integration/
│   └── safety/
├── docs/
├── .env.example
├── pyproject.toml
├── LICENSE
└── README.md
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Nebius API credentials (for NVIDIA Nemotron model)

### Installation

```bash
# Backend dependencies (from the project root)
pip install -e services/api

# Frontend dependencies (apps/web currently has no lockfile)
cd apps/web
npm install
```

### Configuration

```bash
cp .env.example .env
# Edit .env and configure either NEBIUS_API_KEY or NVIDIA_NIM_API_KEY
```

### Running

```bash
# Terminal 1: Backend (from the project root)
PYTHONPATH=services/api uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2: Frontend
cd apps/web
npm run dev
```

Open http://localhost:3013

## Render API and Vercel frontend deployment

The API is served by `app.main:app`; its health endpoint is `GET /health`.
The SQLite default remains under the user's home directory for local development.
On Render, when `DATABASE_URL` is unset, the API uses `/tmp/depmigrant.db`.
That filesystem is ephemeral and the database can be lost when the service restarts
or is redeployed. Use a persistent managed database and set `DATABASE_URL` for
production data; do not rely on the temporary SQLite file for persistence.

For a Render web service with the repository root as its Root Directory, use:

```text
Build Command: pip install .
Start Command: uvicorn app.main:app --app-dir services/api --host 0.0.0.0 --port $PORT
```

Set backend secrets and optional database configuration in the Render service
environment, not in source control:

- `NEBIUS_API_KEY`, `NEBIUS_BASE_URL`, and `NEBIUS_MODEL` for the configured
  Nebius provider, or the corresponding `NVIDIA_NIM_*` variables for NVIDIA NIM.
- `DATABASE_URL` only when overriding the default SQLite URL; use a persistent
  database URL for production.

For the Vercel frontend, set `NEXT_PUBLIC_API_URL` to the Render API service's
public origin (scheme and host, without `/api`). Next.js uses it for the `/api/*`
and `/health` rewrites; if unset during local development, the frontend targets
`http://localhost:8000`. Configure the value in Vercel and redeploy after changes.
Do not put provider API keys in Vercel frontend environment variables.

## NVIDIA Nemotron + Nebius Integration

DepMigrant AI uses **NVIDIA Nemotron 3 Ultra** via **Nebius AI Studio** for:
- Migration planning and breaking change analysis
- Code modification proposals
- Failure diagnosis and repair suggestions

The integration is in `services/api/app/services/nebius_client.py`.

## Security

- Repository command execution is disabled by default. A copied repository is not OS-level isolation.
- The backend binds to `127.0.0.1` by default and has no authentication; do not expose it to a network.
- Planning and failure-diagnosis requests send repository metadata and selected source/error context to the configured model provider. Do not use proprietary repositories without approval.
- Do not enable `ALLOW_UNSAFE_REPOSITORY_EXECUTION` for untrusted repositories. Enabling it allows repository/package commands to run with the backend user's filesystem and network permissions.
- API keys must be supplied through the root `.env` file or environment variables and must not be committed.

See [docs/SECURITY.md](docs/SECURITY.md) for limitations and the demo-safe workflow.

## Testing

```bash
# Unit tests
pytest tests/unit/
```

Integration and dedicated safety test suites have not been added yet.

## License

MIT License - see LICENSE file
