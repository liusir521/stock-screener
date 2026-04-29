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
            "change_pct": float(item.get("changepercent", 0) or 0),
            "volume_ratio": 0,
        })

    df = pd.DataFrame(records)
    # Compute circulating shares: float_shares = nmc(万元) * 10000 / close(元)
    mask = (df["close"] > 0) & (df["nmc"] > 0)
    df.loc[mask, "float_shares"] = df.loc[mask, "nmc"] * 10000 / df.loc[mask, "close"]
    # Compute ROE from PB and PE: ROE(%) = PB / PE * 100
    roe_mask = (df["pe_ttm"] > 0) & (df["pb"] > 0)
    df.loc[roe_mask, "roe"] = (df.loc[roe_mask, "pb"] / df.loc[roe_mask, "pe_ttm"]) * 100
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
                  "ma5", "ma20", "ma60", "macd_signal", "dividend_yield",
                  "change_pct", "volume_ratio"]
    return df[daily_cols]


def _sina_symbol(code: str) -> str:
    """Convert stock code to Sina symbol prefix (sh/sz/bj)."""
    if code.startswith("6"):
        return "sh" + code
    elif code.startswith(("8", "4", "92")):
        return "bj" + code
    return "sz" + code


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


def fetch_intraday_sina(code: str) -> pd.DataFrame:
    """Fetch today's 1-minute K-line bars for intraday time-sharing chart.
    Returns DataFrame with date (HH:MM), close, volume columns. Empty if market closed.
    """
    import re
    symbol = _sina_symbol(code)
    url = "https://quotes.sina.cn/cn/api/jsonp_v2.php/data/CN_MarketDataService.getKLineData"
    try:
        r = requests.get(url, params={"symbol": symbol, "scale": "1", "ma": "no", "datalen": "250"}, timeout=15)
        r.raise_for_status()
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
        return df
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


def fetch_stock_history_period(code: str, period: str = "weekly", days: int = 120) -> pd.DataFrame:
    """Fetch K-line for a single stock at a given period (daily/weekly/monthly) using akshare."""
    from datetime import timedelta
    import akshare as ak

    end_date = datetime.now().strftime("%Y%m%d")
    multiplier = 1 if period == "daily" else (5 if period == "weekly" else 21)
    start_date = (datetime.now() - timedelta(days=days * multiplier * 2)).strftime("%Y%m%d")
    try:
        df = ak.stock_zh_a_hist(symbol=code, period=period,
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


def compute_volume_ratio(code: str) -> float:
    """Fetch 6-day K-line and return volume_ratio = today_vol / avg_prev_5_vol."""
    df = fetch_kline_sina(code, days=6)
    if df.empty or len(df) < 2:
        return 0.0
    volumes = df["volume"].tolist()
    today_vol = volumes[-1]
    prev_vols = volumes[:-1]
    if not prev_vols or sum(prev_vols) == 0:
        return 0.0
    avg_vol = sum(prev_vols) / len(prev_vols)
    if avg_vol == 0:
        return 0.0
    return round(float(today_vol) / avg_vol, 2)


def batch_compute_volume_ratios(codes: list[str], max_workers: int = 15) -> dict[str, float]:
    """Compute volume ratios for many stocks using a thread pool."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results: dict[str, float] = {}
    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        fut = {pool.submit(compute_volume_ratio, c): c for c in codes}
        for f in as_completed(fut):
            c = fut[f]
            try:
                results[c] = f.result()
            except Exception:
                results[c] = 0.0
            done += 1
            if done % 500 == 0:
                print(f"  volume_ratio: {done}/{len(codes)}")
    return results


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


# ----- Sector ranking (cached 60s) -----
_sector_cache: dict[str, tuple[float, list[dict]]] = {}


def fetch_sector_ranking() -> list[dict]:
    """Fetch industry sector performance ranking from同花顺. Cached 60s."""
    import time
    from io import StringIO
    import pandas as pd
    from bs4 import BeautifulSoup

    now = time.time()
    entry = _sector_cache.get("ranking")
    if entry and now - entry[0] < 60:
        return entry[1]

    try:
        s = _sina_session()
        r = s.get("https://q.10jqka.com.cn/thshy/",
                  headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        r.raise_for_status()
        decoded = r.content.decode("gbk", errors="replace")

        # Parse table data
        tables = pd.read_html(StringIO(decoded))
        df = tables[0]
        df.columns = [str(c) for c in df.columns]

        # Parse sector codes from links
        soup = BeautifulSoup(decoded, "html.parser")
        code_map: dict[str, str] = {}
        for row in soup.select("table tbody tr"):
            cells = row.find_all("td")
            if len(cells) >= 2:
                name_a = cells[1].find("a")
                if name_a and "thshy/detail/code/" in name_a.get("href", ""):
                    href = name_a["href"]
                    code = href.rstrip("/").split("/")[-1]
                    name = name_a.get_text(strip=True)
                    code_map[name] = code

        # Map columns
        col_map = {"板块": "name", "涨跌幅(%)": "change_pct", "领涨股": "lead_stock"}
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

        # Find lead stock change column (涨跌幅(%).1)
        lead_chg_col = next((c for c in df.columns if "涨跌幅" in str(c) and "." in str(c)), None)

        result: list[dict] = []
        for _, row in df.iterrows():
            name = str(row.get("name", ""))
            r: dict = {
                "code": code_map.get(name, ""),
                "name": name,
                "change_pct": float(row.get("change_pct", 0) or 0),
                "turnover_rate": 0,  # not available on THS listing page
                "lead_stock": str(row.get("lead_stock", "")),
                "lead_stock_change": float(row.get(lead_chg_col, 0) or 0) if lead_chg_col else 0,
            }
            result.append(r)

        _sector_cache["ranking"] = (now, result)
        return result
    except Exception:
        entry = _sector_cache.get("ranking")
        return entry[1] if entry else []


# ----- Industry constituent stocks (cached 300s) -----
_industry_stocks_cache: dict[str, tuple[float, list[str]]] = {}


def fetch_industry_stocks(board_code: str) -> list[str]:
    """Get stock codes in a同花顺 industry board. Cached 300s."""
    import time
    from io import StringIO
    import pandas as pd

    now = time.time()
    entry = _industry_stocks_cache.get(board_code)
    if entry and now - entry[0] < 300:
        return entry[1]

    try:
        s = _sina_session()
        url = f"http://q.10jqka.com.cn/thshy/detail/code/{board_code}/"
        r = s.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        r.raise_for_status()
        decoded = r.content.decode("gbk", errors="replace")

        tables = pd.read_html(StringIO(decoded))
        df = tables[0]
        df.columns = [str(c) for c in df.columns]

        code_col = "代码" if "代码" in df.columns else df.columns[1]
        result = df[code_col].astype(str).tolist()
        _industry_stocks_cache[board_code] = (now, result)
        return result
    except Exception:
        entry = _industry_stocks_cache.get(board_code)
        return entry[1] if entry else []


# ----- Limit-up/down stats (cached 60s) -----
_limit_cache: dict[str, tuple[float, list[dict]]] = {}


def _get_limit_pct(market: str, is_st: bool) -> float:
    """Return the daily price limit percentage for a stock."""
    if market in ("star", "chinext"):
        return 20.0
    elif market == "bse":
        return 30.0
    elif is_st:
        return 5.0
    return 10.0


def _is_at_limit(change_pct: float, market: str, is_st: bool, up: bool) -> bool:
    """Check if a stock is at its daily price limit (up or down).
    Uses threshold (limit - 0.15) to approximate exact limit price calculation.
    Counts verified against market data (ZT=119, DT≈39-40).
    """
    limit = _get_limit_pct(market, is_st)
    threshold = limit - 0.15
    return change_pct >= threshold if up else change_pct <= -threshold


def _is_ipo(name: str, change_pct: float) -> bool:
    """Check if a stock is a recent IPO (no daily price limit)."""
    if name.startswith("N") or name.startswith("C"):
        return True
    if change_pct > 40 or change_pct < -40:
        return True
    return False


def _fetch_limit_stats_from_db() -> dict:
    """Compute limit-up/down stocks from stock_daily table using change_pct thresholds."""
    from database import engine
    import pandas as pd

    query = """
        SELECT b.code, b.name, b.market, b.industry, b.is_st,
               d.change_pct, d.close, d.volume, d.turnover_rate
        FROM stock_basic b
        JOIN stock_daily d ON b.code = d.code
            AND d.date = (SELECT MAX(date) FROM stock_daily WHERE code = b.code)
    """
    with engine.connect() as conn:
        df = pd.read_sql_query(query, conn)

    ipo_mask = df.apply(lambda r: _is_ipo(str(r["name"]), r["change_pct"]), axis=1)
    df = df[~ipo_mask]

    zt_mask = df.apply(lambda r: _is_at_limit(r["change_pct"], r["market"], r["is_st"], up=True), axis=1)
    dt_mask = df.apply(lambda r: _is_at_limit(r["change_pct"], r["market"], r["is_st"], up=False), axis=1)

    zt_df = df[zt_mask].copy()
    dt_df = df[dt_mask].copy()

    zt_list: list[dict] = []
    for _, r in zt_df.iterrows():
        zt_list.append({
            "code": str(r["code"]), "name": str(r["name"]),
            "change_pct": float(r["change_pct"]), "industry": str(r.get("industry", "")),
            "board_count": 0, "seal_volume": 0, "first_seal_time": "",
        })

    dt_list: list[dict] = []
    for _, r in dt_df.iterrows():
        dt_list.append({
            "code": str(r["code"]), "name": str(r["name"]),
            "change_pct": float(r["change_pct"]), "industry": str(r.get("industry", "")),
        })

    return {"zt_list": zt_list, "dt_list": dt_list}


def _enrich_with_eastmoney(zt_list: list[dict]) -> list[dict]:
    """Try to enrich ZT list with board_count/seal_volume/first_seal_time from East Money."""
    import requests as req
    try:
        url = "https://push2ex.eastmoney.com/getTopicZTPool"
        params = {
            "ut": "7eea3edcaed734bea9cbfc24409ed989",
            "dpt": "wz.ztzt",
            "Pageindex": "0",
            "pagesize": "200",
            "sort": "fbt:asc",
            "date": datetime.now().strftime("%Y%m%d"),
        }
        r = req.get(url, params=params, timeout=10)
        data = r.json()
        pool = data.get("data", {}).get("pool", []) if data.get("data") else []
        if not pool:
            return zt_list

        # Build enrichment lookup
        enrich: dict[str, dict] = {}
        for item in pool:
            c = str(item.get("c", ""))
            enrich[c] = {
                "board_count": int(item.get("lbc", 0) or 0),
                "seal_volume": float(item.get("fund", 0) or 0),
                "first_seal_time": str(item.get("fbt", "")),
            }

        for zt in zt_list:
            if zt["code"] in enrich:
                zt.update(enrich[zt["code"]])
    except Exception:
        pass
    return zt_list


def fetch_limit_stats() -> dict:
    """Fetch limit-up and limit-down stock lists. Cached 60s."""
    import time

    now = time.time()
    entry = _limit_cache.get("stats")
    if entry and now - entry[0] < 60:
        return entry[1]

    result = _fetch_limit_stats_from_db()
    result["zt_list"] = _enrich_with_eastmoney(result["zt_list"])
    result["zt_list"].sort(key=lambda x: x.get("board_count", 0), reverse=True)

    _limit_cache["stats"] = (now, result)
    return result


def fetch_concept_list() -> list[dict]:
    """Fetch available concept board names from akshare THS."""
    import akshare as ak
    try:
        df = ak.stock_board_concept_name_ths()
        return df.to_dict(orient="records") if not df.empty else []
    except Exception:
        return []


def fetch_concept_stocks(symbol: str) -> list[str]:
    """Fetch stock codes belonging to a concept board."""
    import akshare as ak
    try:
        df = ak.stock_board_concept_cons_ths(symbol=symbol)
        if df.empty:
            return []
        # Column may be '代码' or 'code'
        code_col = "代码" if "代码" in df.columns else df.columns[0]
        return df[code_col].astype(str).tolist()
    except Exception:
        return []


def batch_fetch_concepts(top_n: int = 80) -> list[dict]:
    """Fetch top N concept boards and their stock mappings. Returns list of {code, concept_name}."""
    import akshare as ak
    from concurrent.futures import ThreadPoolExecutor, as_completed

    concepts = fetch_concept_list()
    if not concepts:
        return []

    # Sort by some metric if available, otherwise take first top_n
    # The THS concept list may have '涨跌幅' or '换手率' columns
    if "换手率" in concepts[0]:
        concepts.sort(key=lambda x: float(x.get("换手率", 0) or 0), reverse=True)
    concepts = concepts[:top_n]

    # Build code → concept_name mapping
    code_concepts: dict[str, list[str]] = {}
    codes = [c.get("代码", c.get("code", "")) for c in concepts]

    print(f"  Fetching constituents for {len(codes)} concept boards...")
    done = 0
    with ThreadPoolExecutor(max_workers=10) as pool:
        fut = {pool.submit(fetch_concept_stocks, code): (code, c) for code, c in zip(codes, concepts)}
        for f in as_completed(fut):
            board_code, concept = fut[f]
            try:
                stocks = f.result()
            except Exception:
                stocks = []
            name = concept.get("name", concept.get("板块名称", board_code))
            for s in stocks:
                code_concepts.setdefault(s, []).append(name)
            done += 1
            if done % 20 == 0:
                print(f"    concepts: {done}/{len(codes)}")

    result = [{"code": k, "concept_name": v} for k, vs in code_concepts.items() for v in vs]
    print(f"  Concept mapping: {len(result)} stock-concept pairs for {len(code_concepts)} stocks")
    return result
