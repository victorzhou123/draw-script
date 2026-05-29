import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    host: str = "0.0.0.0"
    port: int = 9001
    db_path: str = "draw_script.db"
    log_level: str = "info"
    heartbeat_timeout: int = 15
    heartbeat_interval: int = 5
    node_timeout: int = 30
    run_timeout: int = 300
    compute_timeout: int = 60
    ai_api_key: str = ""
    ai_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ai_model: str = "qwen-vl-plus"
    templates_dir: str = "templates"

    def __post_init__(self):
        self.host = os.getenv("DS_HOST", self.host)
        self.port = int(os.getenv("DS_PORT", self.port))
        self.db_path = os.getenv("DS_DB_PATH", self.db_path)
        self.ai_api_key = os.getenv("DS_AI_API_KEY", self.ai_api_key)
        self.ai_base_url = os.getenv("DS_AI_BASE_URL", self.ai_base_url)
        self.ai_model = os.getenv("DS_AI_MODEL", self.ai_model)
        self.templates_dir = os.getenv("DS_TEMPLATES_DIR", self.templates_dir)
        os.makedirs(self.templates_dir, exist_ok=True)


settings = Settings()
