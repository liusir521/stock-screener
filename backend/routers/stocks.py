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
    revenue_growth_max: float | None = Query(None),
    change_pct_min: float | None = Query(None),
    change_pct_max: float | None = Query(None),
    volume_ratio_min: float | None = Query(None),
    concept: str | None = Query(None),
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
        "revenue_growth_min": revenue_growth_min, "revenue_growth_max": revenue_growth_max,
        "change_pct_min": change_pct_min, "change_pct_max": change_pct_max,
        "volume_ratio_min": volume_ratio_min, "concept": concept,
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
    from services.data_fetcher import fetch_kline_sina, fetch_stock_history, fetch_corp_info

    basic_query = "SELECT * FROM stock_basic WHERE code = :code"
    with engine.connect() as conn:
        basic = pd.read_sql_query(basic_query, conn, params={"code": code})

    basic_dict = basic.to_dict(orient="records")[0] if len(basic) > 0 else None

    # Enrich basic info with industry and list_date from Sina corp pages
    if basic_dict and (not basic_dict.get("industry") or not basic_dict.get("list_date")):
        corp = fetch_corp_info(code)
        if corp.get("industry"):
            basic_dict["industry"] = corp["industry"]
        if corp.get("list_date"):
            basic_dict["list_date"] = corp["list_date"]

    # Try Sina K-line first, then akshare, then fallback to stock_daily
    kline_df = fetch_kline_sina(code, days=120)
    if kline_df.empty:
        kline_df = fetch_stock_history(code, days=120)
    daily_data = kline_df.where(kline_df.notna(), None).to_dict(orient="records") if not kline_df.empty else []

    if not daily_data:
        query = "SELECT * FROM stock_daily WHERE code = :code ORDER BY date DESC LIMIT 120"
        with engine.connect() as conn:
            df = pd.read_sql_query(query, conn, params={"code": code})
        daily_data = df.where(df.notna(), None).to_dict(orient="records")

    # Enrich with turnover_rate if missing (compute using float_shares from DB)
    if daily_data and 'turnover_rate' not in daily_data[0] and 'float_shares' not in daily_data[0]:
        float_shares = 0
        try:
            fs_query = "SELECT float_shares FROM stock_daily WHERE code = :code AND float_shares > 0 ORDER BY date DESC LIMIT 1"
            with engine.connect() as conn:
                row = conn.execute(text(fs_query), {"code": code}).fetchone()
                if row:
                    float_shares = float(row[0])
        except Exception:
            pass
        if float_shares > 0:
            for d in daily_data:
                vol = float(d.get("volume") or 0)
                # turnover_rate(%) = volume(手) * 100 / float_shares(股)
                d["turnover_rate"] = round(vol * 100 / float_shares, 2)

    return {
        "basic": basic_dict,
        "daily": daily_data,
    }


@router.get("/stocks/{code}/intraday")
def stock_intraday(code: str):
    from database import engine
    from services.data_fetcher import fetch_intraday_sina

    bars_df = fetch_intraday_sina(code)
    bars = bars_df.where(bars_df.notna(), None).to_dict(orient="records") if not bars_df.empty else []

    # Get prev_close and float_shares from stock_daily, compute turnover_rate
    prev_close = None
    float_shares = 0
    turnover_rate = None
    try:
        import pandas as pd
        # Get last 2 rows for prev_close, and any row with valid float_shares
        query = "SELECT close, float_shares FROM stock_daily WHERE code = :code ORDER BY date DESC LIMIT 2"
        with engine.connect() as conn:
            df = pd.read_sql_query(query, conn, params={"code": code})
        if len(df) >= 2:
            prev_close = float(df.iloc[1]["close"])
        elif len(df) == 1:
            prev_close = float(df.iloc[0]["close"])
        # float_shares should be the same across rows — use most recent non-zero
        for i in range(len(df)):
            fs = df.iloc[i].get("float_shares")
            if fs and (not isinstance(fs, float) or fs == fs):  # not NaN
                v = float(fs)
                if v > 0:
                    float_shares = v
                    break
        # Compute turnover_rate from intraday total volume
        if float_shares > 0 and bars:
            total_vol = sum(float(b.get("volume") or 0) for b in bars)
            if total_vol > 0:
                turnover_rate = round(total_vol * 100 / float_shares, 2)
    except Exception:
        pass

    return {"bars": bars, "prev_close": prev_close, "float_shares": float_shares, "turnover_rate": turnover_rate}


@router.get("/concepts")
def list_concepts():
    from database import engine
    import pandas as pd
    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(
                "SELECT concept_name, COUNT(*) as stock_count FROM stock_concept GROUP BY concept_name ORDER BY stock_count DESC",
                conn)
        return {"concepts": df.to_dict(orient="records")}
    except Exception:
        return {"concepts": []}


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
