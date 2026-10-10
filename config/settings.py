from typing import Literal, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application and test execution settings.
    
    Reads from environment variables (prefixed with APP_) or a local .env file.
    Works seamlessly in both local environments and CI/CD pipelines.
    """
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    env: str = Field(default="local", description="Environment: local, dev, staging, prod, ci")
    base_url: str = Field(default="http://localhost:8080", description="Base URL of application under test")

    # Browser Execution
    browser: Literal["chromium", "firefox", "webkit"] = Field(
        default="chromium", description="Target browser engine"
    )
    headless: bool = Field(default=True, description="Run browser in headless mode")
    slow_mo_ms: int = Field(default=0, description="Slow down Playwright actions by milliseconds")
    timeout_ms: int = Field(default=10_000, description="Default assertion and action timeout in ms")

    # Viewport
    viewport_width: int = Field(default=1280, description="Browser window width")
    viewport_height: int = Field(default=720, description="Browser window height")

    # Diagnostics & Reporting
    screenshot_on_failure: bool = Field(default=True, description="Capture full-page screenshot on failure")
    embed_logs: bool = Field(default=True, description="Embed execution logs in HTML report")
    embed_logs_on_failure_only: bool = Field(default=False, description="Embed execution logs only on failure if True")
    embed_console_logs: bool = Field(default=True, description="Embed browser console logs in HTML report")
    company_logo: Optional[str] = Field(
        default="assets/company_logo.svg",
        description="Path or URL to company logo to display on HTML reports",
    )
    reports_dir: str = Field(default="reports", description="Directory to store reports")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Logging level"
    )


# Global singleton settings instance
settings = Settings()
