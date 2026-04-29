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
    description: str = Field(default="", max_length=200)


def _load_strategies() -> list[dict]:
    if not STRATEGIES_FILE.exists():
        return _presets()
    try:
        with open(STRATEGIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return _presets()


def _presets() -> list[dict]:
    return [
        {
            "name": "高ROE成长股",
            "description": "ROE >= 15%，营收增长 >= 20%，寻找高质量成长企业",
            "filters": {"roe_min": 15, "revenue_growth_min": 20, "exclude_st": True, "sort_by": "roe", "order": "desc"},
        },
        {
            "name": "低估值蓝筹",
            "description": "PE <= 15，PB <= 1.5，股息率 >= 3%，筛选低估值高分红蓝筹",
            "filters": {"pe_max": 15, "pb_max": 1.5, "dividend_yield_min": 3, "exclude_st": True, "sort_by": "pe_ttm", "order": "asc"},
        },
        {
            "name": "均线多头排列",
            "description": "均线多头排列趋势向好，按市值排序",
            "filters": {"exclude_st": True, "sort_by": "market_cap", "order": "desc"},
        },
        {
            "name": "新高附近",
            "description": "股价接近新高，按收盘价排序",
            "filters": {"exclude_st": True, "sort_by": "close", "order": "desc"},
        },
        {
            "name": "放量突破",
            "description": "量比 >= 2，涨幅 >= 3%，放量上攻形态",
            "filters": {"volume_ratio_min": 2, "change_pct_min": 3, "exclude_st": True, "sort_by": "volume_ratio", "order": "desc"},
        },
        {
            "name": "低位高换手",
            "description": "换手率 >= 5%，涨跌幅 -5%~5%，筛选活跃度提升标的",
            "filters": {"turnover_rate_min": 5, "change_pct_min": -5, "change_pct_max": 5, "exclude_st": True, "sort_by": "turnover_rate", "order": "desc"},
        },
    ]


def _save_strategies(strategies: list[dict]):
    STRATEGIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STRATEGIES_FILE, "w", encoding="utf-8") as f:
        json.dump(strategies, f, ensure_ascii=False, indent=2)


@router.get("/strategies")
def list_strategies():
    return {"strategies": _load_strategies()}


@router.post("/strategies")
def save_strategy(strategy: Strategy):
    strategies = _load_strategies()
    strategies = [s for s in strategies if s["name"] != strategy.name]
    strategies.append({"name": strategy.name, "filters": strategy.filters, "description": strategy.description})
    try:
        _save_strategies(strategies)
    except OSError:
        raise HTTPException(status_code=500, detail="Failed to save strategies")
    return {"status": "saved", "name": strategy.name}


@router.delete("/strategies/{name}")
def delete_strategy(name: str):
    preset_names = [p["name"] for p in _presets()]
    if name in preset_names:
        raise HTTPException(status_code=400, detail="Cannot delete built-in preset strategies")
    strategies = _load_strategies()
    original_len = len(strategies)
    strategies = [s for s in strategies if s["name"] != name]
    if len(strategies) == original_len:
        raise HTTPException(status_code=404, detail="Strategy not found")
    try:
        _save_strategies(strategies)
    except OSError:
        raise HTTPException(status_code=500, detail="Failed to save strategies")
    return {"status": "deleted", "name": name}
