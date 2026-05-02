"""Fund flow data fetching — 龙虎榜, 北向资金, 融资融券.

All functions handle network errors gracefully, returning empty/zero results
with a "note" key when an API fails or is unavailable.
"""
from datetime import datetime, date, timedelta
import akshare as ak


def _today_str() -> str:
    """Return today's date as YYYY-MM-DD string."""
    return datetime.now().strftime("%Y-%m-%d")


def _today_compact() -> str:
    """Return today's date as YYYYMMDD string."""
    return datetime.now().strftime("%Y%m%d")


# ---------------------------------------------------------------------------
# 1. Dragon & Tiger Board (龙虎榜)
# ---------------------------------------------------------------------------

def fetch_dragon_tiger(date_str: str | None = None) -> dict:
    """Fetch dragon & tiger board data from Eastmoney via akshare.

    Returns institutional seat trading details for the specified date:
    buy/sell/net amounts per stock.

    Args:
        date_str: Optional date in YYYY-MM-DD format. Defaults to today.

    Returns:
        {"date": "...", "stocks": [...], "count": N}
        Empty result on error.
    """
    if date_str is None:
        date_str = _today_str()

    # Convert to YYYYMMDD for the akshare API
    try:
        api_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y%m%d")
    except ValueError:
        api_date = date_str.replace("-", "")

    try:
        # Use Eastmoney LHB detail API which has buy/sell/net amounts
        df = ak.stock_lhb_detail_em(start_date=api_date, end_date=api_date)
        if df is None or df.empty:
            return {"date": date_str, "stocks": [], "count": 0}

        stocks = []
        for _, row in df.iterrows():
            try:
                # Amounts are in yuan (元), convert to 万元
                # col 7: 龙虎榜净买额, col 8: 龙虎榜买入额, col 9: 龙虎榜卖出额
                net_amt = float(row.iloc[7] or 0) / 10000   # 净买入额(万元)
                buy_amt = float(row.iloc[8] or 0) / 10000   # 买入总额(万元)
                sell_amt = float(row.iloc[9] or 0) / 10000  # 卖出总额(万元)
                stocks.append({
                    "code": str(row.iloc[1]),            # 代码
                    "name": str(row.iloc[2]),            # 名称
                    "change_pct": round(float(row.iloc[6] or 0), 2),  # 涨跌幅
                    "turnover_rate": round(float(row.iloc[14] or 0), 2),  # 换手率
                    "reason": str(row.iloc[16] or ""),   # 上榜原因
                    "buy_amount": round(buy_amt, 2),
                    "sell_amount": round(sell_amt, 2),
                    "net_amount": round(net_amt, 2),
                })
            except (ValueError, IndexError):
                continue

        return {"date": date_str, "stocks": stocks, "count": len(stocks)}

    except Exception as e:
        return {
            "date": date_str,
            "stocks": [],
            "count": 0,
            "note": f"fetch_dragon_tiger failed: {e}",
        }


# ---------------------------------------------------------------------------
# 2. Northbound Capital Flow (北向资金)
# ---------------------------------------------------------------------------

def fetch_northbound_flow(days: int = 20) -> dict:
    """Fetch northbound (沪港通/深港通) net capital flow — foreign A-share investment.

    Uses akshare's stock_hsgt_hist_em which provides daily net-buy amounts
    (in 亿元) for 沪股通, 深股通, and aggregated 北向资金.

    Args:
        days: Number of recent trading days to include in history.

    Returns:
        {"latest": {"date": "...", "net_flow": ...}, "history": [...],
         "cumulative_5d": ...} with net_flow in 亿元.
    """
    result: dict = {
        "latest": {"date": _today_str(), "net_flow": 0.0},
        "history": [],
        "cumulative_5d": 0.0,
    }

    try:
        # Fetch aggregated northbound (北向资金 = 沪股通 + 深股通)
        df = ak.stock_hsgt_hist_em(symbol="北向资金")
        if df is None or df.empty:
            result["note"] = "no data from stock_hsgt_hist_em"
            return result

        # Columns (by position):
        # 0: 日期, 1: 当日成交净买额(亿元), 2: 买入成交额, 3: 卖出成交额,
        # 4: 历史累计净买额, 5: 当日资金流入, 6: 余额, 7: 持股市值, ...
        history: list[dict] = []
        for _, row in df.iterrows():
            try:
                d = row.iloc[0]
                net = row.iloc[1]
                # Skip rows with NaN net flow (non-trading days, holidays,
                # or data not yet available from upstream source)
                if net != net:  # NaN check
                    continue
                if isinstance(d, date):
                    d = d.strftime("%Y-%m-%d")
                history.append({
                    "date": str(d),
                    "net_flow": round(float(net), 2),
                })
            except (ValueError, IndexError):
                continue

        # Supplement with fund_flow_summary for today/latest snapshot
        # (stock_hsgt_hist_em may lag by months due to upstream data limits)
        try:
            snap = ak.stock_hsgt_fund_flow_summary_em()
            if snap is not None and not snap.empty:
                # Columns: 交易日, 类型, 板块, 资金方向, 板块状态,
                # 成交净买额(亿元), 资金净流入(亿元), ...
                # Rows: 沪股通→沪股通, 沪股通→港股通(沪), 深股通→深股通, 深股通→港股通(深)
                # We only want northbound (沪股通/深股通), not southbound (港股通)
                daily_net = 0.0
                latest_snap_date = None
                for _, srow in snap.iterrows():
                    try:
                        board = str(srow.iloc[2])
                        if "港股通" in board:  # skip southbound
                            continue
                        snet = float(srow.iloc[5] or 0)
                        if snet != snet:  # NaN
                            continue
                        daily_net += snet
                        if latest_snap_date is None:
                            sd = srow.iloc[0]
                            if isinstance(sd, date):
                                latest_snap_date = sd.strftime("%Y-%m-%d")
                            else:
                                latest_snap_date = str(sd)
                    except (ValueError, IndexError):
                        continue
                if latest_snap_date and daily_net != 0:
                    history.append({
                        "date": latest_snap_date,
                        "net_flow": round(daily_net, 2),
                    })
        except Exception:
            pass  # supplement is optional

        if not history:
            result["note"] = "no valid trading-day data in history"
            return result

        result["history"] = history[-days:] if len(history) > days else history
        result["latest"] = result["history"][-1]

        # Cumulative 5-day net flow
        recent = result["history"][-5:]
        result["cumulative_5d"] = round(sum(h["net_flow"] for h in recent), 2)

        # Warn if data is stale (>30 days old)
        try:
            latest_dt = datetime.strptime(result["latest"]["date"], "%Y-%m-%d")
            if (datetime.now() - latest_dt).days > 30:
                result.setdefault("note", "northbound flow data may be stale — "
                                   f"latest available is {result['latest']['date']}")
        except (ValueError, KeyError):
            pass

    except Exception as e:
        result["latest"] = {"date": _today_str(), "net_flow": 0.0}
        result["history"] = []
        result["cumulative_5d"] = 0.0
        result["note"] = f"fetch_northbound_flow failed: {e}"

    return result


# ---------------------------------------------------------------------------
# 3. Margin Trading (融资融券)
# ---------------------------------------------------------------------------

def fetch_margin_stats() -> dict:
    """Fetch market-wide margin trading aggregate stats (融资融券).

    Combines SSE (上交所) and SZSE (深交所) margin data.
    SSE data is in 元, SZSE data is in 亿元 — both are normalised to 亿元.

    Returns:
        {"date": "...", "margin_balance": ..., "short_balance": ...,
         "total_balance": ..., "margin_buy": ...} all in 亿元.
    """
    result: dict = {
        "date": _today_str(),
        "margin_balance": 0.0,   # 融资余额(亿元)
        "short_balance": 0.0,    # 融券余额(亿元)
        "total_balance": 0.0,    # 两融余额(亿元)
        "margin_buy": 0.0,       # 融资买入额(亿元)
    }

    margin_balance = 0.0
    short_balance = 0.0
    total_balance = 0.0
    margin_buy = 0.0
    latest_date = ""

    # --- SSE (上交所) ---
    try:
        end = _today_compact()
        start = (datetime.strptime(end, "%Y%m%d") - timedelta(days=10)).strftime("%Y%m%d")
        df_sse = ak.stock_margin_sse(start_date=start, end_date=end)
        if df_sse is not None and not df_sse.empty:
            # Data is in descending order (latest first). Columns by position:
            # 0: 信用交易日期, 1: 融资余额(元), 2: 融资买入额(元),
            # 3: 融券余量(股), 4: 融券余量金额(元), 5: 融券卖出量(股),
            # 6: 融资融券余额(元)
            row = df_sse.iloc[0]  # latest row first
            sse_date = str(row.iloc[0])
            latest_date = sse_date
            margin_balance += float(row.iloc[1] or 0) / 1e8   # 元 -> 亿元
            margin_buy += float(row.iloc[2] or 0) / 1e8       # 元 -> 亿元
            short_balance += float(row.iloc[4] or 0) / 1e8    # 元 -> 亿元
            total_balance += float(row.iloc[6] or 0) / 1e8    # 元 -> 亿元
    except Exception as e:
        result["note_sse"] = f"SSE margin fetch failed: {e}"

    # --- SZSE (深交所) ---
    # SZSE may lag SSE by 1 day; try SSE date first, then 1-2 days earlier
    szse_dates = []
    if latest_date:
        dt = datetime.strptime(latest_date, "%Y%m%d")
        szse_dates = [(dt - timedelta(days=i)).strftime("%Y%m%d") for i in range(3)]

    for szse_date_str in szse_dates:
        try:
            df_szse = ak.stock_margin_szse(date=szse_date_str)
            if df_szse is not None and not df_szse.empty:
                # Columns (by position):
                # 0: 各项融余额, 1: 融资余额(亿元), 2: 融券余量,
                # 3: 融券余额(亿元), 4: 融券余量金额(亿元), 5: 融资融券余额(亿元)
                row = df_szse.iloc[0]
                szse_margin = float(row.iloc[1] or 0)       # 融资余额(亿元)
                szse_short = float(row.iloc[3] or 0)         # 融券余额(亿元)
                szse_total = float(row.iloc[5] or 0)         # 融资融券余额(亿元)
                margin_balance += szse_margin
                short_balance += szse_short
                total_balance += szse_total
                break  # success, stop retrying
        except Exception:
            continue
    else:
        if not any([margin_balance, short_balance, total_balance]):
            result["note_szse"] = "SZSE margin fetch failed for all attempted dates"

    result["margin_balance"] = round(margin_balance, 2)
    result["short_balance"] = round(short_balance, 2)
    result["total_balance"] = round(total_balance, 2)
    result["margin_buy"] = round(margin_buy, 2)

    # Use the date from SSE if available
    if latest_date:
        try:
            result["date"] = datetime.strptime(latest_date, "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            result["date"] = latest_date

    if margin_balance == 0 and short_balance == 0 and total_balance == 0:
        result.setdefault("note", "all margin sources returned empty or failed")

    return result


# ---------------------------------------------------------------------------
# 4. Northbound Holdings (single stock)
# ---------------------------------------------------------------------------

def fetch_northbound_holdings(code: str) -> dict:
    """Fetch northbound holdings for a single stock — foreign capital position.

    Searches the full northbound holdings list from both 沪股通 and 深股通
    for the given stock code.

    Args:
        code: 6-digit stock code string (e.g. "600519").

    Returns:
        {"code": "...", "name": "...", "hold_shares": ..., "hold_ratio": ...,
         "hold_value": ..., "date": "..."}
        hold_shares in 万股, hold_ratio in %, hold_value in 亿元, date is
        the reporting date.
    """
    result: dict = {
        "code": str(code),
        "name": "",
        "hold_shares": 0.0,     # 万股
        "hold_ratio": 0.0,      # 占流通股比例(%)
        "hold_value": 0.0,      # 亿元
        "date": _today_str(),
    }

    found = False
    for market in ["沪股通", "深股通"]:
        try:
            df = ak.stock_hsgt_hold_stock_em(market=market, indicator="今日排行")
            if df is None or df.empty:
                continue

            # Columns (by position):
            # 1: 代码, 2: 名称, 5: 当日持股-数量(万股), 6: 当日持股-市值(万元),
            # 7: 当日持股-占流通股比(%), 15: 日期
            for _, row in df.iterrows():
                try:
                    row_code = str(row.iloc[1]).strip()
                    if row_code != str(code):
                        continue
                    hold_shares_wan = float(row.iloc[5] or 0)       # 万股
                    hold_value_wan = float(row.iloc[6] or 0)        # 万元
                    hold_ratio = float(row.iloc[7] or 0)            # %
                    d = row.iloc[15]
                    if isinstance(d, date):
                        d = d.strftime("%Y-%m-%d")

                    result["name"] = str(row.iloc[2])
                    result["hold_shares"] = round(hold_shares_wan, 2)
                    result["hold_ratio"] = round(hold_ratio, 2)
                    result["hold_value"] = round(hold_value_wan / 10000, 2)  # 万元 -> 亿元
                    result["date"] = str(d)
                    found = True
                    break
                except (ValueError, IndexError):
                    continue
            if found:
                break
        except Exception:
            continue

    if not found:
        result["note"] = f"stock {code} not found in northbound holdings (data may lag)"

    # Warn if data is stale (>30 days old)
    if found:
        try:
            latest_dt = datetime.strptime(result["date"], "%Y-%m-%d")
            if (datetime.now() - latest_dt).days > 30:
                result["note"] = (f"holdings data may be stale — "
                                  f"latest available is {result['date']}")
        except (ValueError, KeyError):
            pass

    return result
