"""Stock screening and detail endpoints."""
from fastapi import APIRouter, Query

from services.screener import get_all_stocks_df, apply_filters, paginate

router = APIRouter(prefix="/api")


@router.get("/stocks")
def list_stocks(
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
    exclude_st: bool = Query(True),
    sort_by: str = Query("code"),
    order: str = Query("asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    filters = {k: v for k, v in {
        "market": market, "pe_min": pe_min, "pe_max": pe_max,
        "pb_min": pb_min, "pb_max": pb_max, "roe_min": roe_min,
        "market_cap_min": market_cap_min, "market_cap_max": market_cap_max,
        "dividend_yield_min": dividend_yield_min,
        "revenue_growth_min": revenue_growth_min,
        "exclude_st": exclude_st, "sort_by": sort_by, "order": order,
    }.items() if v is not None}

    df = get_all_stocks_df()
    filtered = apply_filters(df, filters)
    items, total = paginate(filtered, page, page_size)

    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/stocks/{code}")
def stock_detail(code: str):
    from database import engine
    import pandas as pd

    query = "SELECT * FROM stock_daily WHERE code = :code ORDER BY date DESC LIMIT 60"
    with engine.connect() as conn:
        df = pd.read_sql_query(query, conn, params={"code": code})

    basic_query = "SELECT * FROM stock_basic WHERE code = :code"
    with engine.connect() as conn:
        basic = pd.read_sql_query(basic_query, conn, params={"code": code})

    return {
        "basic": basic.to_dict(orient="records")[0] if len(basic) > 0 else None,
        "daily": df.where(df.notna(), None).to_dict(orient="records"),
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
