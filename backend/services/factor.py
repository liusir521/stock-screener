"""Multi-factor scoring model for A-share stocks.

Four dimensions: valuation (25%), growth (30%), quality (25%), momentum (20%).
"""
import pandas as pd
import numpy as np
from database import engine


def _get_latest_data() -> pd.DataFrame:
    """Get latest daily data joined with stock_basic for all stocks."""
    query = """
        SELECT b.code, b.name, b.market, b.industry, b.is_st,
               d.close, d.pe_ttm, d.pb, d.roe, d.revenue_growth_3y,
               d.ma5, d.ma20, d.change_pct, d.dividend_yield, d.market_cap
        FROM stock_basic b
        LEFT JOIN stock_daily d ON b.code = d.code
            AND d.date = (SELECT MAX(date) FROM stock_daily WHERE code = b.code)
    """
    with engine.connect() as conn:
        df = pd.read_sql_query(query, conn)
    return df


def _score_valuation(df: pd.DataFrame) -> pd.Series:
    """Score valuation (25% weight): PE and PB percentiles among all stocks.

    Lower PE/PB = cheaper = higher score.  Uses rank-based scoring:
    bottom 10% PE = score 90, bottom 50% = score 50.
    Only positive PE/PB values are used for percentile computation.
    """
    scores = pd.Series(np.nan, index=df.index)
    valid_mask = (
        df["pe_ttm"].notna() & df["pb"].notna()
        & df["pe_ttm"].gt(0) & df["pb"].gt(0)
    )
    valid = df[valid_mask]
    if len(valid) == 0:
        return scores
    pe_pct = valid["pe_ttm"].rank(pct=True)
    pb_pct = valid["pb"].rank(pct=True)
    pe_score = (1 - pe_pct) * 100
    pb_score = (1 - pb_pct) * 100
    scores[valid_mask] = (pe_score + pb_score) / 2
    return scores


def _score_growth(df: pd.DataFrame) -> pd.Series:
    """Score growth (30% weight): ROE and revenue_growth_3y.

    ROE: >20%=100, 10-20%=50-100, 5-10%=10-50, 0-5%=0-10, <0%=0.
    Revenue growth: >30%=100, 10-30%=60-100, 0-10%=30-60, <0%=0.
    """
    roe = df["roe"].fillna(0).values
    rev = df["revenue_growth_3y"].fillna(0).values
    n = len(df)

    # ---- ROE sub-score ----
    roe_score = np.zeros(n)
    roe_score = np.where(roe >= 20, 100, roe_score)
    mask = (roe >= 10) & (roe < 20)
    roe_score = np.where(mask, 50 + (roe - 10) / 10 * 50, roe_score)
    mask = (roe >= 5) & (roe < 10)
    roe_score = np.where(mask, 10 + (roe - 5) / 5 * 40, roe_score)
    mask = (roe > 0) & (roe < 5)
    roe_score = np.where(mask, roe / 5 * 10, roe_score)

    # ---- Revenue-growth sub-score ----
    rev_score = np.zeros(n)
    rev_score = np.where(rev >= 30, 100, rev_score)
    mask = (rev >= 10) & (rev < 30)
    rev_score = np.where(mask, 60 + (rev - 10) / 20 * 40, rev_score)
    mask = (rev > 0) & (rev < 10)
    rev_score = np.where(mask, 30 + rev / 10 * 30, rev_score)

    result = pd.Series((roe_score + rev_score) / 2, index=df.index)
    # If ROE was NaN the stock has no fundamental data – mark as NaN
    result[df["roe"].isna()] = np.nan
    return result


def _score_quality(df: pd.DataFrame) -> pd.Series:
    """Score quality (25% weight): ROE stability proxy + dividend yield bonus.

    ROE >15 = high-quality base (80), ROE 10-15 = medium (50), ROE 0-10 = low (20).
    Dividend yield bonus: >2% = +20, >1% = +10.
    """
    roe = df["roe"].fillna(0).values
    dy = df["dividend_yield"].fillna(0).values
    n = len(df)

    quality_base = np.zeros(n)
    quality_base = np.where(roe >= 15, 80, quality_base)
    quality_base = np.where((roe >= 10) & (roe < 15), 50, quality_base)
    quality_base = np.where((roe > 0) & (roe < 10), 20, quality_base)

    dy_bonus = np.zeros(n)
    dy_bonus = np.where(dy > 2, 20, dy_bonus)
    dy_bonus = np.where((dy > 1) & (dy <= 2), 10, dy_bonus)

    result = pd.Series(np.clip(quality_base + dy_bonus, 0, 100), index=df.index)
    result[df["roe"].isna()] = np.nan
    return result


def _score_momentum(df: pd.DataFrame) -> pd.Series:
    """Score momentum (20% weight): change_pct and MA20 alignment.

    change_pct: >=5%=100, 2-5%=80, 0-2%=50, -2-0%=30, <-2%=10.
    MA20 alignment: close > ma20 = +20 pts (bullish trend).
    """
    chg = df["change_pct"].fillna(0).values
    close = df["close"].fillna(0).values
    ma20 = df["ma20"].fillna(0).values
    n = len(df)

    chg_score = np.zeros(n)
    chg_score = np.where(chg >= 5, 100, chg_score)
    chg_score = np.where((chg >= 2) & (chg < 5), 80, chg_score)
    chg_score = np.where((chg >= 0) & (chg < 2), 50, chg_score)
    chg_score = np.where((chg >= -2) & (chg < 0), 30, chg_score)
    chg_score = np.where(chg < -2, 10, chg_score)

    ma_bonus = np.where((close > ma20) & (ma20 > 0), 20, 0)

    return pd.Series(np.clip(chg_score + ma_bonus, 0, 100), index=df.index)


WEIGHTS = {"valuation": 0.25, "growth": 0.30, "quality": 0.25, "momentum": 0.20}


def _build_result(row) -> dict:
    """Build the result dict for a single stock row with pre-computed scores."""
    close_val = float(row["close"]) if pd.notna(row["close"]) else 0.0
    ma20_val = float(row["ma20"]) if pd.notna(row["ma20"]) else 0.0
    pe_val = row["pe_ttm"]
    pb_val = row["pb"]
    roe_val = row["roe"]
    rev_val = row["revenue_growth_3y"]
    dy_val = row["dividend_yield"]
    chg_val = row["change_pct"]

    def _r(v):
        """Round a float, return None when NaN."""
        return round(float(v), 2) if pd.notna(v) else None

    return {
        "code": str(row["code"]),
        "name": str(row["name"]),
        "composite": round(float(row["composite"]), 1),
        "factors": {
            "valuation": {
                "score": round(float(row["val_score"]), 1),
                "pe_ttm": _r(pe_val),
                "pb": _r(pb_val),
            },
            "growth": {
                "score": round(float(row["gro_score"]), 1),
                "roe": _r(roe_val),
                "revenue_growth_3y": _r(rev_val),
            },
            "quality": {
                "score": round(float(row["qua_score"]), 1),
                "roe": _r(roe_val),
                "dividend_yield": _r(dy_val),
            },
            "momentum": {
                "score": round(float(row["mom_score"]), 1),
                "change_pct": _r(chg_val),
                "ma20_aligned": bool(close_val > ma20_val > 0),
            },
        },
    }


def score_stock(code: str) -> dict:
    """Score a single stock across 4 dimensions (0-100 each), returns composite weighted score.

    Factors:
    - Valuation (weight 25%): PE/PB percentile among all stocks (lower = better)
    - Growth (weight 30%): ROE and revenue_growth_3y (higher = better)
    - Quality (weight 25%): ROE stability proxy + dividend yield bonus
    - Momentum (weight 20%): change_pct + MA20 alignment

    Raises ValueError if the stock is not found or has missing PE/PB/ROE.
    """
    df = _get_latest_data()

    stock = df[df["code"] == str(code)]
    if stock.empty:
        raise ValueError(f"Stock {code} not found")

    row = stock.iloc[0]
    pe = row["pe_ttm"]
    pb = row["pb"]
    roe = row["roe"]

    if pd.isna(pe) or pd.isna(pb) or pd.isna(roe) or pe <= 0 or pb <= 0:
        raise ValueError(f"Stock {code} missing essential data (PE/PB/ROE)")

    # Compute all factor scores over the full dataset for percentile accuracy
    df["val_score"] = _score_valuation(df)
    df["gro_score"] = _score_growth(df)
    df["qua_score"] = _score_quality(df)
    df["mom_score"] = _score_momentum(df)

    idx = stock.index[0]
    df.at[idx, "close"] = row["close"]
    df.at[idx, "ma20"] = row["ma20"]
    df.at[idx, "pe_ttm"] = row["pe_ttm"]
    df.at[idx, "pb"] = row["pb"]
    df.at[idx, "roe"] = row["roe"]
    df.at[idx, "revenue_growth_3y"] = row["revenue_growth_3y"]
    df.at[idx, "dividend_yield"] = row["dividend_yield"]
    df.at[idx, "change_pct"] = row["change_pct"]

    ws = WEIGHTS
    df.at[idx, "composite"] = (
        df.at[idx, "val_score"] * ws["valuation"]
        + df.at[idx, "gro_score"] * ws["growth"]
        + df.at[idx, "qua_score"] * ws["quality"]
        + df.at[idx, "mom_score"] * ws["momentum"]
    )

    return _build_result(df.loc[idx])


def rank_stocks(
    market: str | None = None,
    exclude_st: bool = True,
    industry: str | None = None,
    min_score: float = 0,
    top_n: int = 50,
) -> list[dict]:
    """Score all stocks (optionally filtered), return top N sorted by composite descending.

    Args:
        market: Filter by market (comma-separated, e.g. "沪市主板,深市主板").
        exclude_st: Exclude ST stocks (default True).
        industry: Fuzzy match on industry name.
        min_score: Minimum composite score threshold.
        top_n: Return at most this many results.
    """
    df = _get_latest_data()

    # --- Filters ---
    if market:
        markets = [m.strip() for m in market.split(",") if m.strip()]
        if markets:
            df = df[df["market"].isin(markets)]

    if exclude_st:
        df = df[df["is_st"] == 0]

    if industry:
        df = df[df["industry"].astype(str).str.contains(industry, case=False, na=False)]

    # --- Score all rows ---
    df["val_score"] = _score_valuation(df)
    df["gro_score"] = _score_growth(df)
    df["qua_score"] = _score_quality(df)
    df["mom_score"] = _score_momentum(df)

    # Drop stocks that couldn't be scored (missing PE/PB/ROE)
    df = df.dropna(subset=["val_score", "gro_score", "qua_score", "mom_score"])

    ws = WEIGHTS
    df["composite"] = (
        df["val_score"] * ws["valuation"]
        + df["gro_score"] * ws["growth"]
        + df["qua_score"] * ws["quality"]
        + df["mom_score"] * ws["momentum"]
    )

    if min_score:
        df = df[df["composite"] >= min_score]

    df = df.sort_values("composite", ascending=False).head(top_n)

    return [_build_result(row) for _, row in df.iterrows()]
