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

    # Fetch K-line (120 trading days ≈ 6 months)
    kline_df = fetch_kline_sina(code, days=120)
    if kline_df.empty:
        query = "SELECT * FROM stock_daily WHERE code = :code ORDER BY date DESC LIMIT 120"
        with engine.connect() as conn:
            kline_df = pd.read_sql_query(query, conn, params={"code": code})
    # Filter out rows with zero/negative close (suspended days)
    kline_df = kline_df[kline_df["close"] > 0] if not kline_df.empty else kline_df
    daily_data = kline_df.astype(object).where(kline_df.notna(), None).to_dict(orient="records") if not kline_df.empty else []

    # Compute turnover_rate for all rows from volume and float_shares
    if daily_data:
        float_shares = 0.0
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
                if vol > 0:
                    d["turnover_rate"] = round(vol * 100 / float_shares, 2)

    # For suspended stocks: fill gap between last K-line date and the last known trading day
    # with fixed-price rows. Only fill weekdays (Mon–Fri), and cap at the most recent
    # trading date in the database (to avoid filling holidays like May Day).
    if daily_data:
        last_close = float(daily_data[-1]["close"])
        last_date_str = str(daily_data[-1]["date"])
        last_date = pd.to_datetime(last_date_str).date()
        yesterday = pd.Timestamp.now().date()

        # Find the last actual trading day from the database (any stock with close > 0)
        last_trading = None
        try:
            max_date_query = "SELECT MAX(date) FROM stock_daily WHERE close > 0"
            with engine.connect() as conn:
                row = conn.execute(text(max_date_query)).fetchone()
                if row and row[0]:
                    last_trading = pd.to_datetime(row[0]).date()
        except Exception:
            pass

        upper_bound = min(yesterday, last_trading) if last_trading else yesterday
        gap_days = (upper_bound - last_date).days
        if gap_days > 2:
            from datetime import timedelta
            d = last_date + timedelta(days=1)
            while d < upper_bound:
                if d.weekday() < 5:  # Mon=0 ... Fri=4
                    daily_data.append({
                        "date": d.strftime("%Y-%m-%d"),
                        "open": last_close, "high": last_close, "low": last_close,
                        "close": last_close, "volume": 0.0,
                    })
                d += timedelta(days=1)
        # Enrich latest row with snapshot fundamentals (PE/PB/ROE/market_cap)
        if daily_data[-1].get("pe_ttm") is None:
            try:
                snap = fetch_single_snapshot(code)
                latest = daily_data[-1]
                for k in ("pe_ttm", "pb", "roe", "market_cap", "change_pct"):
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


@router.get("/indicators")
def list_indicators():
    """列出所有注册的技术指标及其参数。"""
    from services.indicator import get_indicator_registry
    registry = get_indicator_registry()
    return {
        "indicators": list(registry.values()),
        "count": len(registry),
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


@router.get("/dragon-tiger")
def dragon_tiger(date: str | None = Query(None)):
    """龙虎榜数据：上榜股票的买卖席位和净买入。"""
    from services.fund_flow import fetch_dragon_tiger
    return fetch_dragon_tiger(date)


@router.get("/northbound-flow")
def northbound_flow(days: int = Query(20, ge=1, le=60)):
    """北向资金净流入历史。"""
    from services.fund_flow import fetch_northbound_flow
    return fetch_northbound_flow(days)


@router.get("/margin-stats")
def margin_stats():
    """全市场融资融券余额统计。"""
    from services.fund_flow import fetch_margin_stats
    return fetch_margin_stats()


@router.get("/stocks/{code}/northbound")
def stock_northbound(code: str):
    """单只股票北向资金持股数据。"""
    from services.fund_flow import fetch_northbound_holdings
    return fetch_northbound_holdings(code)


@router.get("/stocks/{code}/financials")
def stock_financials(code: str):
    """个股财务三表摘要。"""
    from services.financials import fetch_financial_summary
    return fetch_financial_summary(code)


@router.get("/daily-report")
def daily_report():
    """Generate AI daily market report."""
    import requests
    from datetime import datetime, date
    from services.data_fetcher import fetch_limit_stats, fetch_sector_ranking
    from services.factor import rank_stocks

    # 1. Market breadth
    limits = fetch_limit_stats()
    zt_count = limits.get("zt_count", len(limits.get("zt_list", [])))
    dt_count = limits.get("dt_count", len(limits.get("dt_list", [])))

    # 2. Sector ranking (top 5)
    sectors = fetch_sector_ranking()
    top5_sectors = sectors[:5]

    # 3. Factor-ranked stocks (top 5)
    top5_stocks = rank_stocks(top_n=5)

    # 4. Build markdown tables
    sector_lines = [
        "| 板块 | 涨跌幅 | 领涨股 | 股票数 |",
        "|------|--------|--------|--------|",
    ]
    for s in top5_sectors:
        sector_lines.append(
            f"| {s['name']} | {s['change_pct']}% | {s['lead_stock']}({s['lead_stock_change']}%) | {s['stock_count']} |"
        )
    sector_table = "\n".join(sector_lines)

    factor_lines = [
        "| 代码 | 名称 | 综合得分 | 估值 | 成长 | 质量 | 动量 |",
        "|------|------|----------|------|------|------|------|",
    ]
    for s in top5_stocks:
        f = s["factors"]
        factor_lines.append(
            f"| {s['code']} | {s['name']} | {s['composite']} | {f['valuation']['score']} | {f['growth']['score']} | {f['quality']['score']} | {f['momentum']['score']} |"
        )
    factor_table = "\n".join(factor_lines)

    # 5. Build prompt
    prompt = f"""请根据以下A股市场数据生成一份今日市场日报（500字以内，Markdown格式）：

## 市场情绪
涨停{zt_count}只，跌停{dt_count}只

## 板块TOP5
{sector_table}

## 因子排名TOP5
{factor_table}

请包含：市场概况(1-2句)、情绪解读、板块分析、个股关注，用通俗易懂的语言。"""

    today_str = date.today().strftime("%Y-%m-%d")
    generated_at = datetime.now().isoformat()

    # 6. Call AI agent (non-streaming, one-shot)
    try:
        from services.agent import _api_params
        api_url, model, api_key = _api_params()

        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 2048,
        }

        resp = requests.post(
            f"{api_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
            timeout=120,
        )

        if resp.status_code == 200:
            report = resp.json()["choices"][0]["message"]["content"]
        else:
            raise RuntimeError(f"API error: {resp.status_code}")
    except Exception:
        # Fallback: stats-only summary
        mood = "偏暖" if zt_count > dt_count * 2 else ("偏冷" if dt_count > zt_count * 2 else "中性")
        report = f"""## 今日市场日报 ({today_str})

> AI 报告生成失败，以下为基础数据统计。

### 市场情绪
- 涨停: **{zt_count}** 只
- 跌停: **{dt_count}** 只
- 市场情绪: **{mood}**

### 板块 TOP5
{sector_table}

### 因子排名 TOP5
{factor_table}

---
*数据来源: Sina Finance, 因子模型 v1.0*"""

    return {"report": report, "date": today_str, "generated_at": generated_at}
