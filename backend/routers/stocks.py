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
    industry: str | None = Query(None),
    industry_name: str | None = Query(None),
    change_pct_min: float | None = Query(None),
    change_pct_max: float | None = Query(None),
    volume_ratio_min: float | None = Query(None),
    concept: str | None = Query(None),
    codes: str | None = Query(None),
    exclude_st: bool = Query(False),
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
        "industry": industry, "industry_name": industry_name,
        "change_pct_min": change_pct_min, "change_pct_max": change_pct_max,
        "volume_ratio_min": volume_ratio_min, "concept": concept,
        "codes": codes,
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
    from services.data_fetcher import fetch_kline_sina, fetch_single_snapshot

    basic_query = "SELECT * FROM stock_basic WHERE code = :code"
    with engine.connect() as conn:
        basic = pd.read_sql_query(basic_query, conn, params={"code": code})

    basic_dict = basic.to_dict(orient="records")[0] if len(basic) > 0 else None

    # Fetch K-line (250 days ≈ 1 year for meaningful MA60 and trend analysis)
    kline_df = fetch_kline_sina(code, days=250)
    if kline_df.empty:
        query = "SELECT * FROM stock_daily WHERE code = :code ORDER BY date DESC LIMIT 250"
        with engine.connect() as conn:
            kline_df = pd.read_sql_query(query, conn, params={"code": code})
    # Filter out rows with zero/negative close (suspended days)
    kline_df = kline_df[kline_df["close"] > 0] if not kline_df.empty else kline_df
    daily_data = kline_df.astype(object).where(kline_df.notna(), None).to_dict(orient="records") if not kline_df.empty else []

    # Enrich latest row with snapshot fundamentals (PE/PB/ROE/market_cap/turnover) for suspended stocks
    if daily_data and daily_data[-1].get("pe_ttm") is None:
        try:
            snap = fetch_single_snapshot(code)
            latest = daily_data[-1]
            for k in ("pe_ttm", "pb", "roe", "market_cap", "turnover_rate", "change_pct"):
                if snap.get(k) is not None:
                    latest[k] = snap.get(k)
        except Exception:
            pass

    return {
        "basic": basic_dict,
        "daily": daily_data,
    }


@router.get("/stocks/{code}/intraday")
def stock_intraday(code: str):
    from database import engine
    from services.data_fetcher import fetch_intraday_sina
    from datetime import date

    bars_df = fetch_intraday_sina(code)
    bars: list[dict] = []

    # Only return intraday bars if data is from today or recent (within 4 calendar days).
    # Live data uses "HH:MM" format; historical data uses "YYYY-MM-DD HH:MM:SS".
    # This filters out suspended stocks (data weeks old) while showing last trading day
    # on holidays/weekends.
    if not bars_df.empty:
        raw_date = str(bars_df.iloc[0]["date"])
        is_live = raw_date.count(":") == 1  # "HH:MM" format = live today
        if is_live:
            bars = bars_df.astype(object).where(bars_df.notna(), None).to_dict(orient="records")
        else:
            from datetime import timedelta
            cutoff = (date.today() - timedelta(days=4)).strftime("%Y-%m-%d")
            if raw_date[:10] >= cutoff:
                bars = bars_df.astype(object).where(bars_df.notna(), None).to_dict(orient="records")

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


@router.get("/stocks/{code}/kline")
def stock_kline(code: str, period: str = Query("daily", pattern="^(daily|weekly|monthly)$")):
    from services.data_fetcher import fetch_stock_history_period
    df = fetch_stock_history_period(code, period)
    kline_data = df.astype(object).where(df.notna(), None).to_dict(orient="records") if not df.empty else []
    return {"kline": kline_data, "period": period}


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


@router.get("/sectors")
def list_sectors():
    from services.data_fetcher import fetch_sector_ranking
    sectors = fetch_sector_ranking()
    return {"sectors": sectors, "count": len(sectors)}


@router.get("/limit-stats")
def limit_stats():
    from services.data_fetcher import fetch_limit_stats
    stats = fetch_limit_stats()
    return {"zt_count": len(stats["zt_list"]), "dt_count": len(stats["dt_list"]),
            "zt_list": stats["zt_list"], "dt_list": stats["dt_list"]}


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
