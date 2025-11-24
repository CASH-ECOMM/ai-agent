# AI agent
The AI agent feature for the auctioning system

## Quick Start

### 1. Setup Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your configuration (LLM credentials, etc.)

### 2. Running with CLI

**Install dependencies:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**Run the API agent:**
```bash
python -m app.agents.api_agent.api_agent
```

**Run the SQL agent:**
```bash
python -m app.agents.sql_agent.sql_agent
```

**Run the Supervisor Agent V2 (Sequential Flow):**
```bash
python -m app.agents.supervisor_agent.supervisor_agent_v2
```

The Supervisor Agent V2 implements a sequential flow where:
- API agent is tried first for all requests
- SQL agent is used as fallback when API agent cannot fulfill the request

See [docs/SUPERVISOR_AGENT_V2.md](docs/SUPERVISOR_AGENT_V2.md) for details.

# ----- **UNDER CONSTRUCTION** -----

**Run the service:**
```bash
uvicorn app/main:app --host 0.0.0.0 --port 8080
```

Service will start on `localhost:8080`

### 3. Running with Docker

```bash
docker compose up
```

This starts AI agent service in a Docker.

## Features

### Multi-Agent System
- **API Agent**: Handles direct API operations (create items, place bids, get auction info)
- **SQL Agent**: Executes complex database queries for analytics and reporting
- **Supervisor Agent V2**: Sequential flow coordinator (API first, SQL as fallback)

### Key Capabilities
- Create and manage auction items
- Place and track bids
- Query auction statistics and analytics
- Natural language to SQL conversion
- Automatic fallback for complex queries

## Testing

Run unit tests:
```bash
PYTHONPATH=/home/runner/work/ai-agent/ai-agent python tests/test_supervisor_v2_unit.py
```

## Tech Stack
