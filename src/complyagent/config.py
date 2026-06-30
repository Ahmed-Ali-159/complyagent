"""Central configuration: merges config.yaml + .env into a typed settings object."""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_YAML_PATH = REPO_ROOT / "config.yaml"


# ---------- YAML-backed sub-models ----------

class LLMConfig(BaseModel):
    supervisor_model: str
    worker_model: str
    provider: str
    temperature: float
    max_tokens: int


class RetrievalConfig(BaseModel):
    embedding_model: str
    reranker_model: str
    bm25_weight: float
    dense_weight: float
    initial_k: int
    final_k: int
    collection_name: str


class GraphConfig(BaseModel):
    max_iterations: int
    stale_state_threshold: int
    confidence_threshold: float
    max_reretrieval: int


class PathsConfig(BaseModel):
    data_dir: str
    chroma_persist_dir: str
    policies_dir: str
    processed_dir: str
    eval_dir: str

    def resolve(self, root: Path) -> "PathsConfig":
        """Convert relative paths to absolute, anchored at repo root."""
        return PathsConfig(
            data_dir=str((root / self.data_dir).resolve()),
            chroma_persist_dir=str((root / self.chroma_persist_dir).resolve()),
            policies_dir=str((root / self.policies_dir).resolve()),
            processed_dir=str((root / self.processed_dir).resolve()),
            eval_dir=str((root / self.eval_dir).resolve()),
        )


# ---------- .env-backed secrets ----------

class Secrets(BaseSettings):
    """Loaded from .env. Never log or print these."""
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    cerebras_api_key: str = Field(default="", alias="CEREBRAS_API_KEY")  
    langsmith_api_key: str = Field(default="", alias="LANGSMITH_API_KEY")
    langsmith_tracing: bool = Field(default=False, alias="LANGSMITH_TRACING")
    langsmith_project: str = Field(default="complyagent", alias="LANGSMITH_PROJECT")


# ---------- Top-level Settings ----------

class Settings(BaseModel):
    llm: LLMConfig
    retrieval: RetrievalConfig
    graph: GraphConfig
    paths: PathsConfig
    secrets: Secrets

    @classmethod
    def load(cls) -> "Settings":
        with open(CONFIG_YAML_PATH, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        return cls(
            llm=LLMConfig(**raw["llm"]),
            retrieval=RetrievalConfig(**raw["retrieval"]),
            graph=GraphConfig(**raw["graph"]),
            paths=PathsConfig(**raw["paths"]).resolve(REPO_ROOT),
            secrets=Secrets(),
        )


settings = Settings.load()