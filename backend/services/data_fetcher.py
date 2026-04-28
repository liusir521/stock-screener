"""Fetch A-share stock list and daily financial data from Sina."""
from datetime import datetime

import pandas as pd
import requests

SINA_API = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"


def _sina_session():
    s = requests.Session()
    s.trust_env = False
    return s


def _fetch_sina_page(page: int, page_size: int = 100) -> list[dict]:
    """Fetch one page from Sina market center API."""
    session = _sina_session()
    params = {
        "page": page, "num": page_size, "sort": "symbol", "asc": 1,
        "node": "hs_a", "symbol": "", "_s_r_a": "auto",
    }
    r = session.get(SINA_API, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected Sina API response: {r.text[:200]}")
    return data


def _classify_market(symbol: str, code: str) -> str:
    """Classify A-share market by Sina symbol prefix and code pattern."""
    prefix = symbol[:2]
    if prefix == "bj":
        return "bse"
    if prefix == "sh" and code.startswith("688"):
        return "star"
    if prefix == "sz" and code.startswith(("300", "301")):
        return "chinext"
    return "sh_sz"


def fetch_all_sina_data() -> pd.DataFrame:
    """Fetch all A-share stocks with daily indicators from Sina.
    Returns DataFrame with columns for both stock_basic and stock_daily.
    """
    all_rows = []
    page = 1
    while True:
        try:
            rows = _fetch_sina_page(page)
        except Exception as e:
            print(f"  Sina page {page} error: {e}")
            break
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < 100:
            break
        page += 1

    if not all_rows:
        return pd.DataFrame()

    today = datetime.now().strftime("%Y%m%d")

    records = []
    for item in all_rows:
        code = str(item.get("code", ""))
        symbol = str(item.get("symbol", ""))
        records.append({
            # stock_basic fields
            "code": code,
            "name": str(item.get("name", "")),
            "market": _classify_market(symbol, code),
            "industry": "",
            "list_date": "",
            "is_st": 1 if "ST" in str(item.get("name", "")) else 0,
            # stock_daily fields
            "date": today,
            "close": float(item.get("trade", 0) or 0),
            "volume": float(item.get("volume", 0) or 0),
            "turnover_rate": float(item.get("turnoverratio", 0) or 0),
            "pe_ttm": float(item.get("per", 0) or 0),
            "pb": float(item.get("pb", 0) or 0),
            "market_cap": float(item.get("mktcap", 0) or 0) / 1e4,  # 万元 -> 亿
            "nmc": float(item.get("nmc", 0) or 0),  # 流通市值(万元)
            "float_shares": 0,  # computed below
            "roe": 0,
            "revenue_growth_3y": 0,
            "ma5": 0,
            "ma20": 0,
            "ma60": 0,
            "macd_signal": "",
            "dividend_yield": 0,
        })

    df = pd.DataFrame(records)
    # Compute circulating shares: float_shares = nmc(万元) * 10000 / close(元)
    mask = (df["close"] > 0) & (df["nmc"] > 0)
    df.loc[mask, "float_shares"] = df.loc[mask, "nmc"] * 10000 / df.loc[mask, "close"]
    return df


def fetch_stock_list() -> pd.DataFrame:
    """Fetch all A-share stock basic info from Sina."""
    df = fetch_all_sina_data()
    if df.empty:
        return df
    return df[["code", "name", "market", "industry", "list_date", "is_st"]]


def fetch_daily_indicators(date: str | None = None) -> pd.DataFrame:
    """Fetch daily indicators for all A-share stocks from Sina.
    Returns DataFrame with columns matching stock_daily schema.
    """
    df = fetch_all_sina_data()
    if df.empty:
        return df
    daily_cols = ["code", "date", "close", "volume", "turnover_rate",
                  "pe_ttm", "pb", "market_cap", "roe", "revenue_growth_3y",
                  "ma5", "ma20", "ma60", "macd_signal", "dividend_yield"]
    return df[daily_cols]


def _sina_symbol(code: str) -> str:
    """Convert stock code to Sina symbol prefix (sh/sz)."""
    return "sh" + code if code.startswith("6") else "sz" + code


def fetch_kline_sina(code: str, days: int = 60) -> pd.DataFrame:
    """Fetch daily K-line data for a single stock from Sina finance API.
    Returns DataFrame with OHLCV columns.
    """
    import re
    symbol = _sina_symbol(code)
    url = "https://quotes.sina.cn/cn/api/jsonp_v2.php/data/CN_MarketDataService.getKLineData"
    try:
        r = requests.get(url, params={"symbol": symbol, "scale": "240", "ma": "no", "datalen": str(days)}, timeout=15)
        r.raise_for_status()
        # Strip JS comment prefix and JSONP wrapper: /*...*/data([...]);
        text = r.text.strip()
        text = re.sub(r'^/\*.*?\*/\s*', '', text)
        m = re.match(r"^data\((.+)\);?\s*$", text)
        if not m:
            return pd.DataFrame()
        items = __import__("json").loads(m.group(1))
        df = pd.DataFrame(items)
        df = df.rename(columns={
            "day": "date",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
        })
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df.tail(days)
    except Exception:
        return pd.DataFrame()


def fetch_stock_history(code: str, days: int = 60) -> pd.DataFrame:
    """Fetch recent daily K-line data for a single stock using akshare."""
    from datetime import timedelta
    import akshare as ak

    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                 start_date=start_date, end_date=end_date,
                                 adjust="qfq")
        df = df.rename(columns={
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "换手率": "turnover_rate",
        })
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        return df.tail(days)
    except Exception:
        return pd.DataFrame()


def fetch_corp_info(code: str) -> dict[str, str]:
    """Fetch industry and list_date for a single stock from Sina corp pages."""
    import re
    import requests as req
    result = {"industry": "", "list_date": ""}

    try:
        url = f"http://money.finance.sina.com.cn/corp/go.php/vCI_CorpInfo/stockid/{code}/displaytype/4.phtml"
        r = req.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        m = re.search(
            rb'<td[^>]*class="ct"[^>]*>[^<]*</td>\s*<td[^>]*class="cc"[^>]*>.*?<a[^>]*>(\d{4}-\d{2}-\d{2})</a>',
            r.content, re.DOTALL,
        )
        if m:
            result["list_date"] = m.group(1).decode()
    except Exception:
        pass

    try:
        url = f"http://vip.stock.finance.sina.com.cn/corp/go.php/vCI_CorpOtherInfo/stockid/{code}/menu_num/2.phtml"
        r = req.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        raw = r.content
        idx = raw.find(b'colspan="2"')
        if idx > 0:
            chunk = raw[idx:idx + 2000]
            m = re.search(
                rb'<td[^>]*class="ct"[^>]*>\s*([\x80-\xff]{2,10}?)\s*</td>\s*<td[^>]*class="ct"[^>]*>\s*<a',
                chunk,
            )
            if m:
                result["industry"] = m.group(1).strip().decode("gb2312", errors="replace").strip()
    except Exception:
        pass

    return result
    """Fetch recent daily K-line data for a single stock using akshare."""
    from datetime import timedelta
    import akshare as ak

    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                 start_date=start_date, end_date=end_date,
                                 adjust="qfq")
        df = df.rename(columns={
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "换手率": "turnover_rate",
        })
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        return df.tail(days)
    except Exception:
        return pd.DataFrame()
