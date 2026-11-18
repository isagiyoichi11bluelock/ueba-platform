"""Configuration loading and validation for the UEBA platform."""
from __future__ import annotations
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any
import yaml
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv

# Load .env
load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent.parent


class DataConfig(BaseModel):
    num_users: int = 60
    num_contractors: int = 10
    num_resources: int = 150
    history_days: int = 90
    baseline_days: int = 75
    detection_start_day: int = 76


class BaselineConfig(BaseModel):
    rolling_window_days: int = 60
    min_days_for_full_confidence: int = 30
    min_events_for_full_confidence: int = 50
    smoothing_alpha: float = 0.1


class ThresholdsConfig(BaseModel):
    impossible_travel_kmh: float = 900.0
    failed_login_burst_count: int = 5
    failed_login_burst_minutes: int = 10
    download_spike_mad_z: float = 3.5
    download_trend_days: int = 5
    peer_deviation_z: float = 2.5


class ScoringBands(BaseModel):
    low: list[int] = [0, 34]
    medium: list[int] = [35, 59]
    high: list[int] = [60, 79]
    critical: list[int] = [80, 100]


class ScoringConfig(BaseModel):
    bands: ScoringBands = Field(default_factory=ScoringBands)
    chain_bonus: dict[str, int] = Field(default_factory=dict)


class ContextDampeningConfig(BaseModel):
    max_reduction_factor: float = 0.80
    approved_travel: float = 0.70
    month_end_close: float = 0.65
    on_call: float = 0.75
    project_deadline: float = 0.50
    new_joiner: float = 0.60
    role_change: float = 0.50
    undampenable_indicators: list[str] = Field(default_factory=list)


class FeedbackConfig(BaseModel):
    adjustment_expiry_days: int = 30
    max_adjustment_factor: float = 0.60
    max_comment_chars: int = 500


class RetentionConfig(BaseModel):
    events_days: int = 90
    alerts_days: int = 365
    audit_days: int = 730


class PrivacyConfig(BaseModel):
    pseudonym_prefix: str = "U-"
    ip_truncation: bool = True
    identity_map_access_role: str = "senior_analyst"
    min_justification_chars: int = 20


class UEBAConfig(BaseModel):
    seed: int = 42
    end_date: str = "yesterday"
    data: DataConfig = Field(default_factory=DataConfig)
    baseline: BaselineConfig = Field(default_factory=BaselineConfig)
    thresholds: ThresholdsConfig = Field(default_factory=ThresholdsConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    context_dampening: ContextDampeningConfig = Field(default_factory=ContextDampeningConfig)
    feedback: FeedbackConfig = Field(default_factory=FeedbackConfig)
    retention: RetentionConfig = Field(default_factory=RetentionConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)

    def get_end_date(self) -> date:
        if self.end_date == "yesterday":
            return date.today() - timedelta(days=1)
        return date.fromisoformat(self.end_date)

    def get_start_date(self) -> date:
        return self.get_end_date() - timedelta(days=self.data.history_days - 1)


class IndicatorWeightConfig(BaseModel):
    base_points: int
    description: str


def load_config(config_path: Path | None = None) -> UEBAConfig:
    """Load and validate the UEBA configuration."""
    if config_path is None:
        config_path = PROJECT_ROOT / "config" / "config.yaml"
    with open(config_path) as f:
        raw = yaml.safe_load(f)
    return UEBAConfig(**raw)


def load_scoring_weights(weights_path: Path | None = None) -> dict[str, IndicatorWeightConfig]:
    """Load indicator scoring weights."""
    if weights_path is None:
        weights_path = PROJECT_ROOT / "config" / "scoring_weights.yaml"
    with open(weights_path) as f:
        raw = yaml.safe_load(f)
    return {k: IndicatorWeightConfig(**v) for k, v in raw["indicators"].items()}


def get_pseudonym_salt() -> str:
    """Get pseudonymization salt from environment."""
    salt = os.environ.get("PSEUDONYM_SALT", "")
    if not salt or salt == "change-me-to-a-random-string-at-least-32-chars":
        import secrets
        salt = secrets.token_hex(32)
        env_path = PROJECT_ROOT / ".env"
        with open(env_path, "a") as f:
            f.write(f"\nPSEUDONYM_SALT={salt}\n")
        os.environ["PSEUDONYM_SALT"] = salt
    return salt


def get_dashboard_role() -> str:
    """Get dashboard role from environment."""
    return os.environ.get("DASHBOARD_ROLE", "analyst")


# Singleton
_config: UEBAConfig | None = None


def get_config() -> UEBAConfig:
    """Get the global config singleton."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


# Alias for backward compatibility
get_settings = get_config
