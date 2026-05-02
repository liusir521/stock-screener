"""MCP Server for stock screener — exposes tools and resources via stdio."""
import os
import sys
from pathlib import Path

# Ensure backend is on path so we can import services
sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("stock-screener")

# ─── helpers ───

from database import engine

def _query_df(sql: str, params: dict | None = None):
    import pandas as pd
    with engine.connect() as conn:
        return pd.read_sql_query(sql, conn, params=params or {})


# ─── Tool: analyze_stock ───

@mcp.tool()
def analyze_stock(code: str, periods: list[str] | None = None) -> dict:
    """对指定A股做多周期技术分析，返回日/周/月K的 MA、MACD、RSI、KDJ、布林带指标。

    Args:
        code: 6位股票代码，如 600519
        periods: 分析周期列表，可选 daily/weekly/monthly，默认 ['daily']
    """
    if periods is None:
        periods = ["daily"]

    from services.data_fetcher import (
        fetch_single_snapshot,
        fetch_stock_history_period,
        fetch_stock_news,
        fetch_stock_notices,
    )
    from services.indicator import sma, ema, macd, rsi, kdj, bollinger, latest_value

    # Basic info
    basic_df = _query_df("SELECT * FROM stock_basic WHERE code = :code", {"code": code})
    if basic_df.empty:
        return {"error": f"未找到股票 {code}"}
    basic_row = basic_df.iloc[0]
    name = str(basic_row["name"])

    # Snapshot fundamentals
    snap = fetch_single_snapshot(code)

    result: dict = {
        "code": code,
        "name": name,
        "basic": {
            "market": str(basic_row.get("market", "")),
            "industry": str(basic_row.get("industry", "")),
            "pe_ttm": snap.get("pe_ttm"),
            "pb": snap.get("pb"),
            "roe": snap.get("roe"),
            "market_cap": snap.get("market_cap"),
            "change_pct": snap.get("change_pct"),
            "turnover_rate": snap.get("turnover_rate"),
        },
        "periods": {},
    }

    for period in periods:
        kline_df = fetch_stock_history_period(code, period=period, days=120)
        if kline_df.empty:
            result["periods"][period] = {"error": "无数据"}
            continue

        closes = kline_df["close"].tolist()
        highs = kline_df["high"].tolist()
        lows = kline_df["low"].tolist()
        volumes = kline_df["volume"].tolist()

        ma5_list = sma(closes, 5)
        ma20_list = sma(closes, 20)
        ma60_list = sma(closes, 60)
        macd_result = macd(closes)
        rsi14_list = rsi(closes, 14)
        kdj_result = kdj(highs, lows, closes)
        boll_result = bollinger(closes, 20)

        result["periods"][period] = {
            "latest_values": {
                "ma5": latest_value(ma5_list),
                "ma20": latest_value(ma20_list),
                "ma60": latest_value(ma60_list),
                "macd_dif": latest_value(macd_result["dif"]),
                "macd_dea": latest_value(macd_result["dea"]),
                "macd_bar": latest_value(macd_result["bar"]),
                "rsi14": latest_value(rsi14_list),
                "kdj_k": latest_value(kdj_result["k"]),
                "kdj_d": latest_value(kdj_result["d"]),
                "kdj_j": latest_value(kdj_result["j"]),
                "boll_upper": latest_value(boll_result["upper"]),
                "boll_middle": latest_value(boll_result["middle"]),
                "boll_lower": latest_value(boll_result["lower"]),
                "close": closes[-1] if closes else None,
                "volume": volumes[-1] if volumes else None,
            },
            "date_count": len(kline_df),
        }

    # News
    try:
        news = fetch_stock_news(code, limit=8)
        notices = fetch_stock_notices(code, limit=5)
        result["news"] = news
        result["notices"] = notices
    except Exception:
        result["news"] = []
        result["notices"] = []

    return result


# ─── Tool: search_stocks ───

@mcp.tool()
def search_stocks(
    keyword: str | None = None,
    market: str | None = None,
    pe_min: float | None = None,
    pe_max: float | None = None,
    pb_min: float | None = None,
    pb_max: float | None = None,
    roe_min: float | None = None,
    market_cap_min: float | None = None,
    market_cap_max: float | None = None,
    dividend_yield_min: float | None = None,
    revenue_growth_min: float | None = None,
    revenue_growth_max: float | None = None,
    industry: str | None = None,
    concept: str | None = None,
    change_pct_min: float | None = None,
    change_pct_max: float | None = None,
    volume_ratio_min: float | None = None,
    exclude_st: bool = False,
    sort_by: str = "code",
    page_size: int = 20,
) -> dict:
    """按基本面和技术面条件筛选A股。

    Returns: {total, items: [{code, name, market, industry, close, pe_ttm, pb, roe, ...}]}
    """
    from services.screener import get_all_stocks_df, apply_filters, paginate

    filters = {k: v for k, v in {
        "keyword": keyword,
        "market": market,
        "pe_min": pe_min,
        "pe_max": pe_max,
        "pb_min": pb_min,
        "pb_max": pb_max,
        "roe_min": roe_min,
        "market_cap_min": market_cap_min,
        "market_cap_max": market_cap_max,
        "dividend_yield_min": dividend_yield_min,
        "revenue_growth_min": revenue_growth_min,
        "revenue_growth_max": revenue_growth_max,
        "industry": industry,
        "concept": concept,
        "change_pct_min": change_pct_min,
        "change_pct_max": change_pct_max,
        "volume_ratio_min": volume_ratio_min,
        "exclude_st": exclude_st,
        "sort_by": sort_by,
        "order": "asc",
    }.items() if v is not None}

    df = get_all_stocks_df()
    filtered = apply_filters(df, filters)
    items, total = paginate(filtered, 1, page_size)

    return {"total": total, "items": items, "page_size": page_size}


# ─── Tool: compare_stocks ───

@mcp.tool()
def compare_stocks(codes: list[str]) -> dict:
    """并排对比多只股票的技术面和基本面（最多10只）。

    Args:
        codes: 股票代码列表，如 ['600519', '000858']
    """
    if len(codes) > 10:
        codes = codes[:10]

    from services.data_fetcher import fetch_single_snapshot
    from services.indicator import macd, rsi, latest_value

    stocks = []
    for code in codes:
        basic_df = _query_df("SELECT * FROM stock_basic WHERE code = :code", {"code": code})
        if basic_df.empty:
            continue
        basic_row = basic_df.iloc[0]
        snap = fetch_single_snapshot(code)

        # Daily K-line for quick indicators
        kline_df = _query_df(
            "SELECT close FROM stock_daily WHERE code = :code AND close > 0 ORDER BY date DESC LIMIT 60",
            {"code": code},
        )
        closes = list(reversed(kline_df["close"].tolist())) if not kline_df.empty else []

        macd_result = macd(closes) if len(closes) >= 26 else None
        rsi14_list = rsi(closes, 14) if len(closes) >= 15 else None

        stocks.append({
            "code": code,
            "name": str(basic_row["name"]),
            "market": str(basic_row.get("market", "")),
            "industry": str(basic_row.get("industry", "")),
            "pe_ttm": snap.get("pe_ttm"),
            "pb": snap.get("pb"),
            "roe": snap.get("roe"),
            "market_cap": snap.get("market_cap"),
            "change_pct": snap.get("change_pct"),
            "turnover_rate": snap.get("turnover_rate"),
            "macd_dif": latest_value(macd_result["dif"]) if macd_result else None,
            "macd_dea": latest_value(macd_result["dea"]) if macd_result else None,
            "rsi14": latest_value(rsi14_list) if rsi14_list else None,
        })

    return {"stocks": stocks, "count": len(stocks)}


# ─── Tool: get_market_breadth ───

@mcp.tool()
def get_market_breadth() -> dict:
    """获取今日市场全景：涨停板、跌停板统计、行业板块涨跌排名。"""
    from services.data_fetcher import fetch_limit_stats, fetch_sector_ranking

    limit_stats = fetch_limit_stats()
    sectors = fetch_sector_ranking()

    return {
        "zt_count": len(limit_stats["zt_list"]),
        "dt_count": len(limit_stats["dt_list"]),
        "zt_list": limit_stats["zt_list"][:20],
        "dt_list": limit_stats["dt_list"][:20],
        "top_sectors": sectors[:10],
    }


# ─── Tool: get_stock_news ───

@mcp.tool()
def get_stock_news(code: str) -> dict:
    """获取个股近期新闻和公司公告，用于消息面分析。

    Args:
        code: 6位股票代码，如 600519
    """
    from services.data_fetcher import fetch_stock_news, fetch_stock_notices

    basic_df = _query_df("SELECT * FROM stock_basic WHERE code = :code", {"code": code})
    name = str(basic_df.iloc[0]["name"]) if not basic_df.empty else code

    news = fetch_stock_news(code, limit=15)
    notices = fetch_stock_notices(code, limit=10)

    return {
        "code": code,
        "name": name,
        "news": news,
        "notices": notices,
    }


# ─── Resources ───

@mcp.resource("stock://basic")
def resource_stock_basic() -> str:
    """A股股票基本信息全表（JSON格式）。"""
    import json
    df = _query_df("SELECT * FROM stock_basic")
    return json.dumps(df.astype(object).where(df.notna(), None).to_dict(orient="records"), ensure_ascii=False)


@mcp.resource("stock://concepts")
def resource_stock_concepts() -> str:
    """概念板块映射表（JSON格式）。"""
    import json
    df = _query_df("SELECT concept_name, COUNT(*) as stock_count FROM stock_concept GROUP BY concept_name ORDER BY stock_count DESC")
    return json.dumps(df.astype(object).where(df.notna(), None).to_dict(orient="records"), ensure_ascii=False)


@mcp.resource("stock://sectors")
def resource_sectors() -> str:
    """行业板块排名（JSON格式）。"""
    import json
    from services.data_fetcher import fetch_sector_ranking
    sectors = fetch_sector_ranking()
    return json.dumps(sectors, ensure_ascii=False)


@mcp.resource("stock://daily/{code}")
def resource_stock_daily(code: str) -> str:
    """单只股票日线历史数据，最近120条。

    Args:
        code: 6位股票代码
    """
    import json
    df = _query_df(
        "SELECT * FROM stock_daily WHERE code = :code ORDER BY date DESC LIMIT 120",
        {"code": code},
    )
    return json.dumps(
        df.astype(object).where(df.notna(), None).to_dict(orient="records"),
        ensure_ascii=False,
    )


# ─── Tool: factor_score ───

@mcp.tool()
def factor_score(code: str) -> dict:
    """对单只股票进行多因子评分（估值/成长/质量/动量四维），返回综合得分和分项得分。

    Args:
        code: 6位股票代码，如 600519
    """
    from services.factor import score_stock
    return score_stock(code)


# ─── Tool: factor_rank ───

@mcp.tool()
def factor_rank(
    market: str | None = None,
    industry: str | None = None,
    exclude_st: bool = True,
    top_n: int = 20,
) -> dict:
    """按多因子综合得分排名，返回Top N股票。

    Args:
        market: 市场过滤，可选 sh_sz/chinext/star/bse
        industry: 行业过滤，如 '白酒'
        exclude_st: 是否排除ST股
        top_n: 返回数量，默认20
    """
    from services.factor import rank_stocks
    results = rank_stocks(market=market, industry=industry, exclude_st=exclude_st, top_n=top_n)
    return {"count": len(results), "ranking": results}


# ─── Tool: recognize_patterns ───

@mcp.tool()
def recognize_patterns(code: str) -> dict:
    """识别股票K线形态：双重底/双重顶/头肩底/头肩顶/上升三角形/下降三角形，以及支撑压力位。

    Args:
        code: 6位股票代码，如 600519
    """
    from services.data_fetcher import fetch_stock_history_period
    from services.pattern import detect_patterns, find_support_resistance

    basic_df = _query_df("SELECT * FROM stock_basic WHERE code = :code", {"code": code})
    name = str(basic_df.iloc[0]["name"]) if not basic_df.empty else code

    kline_df = fetch_stock_history_period(code, period="daily", days=120)
    if kline_df.empty:
        kline_df = _query_df(
            "SELECT * FROM stock_daily WHERE code = :code AND close > 0 ORDER BY date DESC LIMIT 120",
            {"code": code},
        )
    if kline_df.empty:
        return {"code": code, "name": name, "error": "无K线数据"}

    highs = kline_df["high"].tolist()
    lows = kline_df["low"].tolist()
    closes = kline_df["close"].tolist()
    volumes = kline_df["volume"].tolist() if "volume" in kline_df.columns else None

    patterns = detect_patterns(highs, lows, closes, volumes)
    sr = find_support_resistance(highs, lows, closes)

    return {
        "code": code,
        "name": name,
        "patterns": patterns,
        "support_resistance": sr,
        "data_points": len(closes),
    }


# ─── Entry point ───

if __name__ == "__main__":
    mcp.run(transport="stdio")
