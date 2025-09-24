from pydantic_settings import BaseSettings
from typing import Optional, Literal


class Settings(BaseSettings):
    # Database Configuration - supports either SQLite or PostgreSQL
    SQLITE_DATABASE_URL: Optional[str] = None

    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_DB: Optional[str] = None
    POSTGRES_HOST: Optional[str] = None
    POSTGRES_PORT: Optional[int] = None

    @property
    def DATABASE_URL(self) -> str:
        if self.SQLITE_DATABASE_URL:
            return self.SQLITE_DATABASE_URL
        elif all([self.POSTGRES_USER, self.POSTGRES_PASSWORD, self.POSTGRES_DB, self.POSTGRES_HOST, self.POSTGRES_PORT]):
            return f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        else:
            raise ValueError("Database configuration is missing. Please set either SQLITE_DATABASE_URL or all POSTGRES_* variables in your .env file.")

    # Minio
    MINIO_ENDPOINT: str
    MINIO_EXTERNAL_ENDPOINT: Optional[str] = None # For generating URLs accessible from outside the local network
    MINIO_ROOT_USER: str
    MINIO_ROOT_PASSWORD: str
    MINIO_BUCKET_ORIGINALS: str = "kosmos-originals"
    MINIO_BUCKET_ASSETS: str = "kosmos-assets"
    MINIO_BUCKET_CANONICAL_CONTENTS: str = "kosmos-canonical-contents"
    MINIO_BUCKET_PDFS: str = "kosmos-pdfs"

    # Milvus
    MILVUS_HOST: str
    MILVUS_PORT: int
    MILVUS_USER: str
    MILVUS_PASSWORD: str

    # Redis
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int = 0

    # Asset Analysis
    SERVICE_MODE: str = "internal"  # "internal" or "external"
    ASSET_ANALYSIS_CACHE_TTL_SECONDS: int = 60 * 60 * 24 * 7  # 7 days

    # Auto Asset Description Configuration
    AUTO_ASSET_DESCRIPTION_ENABLED: bool = True  # 是否启用自动资产描述
    AUTO_ASSET_DESCRIPTION_MAX_SIZE_MB: int = 10  # 自动分析的最大文件大小（MB）

    # Document Processing Timeout Configuration
    DOCUMENT_PROCESSING_TIMEOUT_MINUTES: int = 100  # 文档处理任务超时时间（分钟）

    # Chunking Strategy Configuration
    PROCESSING_STRATEGY: Literal["document", "megachunk"] = "document"

    # External Tools
    LIBREOFFICE_PATH: str | None = None
    MINERU_PATH: str | None = None
    MINERU_BACKEND: str = "pipeline"
    MINERU_SERVER_URL: str = "http://localhost:30005"
    MINERU_SOURCE: str = "huggingface"

    # JWT Authentication
    SECRET_KEY: str = "a_very_secret_key_that_should_be_changed"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    SUPER_ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30 # 新增的Refresh Token有效期配置

    # Credential Encryption
    CREDENTIAL_ENCRYPTION_KEY: str = "generate_a_32_byte_url_safe_base64_key_for_this"

    # API Configuration
    API_BASE_URL: str = "http://localhost:8011"
    INTERNAL_API_BASE_URL: str = "http://localhost:8012"
    INTERNAL_API_SECRET: str = "a_very_secret_internal_key"
    WORKER_SECRET: str = "deprecated_use_internal_api_secret" # Deprecated, for reference

    # Event Relay Configuration
    EVENT_RELAY_POLLING_INTERVAL: int = 30 # 事件中继轮询间隔（秒）
    EVENT_RELAY_BATCH_SIZE: int = 100 # 事件中继每次处理的事件数量

    # --- AI Global Defaults ---
    OPENAI_MAX_RETRIES: int = 3
    DEFAULT_AI_CONFIGURATION: dict = {
        "embedding": {
            "provider": "default",
            "model_name": "qwen3-embedding-0.6b",
            "dimension": 1024,
            "params": {}
        },
        "chunking": {
            "provider": "default",
            "model_name": "Qwen/Qwen3-4B-Instruct-2507",
            "params": {
                "temperature": 0.1
            }
        },
        "tagging": {
            "provider": "default",
            "model_name": "Qwen/Qwen3-30B-A3B-Instruct-2507",
            "params": {
                "temperature": 0.3
            }
        },
        "asset_analysis": {
            "provider": "default",
            "model_name": "kimi-vl-2506",
            "params": {
                "temperature": 0.2
            }
        }
    }

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        extra = 'ignore'

settings = Settings()
