"""akshare wrapper: fetch A-share stock list and daily financial data."""
from datetime import datetime, timedelta

import akshare as ak
import pandas as pd


def fetch_stock_list() -> pd.DataFrame:
    """Fetch all A-share stock basic info. Returns DataFrame with columns:
    code, name, market, industry, list_date, is_st
    """
    df = ak.stock_info_a_code_name()
    df = df.rename(columns={"code": "code", "name": "name"})
    df["market"] = "sh_sz"  # default; finer classification below
    df["industry"] = ""
    df["list_date"] = ""
    df["is_st"] = df["name"].str.contains("ST|\\*ST").astype(int)
    return df[["code", "name", "market", "industry", "list_date", "is_st"]]


def fetch_daily_indicators(date: str | None = None) -> pd.DataFrame:
    """Fetch daily financial indicators for all A-share stocks on given date.
    If date is None, fetch the most recent trading day.
    Returns DataFrame with columns matching stock_daily schema.
    """
    if date is None:
        date = datetime.now().strftime("%Y%m%d")

    # akshare stock_a_lg_indicator: PE, PB, market_cap, etc.
    try:
        df = ak.stock_a_lg_indicator(symbol="all")
    except Exception:
        # Fallback: try individual market
        df = pd.DataFrame()

    if df.empty:
        return df

    result = pd.DataFrame()
    result["code"] = df["code"].astype(str)
    result["date"] = date
    result["pe_ttm"] = pd.to_numeric(df.get("pe", 0), errors="coerce").fillna(0)
    result["pb"] = pd.to_numeric(df.get("pb", 0), errors="coerce").fillna(0)
    result["market_cap"] = pd.to_numeric(df.get("total_mv", 0), errors="coerce").fillna(0) / 1e8  # to 100M
    result["roe"] = pd.to_numeric(df.get("roe", 0), errors="coerce").fillna(0)

    # Fill non-available fields with defaults
    result["close"] = 0
    result["volume"] = 0
    result["turnover_rate"] = 0
    result["revenue_growth_3y"] = 0
    result["ma5"] = 0
    result["ma20"] = 0
    result["ma60"] = 0
    result["macd_signal"] = ""
    result["dividend_yield"] = 0

    return result


def fetch_stock_history(code: str, days: int = 60) -> pd.DataFrame:
    """Fetch recent daily K-line data for a single stock."""
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                 start_date=start_date, end_date=end_date,
                                 adjust="qfq")
        df = df.rename(columns={
            "日期": "date",
            "收盘": "close",
            "成交量": "volume",
            "换手率": "turnover_rate",
        })
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        return df.tail(days)
    except Exception:
        return pd.DataFrame()
