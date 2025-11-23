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

**Run the API agent**
```bash
cd /Users/david_zinkiv/eecs4413/ai-agent
python -m app.agents.api_agent.api_agent
```


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


## Tech Stack
