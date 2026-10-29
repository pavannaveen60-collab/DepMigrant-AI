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

Open http://localhost:3000

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