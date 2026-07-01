import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    # Gemini
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = "gemini-3.1-flash-lite"

    # OpenAI (opcional)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # OpenWA
    OPENWA_BASE: str = "http://localhost:2785"
    OPENWA_API_KEY: str = os.getenv("OPENWA_API_KEY", "dev-admin-key")
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "massgo-wa-hmac-2026")

    # Servidor
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    INTERNAL_BASE: str = os.getenv("INTERNAL_BASE", f"http://localhost:{os.getenv('PORT', '8000')}")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")


settings = Settings()
