"""Financial statements data fetching module using akshare.

Uses 同花顺 (THS) financial APIs for abstract metrics, balance sheet, and
cash flow data. All values are parsed from string-with-unit format (e.g.,
'272.43亿', '52.22%') into plain floats.
"""
import pandas as pd
from sqlalchemy import text

from database import engine


# ---------------------------------------------------------------------------
# Value parsing helpers
# ---------------------------------------------------------------------------

def _parse_float(v) -> float:
    """Parse a financial data cell into a float.

    akshare THS APIs return values as strings with unit suffixes:
      '272.43亿'  -> 272.43 (100M CNY)
      '7672.54万' -> 0.77  (10k CNY -> 100M CNY)
      '52.22%'    -> 52.22 (percent)
      '21.7600'   -> 21.76 (plain number)
      False/None  -> 0.0
    """
    if v is None or v is False:
        return 0.0
    if isinstance(v, (int, float)):
        if pd.isna(v):
            return 0.0
        return float(v)
    s = str(v).strip()
    if not s:
        return 0.0
    # Remove commas
    s = s.replace(",", "")
    try:
        if s.endswith("亿"):
            return round(float(s[:-1]), 2)
        elif s.endswith("万"):
            return round(float(s[:-1]) / 10000, 4)
        elif s.endswith("%"):
            return round(float(s[:-1]), 2)
        else:
            return round(float(s), 2)
    except (ValueError, TypeError):
        return 0.0


def _col_val(row, *candidates, default=0.0) -> float:
    """Try multiple column-name candidates on a DataFrame row.

    Returns the first non-None, non-False value parsed via _parse_float,
    or *default* if none match.
    """
    for c in candidates:
        v = row.get(c)
        if v is not None and v is not False and v != "":
            return _parse_float(v)
    return default


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_financial_summary(code: str) -> dict:
    """Fetch key financial metrics for a single stock.

    Data sources (all akshare THS):
      1. stock_financial_abstract_ths   – abstract  (revenue, profit, margins, ROE, …)
      2. stock_financial_debt_ths       – balance sheet (assets, liabilities, equity)
      3. stock_financial_cash_ths       – cash flow   (operating cash flow)

    Returns a dict with standardised keys; missing fields default to 0 / "".
    """
    import akshare as ak

    result: dict = {
        "code": code,
        "name": "",
        "period": "",
        "revenue": 0.0,
        "net_profit": 0.0,
        "total_assets": 0.0,
        "total_liabilities": 0.0,
        "equity": 0.0,
        "operating_cf": 0.0,
        "gross_margin": 0.0,
        "net_margin": 0.0,
        "roe": 0.0,
        "debt_ratio": 0.0,
        "eps": 0.0,
        "bvps": 0.0,
    }

    # ---- 1. 同花顺财务摘要 (abstract – richest single source) ----
    # Sorted OLDEST-FIRST → use iloc[-1] for latest.
    try:
        df = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
        if not df.empty:
            row = df.iloc[-1]

            result["period"] = str(row.get("报告期", ""))

            result["revenue"] = _col_val(row, "营业总收入", "营业收入")
            result["net_profit"] = _col_val(row, "净利润", "归属母公司净利润")
            result["gross_margin"] = _col_val(row, "销售毛利率", "毛利率")
            result["net_margin"] = _col_val(row, "销售净利率", "净利率")
            result["roe"] = _col_val(row, "净资产收益率", "净资产收益率(ROE)")
            result["debt_ratio"] = _col_val(row, "资产负债率")
            result["eps"] = _col_val(row, "基本每股收益", "每股收益")
            result["bvps"] = _col_val(row, "每股净资产")
    except Exception:
        pass

    # ---- 2. 资产负债表 (balance sheet – total assets, liabilities, equity) ----
    # Sorted NEWEST-FIRST → use iloc[0] for latest.
    try:
        df_bs = ak.stock_financial_debt_ths(symbol=code, indicator="按报告期")
        if not df_bs.empty:
            row = df_bs.iloc[0]

            if not result["period"]:
                result["period"] = str(row.get("报告期", ""))

            # THS balance sheet has both '*' prefixed summary columns and
            # non-prefixed detail columns; try both.
            result["total_assets"] = _col_val(row, "资产合计", "*资产合计")
            result["total_liabilities"] = _col_val(row, "负债合计", "*负债合计")
            result["equity"] = _col_val(
                row,
                "归属于母公司股东权益合计",
                "*归属于母公司股东权益合计",
                "*归属母公司股东权益合计",
                "归属母公司股东权益合计",
                "所有者权益（或股东权益）合计",
                "*所有者权益（或股东权益）合计",
            )
    except Exception:
        pass

    # ---- 3. 现金流量表 (cash flow – operating cash flow) ----
    # Sorted NEWEST-FIRST → use iloc[0] for latest.
    try:
        df_cf = ak.stock_financial_cash_ths(symbol=code, indicator="按报告期")
        if not df_cf.empty:
            row = df_cf.iloc[0]

            if not result["period"]:
                result["period"] = str(row.get("报告期", ""))

            result["operating_cf"] = _col_val(
                row,
                "经营活动产生的现金流量净额",
                "*经营活动产生的现金流量净额",
            )
    except Exception:
        pass

    # ---- 4. Fallback: fund flow (name only) ----
    if not result["name"]:
        try:
            market = "sh" if code.startswith("6") else "sz"
            if not code.startswith(("8", "4", "92")):
                df_ff = ak.stock_individual_fund_flow(stock=code, market=market)
                if not df_ff.empty and "名称" in df_ff.columns:
                    result["name"] = str(df_ff.iloc[0]["名称"])
        except Exception:
            pass

    return result


def fetch_financial_growth(code: str) -> dict:
    """Fetch YoY revenue and profit growth rates over multiple periods.

    Returns:
        {
            "code": "600519",
            "revenue_growth": [{"period": "2025", "value": 15.2}, ...],
            "profit_growth":  [{"period": "2025", "value": 14.8}, ...],
        }
    """
    import akshare as ak

    result: dict = {
        "code": code,
        "revenue_growth": [],
        "profit_growth": [],
    }

    # ---- 1. 同花顺财务摘要 (multi-period with YoY growth columns) ----
    try:
        df = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
        if not df.empty:
            # Walk rows newest-first (df is oldest-first); take up to 5 years
            for _, row in reversed(list(df.iterrows())):
                period_raw = str(row.get("报告期", ""))
                year = period_raw[:4] if period_raw else ""
                if not year:
                    continue

                rev_g = _col_val(row, "营业总收入同比增长率")
                if rev_g != 0.0 and not any(
                    g["period"] == year for g in result["revenue_growth"]
                ):
                    result["revenue_growth"].append({"period": year, "value": rev_g})

                np_g = _col_val(row, "净利润同比增长率")
                if np_g != 0.0 and not any(
                    g["period"] == year for g in result["profit_growth"]
                ):
                    result["profit_growth"].append({"period": year, "value": np_g})

                if len(result["revenue_growth"]) >= 5 and len(result["profit_growth"]) >= 5:
                    break

            if result["revenue_growth"] or result["profit_growth"]:
                return result
    except Exception:
        pass

    # ---- 2. Fallback: Sina finance report API ----
    try:
        import requests

        prefix = "sh" if code.startswith("6") else "sz"
        url = "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022"
        params = {
            "paperCode": f"{prefix}{code}",
            "source": "gjzb",
            "type": "0",
            "page": "1",
            "num": "5",
        }
        r = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        data = r.json()
        report_list = data.get("result", {}).get("data", {}).get("report_list", {})
        if report_list:
            for period_key, period_data in report_list.items():
                year = period_key[:4] if period_key else ""
                items = period_data.get("data", [])
                for item in items:
                    title = str(item.get("item_title", ""))
                    raw_val = item.get("item_value")
                    if raw_val is None:
                        continue
                    try:
                        val = round(float(raw_val), 2)
                    except (ValueError, TypeError):
                        continue
                    if "营业总收入增长率" in title and not any(
                        g["period"] == year for g in result["revenue_growth"]
                    ):
                        result["revenue_growth"].append({"period": year, "value": val})
                    elif "净利润同比增长率" in title and not any(
                        g["period"] == year for g in result["profit_growth"]
                    ):
                        result["profit_growth"].append({"period": year, "value": val})
    except Exception:
        pass

    return result


def screen_by_financials(
    min_roe: float = 0,
    min_revenue_growth: float = 0,
    min_net_margin: float = 0,
    max_debt_ratio: float = 100,
    limit: int = 50,
) -> list[dict]:
    """Screen stocks by financial criteria using the local database.

    Primary filters (roe, revenue_growth_3y) hit the local SQLite DB for speed.
    Secondary filters (net_margin, debt_ratio) are applied via a second-pass API
    fetch only when their thresholds are non-default (fewer candidates to check).

    Returns a list of matching stock dicts sorted by ROE descending.
    """
    query = text("""
        SELECT b.code, b.name, d.roe, d.revenue_growth_3y,
               d.pe_ttm, d.pb, d.market_cap
        FROM stock_basic b
        LEFT JOIN stock_daily d ON b.code = d.code
            AND d.date = (SELECT MAX(date) FROM stock_daily WHERE code = b.code)
        WHERE d.roe >= :min_roe
          AND d.revenue_growth_3y >= :min_revenue_growth
        ORDER BY d.roe DESC
        LIMIT :limit
    """)

    with engine.connect() as conn:
        df = pd.read_sql_query(
            query,
            conn,
            params={
                "min_roe": min_roe,
                "min_revenue_growth": min_revenue_growth,
                "limit": limit,
            },
        )

    if df.empty:
        return []

    results = df.astype(object).where(df.notna(), None).to_dict(orient="records")

    # Secondary API filter – only when stricter thresholds are requested
    need_api_filter = min_net_margin > 0 or max_debt_ratio < 100
    if need_api_filter:
        filtered: list[dict] = []
        for stock in results:
            code = str(stock["code"])
            try:
                summary = fetch_financial_summary(code)
                nm = summary.get("net_margin", 0) or 0
                dr = summary.get("debt_ratio", 0) or 0
                if nm >= min_net_margin and dr <= max_debt_ratio:
                    stock["net_margin"] = nm
                    stock["debt_ratio"] = dr
                    filtered.append(stock)
            except Exception:
                # Keep stock on transient API errors – avoid false negatives
                filtered.append(stock)
        return filtered

    return results
