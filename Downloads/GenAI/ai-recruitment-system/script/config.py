"""
Central configuration for the AI Recruitment Pipeline.
All constants, role definitions, and model settings are here.

── SWAPPING MODELS ────────────────────────────────────────────────────────────
Change LLM_PROVIDER + MODEL in your .env — zero code changes needed.

  Ollama (cloud):   LLM_PROVIDER=ollama      MODEL=llama3.1:70b
                    OLLAMA_BASE_URL=https://api.ollama.com
                    OLLAMA_API_KEY=your-key

  Ollama (local):   LLM_PROVIDER=ollama      MODEL=llama3.2
                    OLLAMA_BASE_URL=http://localhost:11434
                    (no OLLAMA_API_KEY needed)

  OpenAI:           LLM_PROVIDER=openai      MODEL=gpt-4o
                    OPENAI_API_KEY=sk-...

  Anthropic:        LLM_PROVIDER=anthropic   MODEL=claude-3-5-sonnet-20241022
                    ANTHROPIC_API_KEY=sk-ant-...

  Gemini:           LLM_PROVIDER=gemini      MODEL=gemini-1.5-pro
                    GEMINI_API_KEY=AIza...
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── LLM Configuration ─────────────────────────────────────────────────────────
LLM_PROVIDER    = os.getenv("LLM_PROVIDER", "ollama").lower()
MODEL           = os.getenv("MODEL", "llama3.1:70b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "https://api.ollama.com")
OLLAMA_API_KEY  = os.getenv("OLLAMA_API_KEY", "")


def get_llm():
    """
    Factory: returns a LangChain chat model based on LLM_PROVIDER in .env.
    Supports: ollama (local + cloud), openai, anthropic, gemini.
    """
    match LLM_PROVIDER:

        case "ollama":
            if OLLAMA_API_KEY:
                # Cloud Ollama — OpenAI-compatible endpoint with API key auth
                from langchain_openai import ChatOpenAI
                base = OLLAMA_BASE_URL.rstrip("/") + "/v1"
                return ChatOpenAI(model=MODEL, base_url=base, api_key=OLLAMA_API_KEY)
            else:
                # Local Ollama — native client, no auth required
                from langchain_ollama import ChatOllama
                return ChatOllama(model=MODEL, base_url=OLLAMA_BASE_URL)

        case "openai":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=MODEL,
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
                temperature=0,
                max_completion_tokens=2048,
            )

        case "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=MODEL,
                api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            )

        case "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            
            return ChatGoogleGenerativeAI(
                model=MODEL,
                google_api_key=os.getenv("GEMINI_API_KEY", ""),
                # temperature=0 is critical for tool calling accuracy
                temperature=0,
                # Ensures the model uses the official function-calling API
                convert_system_message_to_human=True
            )

        case _:
            raise ValueError(
                f"Unknown LLM_PROVIDER='{LLM_PROVIDER}'.\n"
                "Supported: 'ollama', 'openai', 'anthropic', 'gemini'"
            )

# ── OpenAI (embeddings only) ───────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL = "text-embedding-3-small"

# ── Google Calendar ────────────────────────────────────────────────────────────
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
GOOGLE_TOKEN_FILE = os.getenv("GOOGLE_TOKEN_FILE", "token.json")

# ── Gmail (SMTP) ───────────────────────────────────────────────────────────────
GMAIL_SENDER = os.getenv("GMAIL_SENDER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
COMPANY_NAME = os.getenv("COMPANY_NAME", "TechCorp Recruiting")

# ── Interview Prep Output ──────────────────────────────────────────────────────
PREP_PACK_OUTPUT_DIR = os.getenv("PREP_PACK_OUTPUT_DIR", "interview_prep_packs")

# ── Role Definitions ───────────────────────────────────────────────────────────
ROLES = {
    "ai_ml_engineer": "AI/ML Engineer",
    "backend_engineer": "Backend Engineer",
    "frontend_engineer": "Frontend Engineer",
}

ROLE_CORE_SKILLS = {
    "ai_ml_engineer": [
        "Python",
        "PyTorch or TensorFlow",
        "Machine Learning fundamentals (optimization, evaluation, regularization)",
        "Deep Learning and Neural Networks",
        "LLM experience (fine-tuning, RAG, or prompt engineering)",
        "Data engineering (Pandas, SQL, or Spark)",
        "MLOps and model deployment",
        "Git and collaborative development",
    ],
    "backend_engineer": [
        "Python (Django/FastAPI) or Node.js",
        "REST API design",
        "PostgreSQL — schema design and query optimization",
        "AWS (EC2/ECS, RDS, S3, Lambda)",
        "Docker in production",
        "CI/CD (GitHub Actions, Jenkins)",
        "System design and architecture",
        "Security fundamentals (authentication, authorization)",
    ],
    "frontend_engineer": [
        "React (function components, all hooks)",
        "TypeScript (required)",
        "Advanced CSS3 / Tailwind / responsive design",
        "State management (Redux, Zustand, or React Query)",
        "Testing (Jest + React Testing Library; E2E preferred)",
        "Build tools (Vite or Webpack)",
        "Accessibility (WCAG 2.1)",
        "Figma / design collaboration",
    ],
}

SCORE_THRESHOLDS = {
    "strong_accept": 90,
    "accept": 75,
    "borderline": 60,
    "reject": 0,
}

RAG_TOP_K = 6
