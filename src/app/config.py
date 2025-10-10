from pathlib import Path
import json

# Project roots
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # /src
CONFIG_DIR = PROJECT_ROOT / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {"strategy": "gpt-sentiment", "interval_minutes": 5}


def _read_config_file() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            return {}
    return {}


def get_current_config() -> dict:
    """Return current config, overlaying defaults."""
    data = _read_config_file()
    cfg = {**DEFAULT_CONFIG, **data}
    # normalize accepted values
    if cfg.get("strategy") == "gpt":
        cfg["strategy"] = "gpt-sentiment"
    return cfg


def update_config(new_values: dict) -> dict:
    """Update config.json with whitelisted keys and return the result."""
    cfg = get_current_config()
    allowed = {"strategy", "interval_minutes"}
    for k, v in new_values.items():
        if k in allowed:
            cfg[k] = v
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
    return cfg
