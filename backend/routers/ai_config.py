"""AI model configuration persistence."""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api")

AI_CONFIG_FILE = Path(__file__).parent.parent.parent / "data" / "ai_config.json"


def _defaults() -> dict:
    return {"api_url": "https://api.openai.com/v1", "model": "gpt-4o", "api_key": ""}


def _load_ai_config() -> dict:
    if not AI_CONFIG_FILE.exists():
        return _defaults()
    try:
        with open(AI_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return _defaults()


def _save_ai_config(config: dict):
    AI_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(AI_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


class AiConfigRequest(BaseModel):
    api_url: str = Field(default="https://api.openai.com/v1", max_length=500)
    model: str = Field(default="gpt-4o", max_length=200)
    api_key: str = Field(default="", max_length=500)


@router.get("/ai-config")
def get_ai_config():
    config = _load_ai_config()
    key = config.get("api_key", "")
    return {
        "api_url": config.get("api_url", "https://api.openai.com/v1"),
        "model": config.get("model", "gpt-4o"),
        "has_key": bool(key and key.strip()),
    }


@router.post("/ai-config")
def save_ai_config(req: AiConfigRequest):
    config = _load_ai_config()
    config["api_url"] = req.api_url
    config["model"] = req.model
    if req.api_key and req.api_key.strip():
        config["api_key"] = req.api_key.strip()
    try:
        _save_ai_config(config)
    except OSError:
        raise HTTPException(status_code=500, detail="Failed to save AI config")
    return {"status": "saved"}
