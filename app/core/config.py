from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra='ignore')

    # Infra Vars
    db_name: str
    db_user: str
    db_pass: str
    db_host: str
    db_port: int

    redis_url: str
    storage: str


    # LLM
    parser_fallback_llm: str
    matcher_model: str
    extractor_fallback_model: str
    query_reformulator_model: str

    # Web searchs
    serper_api_key: str = ''
    

    # Main Vars
    options_per_item: int = 4
    equivalence_threshold: float = 0.7
    max_reformulations_per_tier: int = 2
    max_searches_per_item: int = 18
    candidates_to_matcher: int = 10
    tier_order: str = "ve,us,cn,global"


    # Emails Config

    poll_interval_minutes: int = 15
    email_credentials_json: str = "secrets/email_credentials.json"
    email_token_json: str = "secrets/email_token.json"
    quote_subject_keywords: str = "cotizacion,cotización,rfq,solicitud de compra"
    quote_sender_whitelist: str = ""

    def model_for(self, role: str) -> str:
        mapping = {
            "parser_fallback": self.parser_fallback_llm,
            "matcher": self.matcher_model,
            "extractor_fallback": self.extractor_fallback_model,
            "query_reformulator": self.query_reformulator_model
        }
        return mapping[role]
    
    @property
    def tiers(self) -> list[str]:
        return [t.strip() for t in self.tier_order.split(",") if t.strip()]
    

    @property
    def subject_keywords(self,) -> list[str]:
        return [k.strip().lower() for k in self.quote_subject_keywords.split(",") if k.strip()]
    
    @property
    def DATABASE_URL(self) -> str:
        """Get the MySQL database URL."""
        return f"postgresql+psycopg://{self.db_user}:{self.db_pass}@{self.db_host}:{self.db_port}/{self.db_name}"
    


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


