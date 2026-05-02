"""Alert system: define conditions, check against current stock data."""
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api")

ALERTS_FILE = Path(__file__).parent.parent.parent / "data" / "alerts.json"


def _generate_id() -> str:
    """Generate unique ID: timestamp in base36 + random suffix."""
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    ts = int(time.time() * 1000)
    base36 = ""
    while ts > 0:
        ts, rem = divmod(ts, 36)
        base36 = chars[rem] + base36
    if not base36:
        base36 = "0"
    random_part = "".join(random.choice(chars) for _ in range(6))
    return base36 + random_part


def _load_alerts() -> list[dict]:
    if not ALERTS_FILE.exists():
        return []
    try:
        with open(ALERTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_alerts(alerts: list[dict]):
    ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ALERTS_FILE, "w", encoding="utf-8") as f:
        json.dump(alerts, f, ensure_ascii=False, indent=2)


class AlertCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    conditions: dict


class AlertUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    conditions: dict | None = None


def check_all_alerts() -> int:
    """Check all enabled alerts against current stock data. Returns count of triggered alerts."""
    from services.screener import get_all_stocks_df, apply_filters

    alerts = _load_alerts()
    if not alerts:
        return 0

    df = get_all_stocks_df()
    if df.empty:
        return 0

    triggered_count = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    for alert in alerts:
        if not alert.get("enabled", True):
            continue
        try:
            conditions = alert.get("conditions", {})
            filtered = apply_filters(df, conditions)

            if len(filtered) > 0:
                cols = [
                    "code", "name", "close", "pe_ttm", "pb", "roe", "market_cap",
                    "change_pct", "volume_ratio", "turnover_rate", "dividend_yield",
                ]
                available = [c for c in cols if c in filtered.columns]
                stocks = filtered[available].astype(object).where(filtered.notna(), None).to_dict(orient="records")

                alert["triggered"] = True
                alert["triggered_stocks"] = stocks
                alert["last_triggered_at"] = now_iso
                triggered_count += 1
            else:
                alert["triggered"] = False
                alert["triggered_stocks"] = []
        except Exception:
            pass  # non-fatal

    _save_alerts(alerts)
    return triggered_count


@router.get("/alerts")
def list_alerts():
    return {"alerts": _load_alerts()}


@router.post("/alerts")
def create_alert(body: AlertCreate):
    alerts = _load_alerts()
    now = datetime.now(timezone.utc).isoformat()
    alert = {
        "id": _generate_id(),
        "name": body.name,
        "enabled": True,
        "conditions": body.conditions,
        "triggered": False,
        "triggered_stocks": [],
        "last_triggered_at": None,
        "created_at": now,
    }
    alerts.append(alert)
    try:
        _save_alerts(alerts)
    except OSError:
        raise HTTPException(status_code=500, detail="Failed to save alerts")
    return alert


@router.put("/alerts/{alert_id}")
def update_alert(alert_id: str, body: AlertUpdate):
    alerts = _load_alerts()
    for alert in alerts:
        if alert["id"] == alert_id:
            if body.name is not None:
                alert["name"] = body.name
            if body.enabled is not None:
                alert["enabled"] = body.enabled
            if body.conditions is not None:
                alert["conditions"] = body.conditions
            try:
                _save_alerts(alerts)
            except OSError:
                raise HTTPException(status_code=500, detail="Failed to save alerts")
            return alert
    raise HTTPException(status_code=404, detail="Alert not found")


@router.delete("/alerts/{alert_id}")
def delete_alert(alert_id: str):
    alerts = _load_alerts()
    original_len = len(alerts)
    alerts = [a for a in alerts if a["id"] != alert_id]
    if len(alerts) == original_len:
        raise HTTPException(status_code=404, detail="Alert not found")
    try:
        _save_alerts(alerts)
    except OSError:
        raise HTTPException(status_code=500, detail="Failed to save alerts")
    return {"status": "deleted", "id": alert_id}


@router.post("/alerts/check")
def trigger_alert_check():
    triggered = check_all_alerts()
    return {"triggered": triggered}
