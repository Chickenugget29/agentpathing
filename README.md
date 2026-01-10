# MPRG - Multi-Path Reasoning Guard

A safety gate that validates agent reasoning robustness by detecting whether multiple **distinct** reasoning paths support a plan — not just surface-level agreement.

## 🔑 Core Concept

Before an agent acts, MPRG checks whether there are **multiple different ways** to justify the plan — not just multiple agents saying the same thing.

## ⚡ Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy and edit environment file
cp .env.example .env

# Add your API keys:
# VOYAGE_API_KEY=your_voyage_key
# OPENAI_API_KEY=your_openai_key (fallback)
# MONGODB_URI=mongodb+srv://... (optional for persistence)
```

### 3. Run the Server

```bash
python server.py
```

### 4. Open Demo UI

Open `web/index.html` in browser or visit http://localhost:5000

## 🏗️ Architecture

```
Task → Multi-Agent Runner (5 agents) → Responses
         ↓
┌─────────────────────────────────────────┐
│ Layer 1: Symbolic FOL    │ Layer 2: Embeddings │
│ translator.py            │ ChromaDB            │
└─────────────────────────────────────────┘
         ↓
Dual-Layer Family Grouper → Reasoning Families
         ↓
Robustness Scorer → FRAGILE | MODERATE | ROBUST
         ↓
Execution Gate → BLOCK | WARN | ALLOW
```

## 📊 Scoring

| Families | Score | Action |
|----------|-------|--------|
| 1 | FRAGILE | 🛑 BLOCK |
| 2 | MODERATE | ⚠️ WARN |
| 3+ | ROBUST | ✅ ALLOW |

## 🗄️ MongoDB Atlas Use Case

MongoDB Atlas is the **reasoning state engine**:

1. **Durable Storage**: Persist all reasoning traces across sessions
2. **Crash Recovery**: Reload agent state after failures
3. **Historical Analysis**: Track fragile patterns over time
4. **Demo Replay**: Show complete analysis history to judges

## 📁 Project Structure

```
agentpathing/
├── translator.py    # FOL translator (existing)
├── planner.py       # Planning agent (existing)
├── main.py          # CLI (existing)
├── server.py        # Flask API
├── mprg/            # MPRG core
│   ├── runner.py    # Multi-agent execution
│   ├── analyzer.py  # Dual-layer analysis
│   ├── grouper.py   # Family detection
│   ├── scorer.py    # Robustness scoring
│   ├── gate.py      # Execution gate
│   ├── vectors.py   # ChromaDB embeddings
│   ├── db.py        # MongoDB integration
│   └── pipeline.py  # Main orchestration
└── web/
    └── index.html   # Demo UI
```

## 🎬 Demo Flow

1. Enter task: "Plan a 3-hour workflow to sync data across APIs"
2. Watch 5 agents generate plans
3. See FOL translations of reasoning
4. View reasoning families (clustered by similarity)
5. Get robustness score: FRAGILE / MODERATE / ROBUST
6. See gate decision: BLOCK / WARN / ALLOW

## 🏆 Why This Wins

- **Impact**: Prevents costly agent failures
- **Creativity**: Nobody else is doing multi-path reasoning validation
- **MongoDB**: Deep integration for reasoning memory
- **Visual**: Clear, intuitive demo
