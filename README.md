# MPRG - Multi-Path Reasoning Guard

A safety gate that validates agentic workflows by checking whether **multiple distinct reasoning families** support a plan or answer — not just surface-level agreement.

## 🔑 Core Concept

Before an agent acts, MPRG checks if there are **different reasoning paths** behind the output, not just multiple agents saying the same thing.

## ✅ What This Build Includes

- Parallel multi-agent runs (3–5 roles) with strict JSON ReasoningSummary outputs
- Validation + retry (JSON-only on failure)
- Reasoning family clustering with:
  - plan embedding cosine similarity
  - assumption overlap (Jaccard)
- Robustness status:
  - 1 family → FRAGILE
  - 2+ families → ROBUST
- MongoDB Atlas as system-of-record (tasks, runs, families)
- Restart-safe clustering (resume from stored runs)
- Minimal API + demo UI

## ⚡ Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env

# Required
OPENAI_API_KEY=your_openai_key_here
MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/mprg?retryWrites=true&w=majority

# Optional overrides
OPENAI_MODEL=gpt-4o-mini
AGENT_COUNT=4
PLAN_SIM_THRESHOLD=0.85
ASSUMPTION_SIM_THRESHOLD=0.70
```

### 3. Run the Server

```bash
python server.py
```

### 4. Open Demo UI

Open `web/index.html` in your browser.

## 🧩 Reasoning Guard Generator (Standalone)

This module runs diverse agents and returns a JSON TaskBundle without touching MongoDB.

```bash
python generator_server.py
```

POST to `/generate`:

```json
{
  "user_prompt": "Plan a 3-hour workflow to sync data across APIs."
}
```

Response: `TaskBundle` with `runs[]` including strict `ReasoningSummary` JSON.

### Using Anthropic Instead of OpenAI

Set the provider and key in `.env`:

```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_anthropic_key_here
ANTHROPIC_MODEL=claude-3-5-sonnet-20240620
ANTHROPIC_API_BASE=https://api.anthropic.com
```

Install the SDK:

```bash
pip install anthropic
```

## 📡 API

- `POST /tasks`
  - Body: `{ "task": "Your task prompt" }`
  - Response: `{ "task_id": "..." }`
- `GET /tasks/:id`
  - Task status + robustness metrics
- `GET /tasks/:id/runs`
  - Raw agent runs (ReasoningSummary + validity)
- `GET /tasks/:id/families`
  - Reasoning families + representative signatures

## 🗄️ MongoDB Collections

- `tasks`: task prompt, created_at, status, robustness metrics
- `runs`: agent outputs + ReasoningSummary + embeddings + validity
- `families`: clustering results + family signature + robustness metrics

## 📁 Project Structure

```
agentpathing/
├── server.py             # Flask API
├── mprg/
│   ├── agent_runner.py   # Multi-agent LLM runner (JSON enforced)
│   ├── models.py         # ReasoningSummary schema + validation
│   ├── embeddings.py     # Plan embeddings + cosine similarity
│   ├── cluster.py        # Family clustering logic
│   ├── orchestrator.py   # End-to-end orchestration + resume
│   └── store.py          # MongoDB persistence
└── web/
    └── index.html        # Demo UI
```

## 🧪 Demo Flow

1. Enter a task prompt in the UI
2. Watch 3–5 agent runs execute in parallel
3. MPRG clusters reasoning families
4. See robustness status + answer agreement

## 📜 License

MIT (or your preferred open-source license).
