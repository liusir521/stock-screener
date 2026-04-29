"""Stock screening logic using pandas on SQLite-backed DataFrames."""
import pandas as pd
from database import engine


def get_all_stocks_df() -> pd.DataFrame:
    """Join stock_basic + stock_daily into a single DataFrame for filtering."""
    query = """
        SELECT b.code, b.name, b.market, b.industry, b.is_st,
               d.close, d.volume, d.turnover_rate,
               d.pe_ttm, d.pb, d.roe, d.revenue_growth_3y,
               d.ma5, d.ma20, d.ma60, d.macd_signal,
               d.market_cap, d.dividend_yield, d.change_pct, d.volume_ratio
        FROM stock_basic b
        LEFT JOIN stock_daily d ON b.code = d.code
            AND d.date = (SELECT MAX(date) FROM stock_daily WHERE code = b.code)
    """
    with engine.connect() as conn:
        df = pd.read_sql_query(query, conn)
    return df


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Apply screening conditions. Returns filtered DataFrame."""
    result = df.copy()

    # Keyword search (name or code)
    if filters.get("keyword"):
        kw = filters["keyword"]
        result = result[result["code"].str.contains(kw, case=False, na=False) |
                        result["name"].str.contains(kw, case=False, na=False)]

    # Industry filter (from sector ranking click)
    if filters.get("industry"):
        ind_val = filters["industry"]
        ind_name = filters.get("industry_name", "")
        search_name = ind_name or ind_val

        # Step 1: if it's a BKxxxx东方财富 board code, try constituent API
        codes: set[str] = set()
        if ind_val.startswith("BK"):
            from services.data_fetcher import fetch_industry_stocks
            codes = set(fetch_industry_stocks(ind_val))

        if codes:
            result = result[result["code"].isin(codes)]
        else:
            # Step 2: fall back to keyword search
            result = result[result["code"].str.contains(search_name, case=False, na=False) |
                            result["name"].str.contains(search_name, case=False, na=False)]

    # Market filter (supports comma-separated multi-select)
    if filters.get("market"):
        markets = [m.strip() for m in filters["market"].split(",") if m.strip()]
        if markets:
            result = result[result["market"].isin(markets)]

    # Exclude ST
    if filters.get("exclude_st"):
        result = result[result["is_st"] == 0]

    # PE range
    pe_min = filters.get("pe_min")
    pe_max = filters.get("pe_max")
    if pe_min is not None:
        result = result[result["pe_ttm"] >= pe_min]
    if pe_max is not None:
        result = result[result["pe_ttm"] <= pe_max]

    # PB
    pb_min = filters.get("pb_min")
    pb_max = filters.get("pb_max")
    if pb_min is not None:
        result = result[result["pb"] >= pb_min]
    if pb_max is not None:
        result = result[result["pb"] <= pb_max]

    # ROE
    if filters.get("roe_min") is not None:
        result = result[result["roe"] >= filters["roe_min"]]

    # Market cap range (in 100M CNY)
    cap_min = filters.get("market_cap_min")
    cap_max = filters.get("market_cap_max")
    if cap_min is not None:
        result = result[result["market_cap"] >= cap_min]
    if cap_max is not None:
        result = result[result["market_cap"] <= cap_max]

    # Dividend yield
    if filters.get("dividend_yield_min") is not None:
        result = result[result["dividend_yield"] >= filters["dividend_yield_min"]]

    # Revenue growth
    rev_min = filters.get("revenue_growth_min")
    rev_max = filters.get("revenue_growth_max")
    if rev_min is not None:
        result = result[result["revenue_growth_3y"] >= rev_min]
    if rev_max is not None:
        result = result[result["revenue_growth_3y"] <= rev_max]

    # Price change
    chg_min = filters.get("change_pct_min")
    chg_max = filters.get("change_pct_max")
    if chg_min is not None:
        result = result[result["change_pct"] >= chg_min]
    if chg_max is not None:
        result = result[result["change_pct"] <= chg_max]

    # Volume ratio
    vol_min = filters.get("volume_ratio_min")
    if vol_min is not None:
        result = result[result["volume_ratio"] >= vol_min]

    # Concept filter (comma-separated concept names)
    if filters.get("concept"):
        selected = [c.strip() for c in filters["concept"].split(",") if c.strip()]
        if selected:
            from database import engine
            import pandas as _pd
            with engine.connect() as conn:
                cdf = _pd.read_sql_query(
                    "SELECT DISTINCT code FROM stock_concept WHERE concept_name IN ({})".format(
                        ",".join("?" for _ in selected)),
                    conn, params=tuple(selected))
            matching_codes = set(cdf["code"].tolist())
            result = result[result["code"].isin(matching_codes)]

    # Sort
    sort_by = filters.get("sort_by", "code")
    order = filters.get("order", "asc")
    if sort_by in result.columns:
        result = result.sort_values(sort_by, ascending=(order == "asc"))

    return result


def paginate(df: pd.DataFrame, page: int, page_size: int) -> tuple[list[dict], int]:
    """Slice DataFrame for pagination. Returns (items_list, total_count)."""
    total = len(df)
    start = (page - 1) * page_size
    end = start + page_size
    page_df = df.iloc[start:end]
    items = page_df.where(page_df.notna(), None).to_dict(orient="records")
    return items, total
