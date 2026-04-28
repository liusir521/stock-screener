"""Stock screening and detail endpoints."""
from fastapi import APIRouter, Query

from services.screener import get_all_stocks_df, apply_filters, paginate

router = APIRouter(prefix="/api")


@router.get("/stocks")
def list_stocks(
    keyword: str | None = Query(None),
    market: str | None = Query(None),
    pe_min: float | None = Query(None),
    pe_max: float | None = Query(None),
    pb_min: float | None = Query(None),
    pb_max: float | None = Query(None),
    roe_min: float | None = Query(None),
    market_cap_min: float | None = Query(None),
    market_cap_max: float | None = Query(None),
    dividend_yield_min: float | None = Query(None),
    revenue_growth_min: float | None = Query(None),
    exclude_st: bool = Query(True),
    sort_by: str = Query("code"),
    order: str = Query("asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    filters = {k: v for k, v in {
        "keyword": keyword, "market": market, "pe_min": pe_min, "pe_max": pe_max,
        "pb_min": pb_min, "pb_max": pb_max, "roe_min": roe_min,
        "market_cap_min": market_cap_min, "market_cap_max": market_cap_max,
        "dividend_yield_min": dividend_yield_min,
        "revenue_growth_min": revenue_growth_min,
        "exclude_st": exclude_st, "sort_by": sort_by, "order": order,
    }.items() if v is not None}

    df = get_all_stocks_df()
    filtered = apply_filters(df, filters)
    items, total = paginate(filtered, page, page_size)

    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/stocks/{code}")
def stock_detail(code: str):
    from database import engine
    from sqlalchemy import text
    import pandas as pd
    from services.data_fetcher import fetch_kline_sina, fetch_stock_history

    basic_query = "SELECT * FROM stock_basic WHERE code = :code"
    with engine.connect() as conn:
        basic = pd.read_sql_query(basic_query, conn, params={"code": code})

    # Try Sina K-line first, then akshare, then fallback to stock_daily
    kline_df = fetch_kline_sina(code)
    if kline_df.empty:
        kline_df = fetch_stock_history(code)
    daily_data = kline_df.where(kline_df.notna(), None).to_dict(orient="records") if not kline_df.empty else []

    if not daily_data:
        query = "SELECT * FROM stock_daily WHERE code = :code ORDER BY date DESC LIMIT 60"
        with engine.connect() as conn:
            df = pd.read_sql_query(query, conn, params={"code": code})
        daily_data = df.where(df.notna(), None).to_dict(orient="records")

    # Enrich with turnover_rate if missing (compute from volume, close, and nmc from DB)
    if daily_data and 'turnover_rate' not in daily_data[0]:
        nmc = 0
        try:
            nmc_query = "SELECT nmc FROM stock_daily WHERE code = :code"
            with engine.connect() as conn:
                row = conn.execute(text(nmc_query), {"code": code}).fetchone()
                if row:
                    nmc = float(row[0] or 0)
        except Exception:
            pass
        if nmc > 0:
            for d in daily_data:
                vol = float(d.get("volume") or 0)
                cls = float(d.get("close") or 0)
                # turnover_rate = volume(手) * close_price(元) / (nmc(万元) * 100)
                d["turnover_rate"] = round(vol * cls / (nmc * 100), 2)

    return {
        "basic": basic.to_dict(orient="records")[0] if len(basic) > 0 else None,
        "daily": daily_data,
    }


@router.get("/markets")
def list_markets():
    return {
        "markets": [
            {"key": "sh_sz", "label": "沪深A股"},
            {"key": "chinext", "label": "创业板"},
            {"key": "star", "label": "科创板"},
            {"key": "bse", "label": "北交所"},
        ]
    }


@router.post("/refresh")
async def refresh_data():
    """Trigger a manual data refresh from Sina API."""
    import asyncio
    from seed_data import seed, get_refresh_status
    status = get_refresh_status()
    if status["running"]:
        return {"status": "running", "message": "数据刷新进行中，请稍后再试"}
    result = await asyncio.to_thread(seed)
    return result


@router.get("/refresh/status")
def refresh_status():
    from seed_data import get_refresh_status
    return get_refresh_status()
