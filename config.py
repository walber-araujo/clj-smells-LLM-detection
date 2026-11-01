import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # LLM
    llm_provider: str = os.getenv("LLM_PROVIDER", "gemini")
    detection_model: str = os.getenv("DETECTION_MODEL", "gemini-flash-latest")
    critic_model: str = os.getenv("CRITIC_MODEL", "gemini-flash-latest")

    # Reliability
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    timeout_s: int = int(os.getenv("TIMEOUT_S", "60"))

    # Catalog
    catalog_path: str = os.getenv("CATALOG_PATH", "smells_catalog.json")
    catalog_short_path: str = os.getenv("CATALOG_SHORT_PATH", "smells_catalog_short.json")

    # Vector DB
    vectordb_provider: str = os.getenv("VECTORDB_PROVIDER", "mock")
    chromadb_persist_path: str = os.getenv("CHROMADB_PERSIST_PATH", ".chromadb")

    # API keys
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")


config = Config()
