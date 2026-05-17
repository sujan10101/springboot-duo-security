# Agentic AI Recruitment Pipeline

**Author:** Sujan Khadka  
**Course:** Generative AI  
**Framework:** LangGraph · Claude Sonnet 4.5 · ChromaDB · OpenAI Embeddings

---

## Problem Statement

International students applying for internships receive hundreds of generic rejection emails with zero actionable feedback. This pipeline automates the recruiter side of screening — with one key difference: **rejections include specific, honest explanations** (grounded in the actual gap analysis), and **acceptances trigger automatic interview scheduling and tailored question generation**.

---

## Agent Architecture

```
START
  │
  ▼
┌─────────────────────────────────────────────────────┐
│  Agent 1: REVIEW AGENT                              │
│  • Embeds resume + JD → retrieves RAG context       │
│  • Scores resume (0–100) against rubric             │
│  • Produces structured GapAnalysis object           │
│    {strengths, skill_gaps, score, deciding_factor}  │
└───────────────────────┬─────────────────────────────┘
                        │ gap_analysis
                        ▼
              [RECRUITER REVIEWS & DECIDES]
                        │ decision: "accept" | "reject"
                        ▼
┌─────────────────────────────────────────────────────┐
│  Agent 2: ORCHESTRATOR AGENT                        │
│  • Receives gap_analysis + recruiter decision       │
│  • Routes to accept or reject path                  │
└──────────────┬──────────────────────────────────────┘
               │
     ┌─────────┴──────────┐
     │ accept             │ reject
     ▼                    ▼
┌─────────┐  ┌─────────┐  ┌──────────────────────────┐
│Agent 3: │  │Agent 4: │  │ Agent 5: REJECTION AGENT │
│COMM.    │  │PREP PACK│  │ • Reads gap_analysis      │
│AGENT    │  │AGENT    │  │ • Writes specific email   │
│(parallel│  │(parallel│  │ • Cites actual gaps       │
│with 4)  │  │with 3)  │  │ • Sends via Gmail MCP     │
│         │  │         │  └──────────────────────────┘
│• Email  │  │• 12-16  │
│• Calendar│  │  tailored│
│  event  │  │  questions│
└─────────┘  └─────────┘
     │              │
     └──────┬───────┘
            ▼
           END
```

**Non-serial pattern:** Communication Agent + Preparation Pack Agent run **in parallel** using LangGraph's `Send()` fan-out on the accept path.

---

## Tech Stack

| Component | Choice |
|---|---|
| Language | Python 3.11+ |
| Agent Framework | LangGraph |
| LLM | Claude Sonnet 4.5 (Anthropic) |
| Embedding Model | text-embedding-3-small (OpenAI) |
| Vector Store | ChromaDB (local, persistent) |
| Email Tool | Gmail SMTP (MCP-style tool) |
| Calendar Tool | Google Calendar API (MCP-style tool) |
| File Output | File I/O tool (interview prep pack) |
| UI | Streamlit |

---

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
# Edit .env with your actual API keys and credentials
```

Required:
- `GEMINI_API_KEY`
- `OPENAI_API_KEY` — from [platform.openai.com](https://platform.openai.com)

For Gmail tool:
- `GMAIL_SENDER` — your Gmail address
- `GMAIL_APP_PASSWORD` — 16-char app password ([guide](https://myaccount.google.com/apppasswords))

For Google Calendar tool:
- `GOOGLE_CREDENTIALS_FILE` — OAuth credentials JSON from [Google Cloud Console](https://console.cloud.google.com)
  1. Enable Google Calendar API
  2. Create OAuth 2.0 Client ID (Desktop app)
  3. Download → rename to `credentials.json` → place in project root
  4. First run opens a browser for authorization

### 3. Initialize the RAG Knowledge Base

```bash
python -m rag.setup
```

This embeds the hiring corpus (5 document types) into ChromaDB. Run once, or with `force_rebuild=True` if you update the documents.

### 4. Run the Application

```bash
streamlit run app.py
```

---

## RAG Knowledge Base

The Review Agent retrieves context from a ChromaDB collection containing:

| Document | Content |
|---|---|
| `01_successful_hires.txt` | Anonymized profiles of 5 past successful hires with skills, projects, and hiring notes |
| `02_scoring_rubric.txt` | Role-specific rubrics (AI/ML, Backend, Frontend) — what 25/25 looks like for each skill category |
| `03_rejection_history.txt` | 5 rejection case studies — specific reasons, score levels, and feedback given |
| `04_job_descriptions.txt` | Full job description templates for all 3 roles |
| `05_onboarding_outcomes.txt` | 90-day performance notes linking interview signals to actual job performance |

Chunked at paragraph level, embedded with `text-embedding-3-small`, stored in ChromaDB with cosine similarity retrieval.

---

## Tools

### Gmail MCP Tool (`tools/gmail_tool.py`)
- **Used by:** Communication Agent (acceptance), Rejection Agent (rejection)
- **Mechanism:** Gmail SMTP via `smtplib`
- **Agent invocation:** Claude decides when to call it based on reasoning (tool use API)

### Google Calendar MCP Tool (`tools/calendar_tool.py`)
- **Used by:** Communication Agent (accept path only)
- **Mechanism:** Google Calendar API v3 with OAuth 2.0
- **Creates:** Calendar event with Google Meet link, candidate invited as attendee

### File I/O Tool (`tools/file_io_tool.py`)
- **Used by:** Preparation Pack Agent (accept path only)
- **Mechanism:** Python file system (`pathlib.Path.write_text`)
- **Creates:** Markdown file in `interview_prep_packs/` with 12–16 tailored questions

---

## Project Structure

```
ai-recruitment-system/
├── app.py                        # Streamlit UI
├── state.py                      # LangGraph state definition
├── config.py                     # Constants and configuration
├── requirements.txt
├── .env.example
│
├── agents/
│   ├── review_agent.py           # Agent 1: RAG-grounded resume scoring
│   ├── orchestrator_agent.py     # Agent 2: Routing logic
│   ├── communication_agent.py    # Agent 3: Email + calendar (accept path)
│   ├── preparation_pack_agent.py # Agent 4: Interview questions + file (accept path)
│   └── rejection_agent.py        # Agent 5: Specific rejection email
│
├── rag/
│   ├── setup.py                  # Embeds corpus into ChromaDB
│   ├── retriever.py              # Retrieval + formatting for agent prompts
│   └── documents/                # 5 hiring knowledge documents
│
├── tools/
│   ├── gmail_tool.py             # Gmail MCP tool (LangChain @tool)
│   ├── calendar_tool.py          # Google Calendar MCP tool
│   └── file_io_tool.py           # File I/O tool
│
└── graph/
    └── recruitment_graph.py      # LangGraph graph definition + run functions
```
