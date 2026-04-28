"""Strategy template save/load."""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api")

STRATEGIES_FILE = Path(__file__).parent.parent.parent / "data" / "strategies.json"


class Strategy(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    filters: dict


def _load_strategies() -> list[dict]:
    if not STRATEGIES_FILE.exists():
        return _presets()
    try:
        with open(STRATEGIES_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return _presets()


def _presets() -> list[dict]:
    return [
        {"name": "高ROE成长股", "filters": {"roe_min": 15, "revenue_growth_min": 20, "exclude_st": True, "sort_by": "roe", "order": "desc"}},
        {"name": "低估值蓝筹", "filters": {"pe_max": 15, "pb_max": 1.5, "dividend_yield_min": 3, "exclude_st": True, "sort_by": "pe_ttm", "order": "asc"}},
        {"name": "均线多头排列", "filters": {"exclude_st": True, "sort_by": "market_cap", "order": "desc"}},
        {"name": "新高附近", "filters": {"exclude_st": True, "sort_by": "close", "order": "desc"}},
    ]


def _save_strategies(strategies: list[dict]):
    STRATEGIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STRATEGIES_FILE, "w") as f:
        json.dump(strategies, f, ensure_ascii=False, indent=2)


@router.get("/strategies")
def list_strategies():
    return {"strategies": _load_strategies()}


@router.post("/strategies")
def save_strategy(strategy: Strategy):
    strategies = _load_strategies()
    strategies = [s for s in strategies if s["name"] != strategy.name]
    strategies.append({"name": strategy.name, "filters": strategy.filters})
    try:
        _save_strategies(strategies)
    except OSError:
        raise HTTPException(status_code=500, detail="Failed to save strategies")
    return {"status": "saved", "name": strategy.name}
