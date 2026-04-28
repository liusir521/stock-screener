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
               d.market_cap, d.dividend_yield
        FROM stock_basic b
        LEFT JOIN stock_daily d ON b.code = d.code
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

    # Market filter
    if filters.get("market"):
        result = result[result["market"] == filters["market"]]

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
    if filters.get("revenue_growth_min") is not None:
        result = result[result["revenue_growth_3y"] >= filters["revenue_growth_min"]]

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
