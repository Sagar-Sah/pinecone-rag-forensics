import os
from dataclasses import dataclass
from dotenv import load_dotenv


load_dotenv()

@dataclass(frozen=True)
class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    pinecone_api_key: str = os.getenv("PINECONE_API_KEY","")

    pinecone_index_name: str  =os.getenv("PINECONE_INDEX_NAME","")
    pinecone_cloud: str = os.getenv("PINECONE_CLOUD","aws")
    pinecone_region: str = os.getenv("PINECONE_REGION","us-east-1")

    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    embedding_dimension: int = int(os.getenv("EMBEDDING_DIMENSION", "1536"))

    chat_model: str = os.getenv("CHAT_MODEL", "gpt-4o-mini")

    upload_dir: str = os.getenv("UPLOAD_DIR", "uploads")
    sqlite_url: str = os.getenv("SQLITE_URL", "sqlite:///data/app.db")
    secret_key: str = os.getenv("SECRET_KEY", "change-me-in-production-use-a-long-random-string")

    def validate(self) -> None:
        missing = []

        if not self.openai_api_key:
            missing.append("OPENAI_API_KEY")

        if not self.pinecone_api_key:
            missing.append("PINECONE_API_KEY")

        if missing:
            raise RuntimeError(
                "Missing required environment variables: " + ", ".join(missing)
            )
        
settings = Settings()