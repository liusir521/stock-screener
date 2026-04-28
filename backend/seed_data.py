"""One-shot script: pull data from akshare and populate SQLite tables."""
from database import SessionLocal, init_db
from models import StockBasic, StockDaily
from services.data_fetcher import fetch_stock_list, fetch_daily_indicators


def seed():
    init_db()
    session = SessionLocal()

    # Seed stock_basic
    basic_df = fetch_stock_list()
    for _, row in basic_df.iterrows():
        existing = session.get(StockBasic, row["code"])
        if existing:
            existing.name = row["name"]
            existing.is_st = row["is_st"]
        else:
            session.add(StockBasic(
                code=row["code"], name=row["name"], market=row["market"],
                industry=row["industry"], list_date=row["list_date"],
                is_st=row["is_st"],
            ))
    session.commit()
    print(f"Seeded {len(basic_df)} stocks in stock_basic")

    # Seed stock_daily
    daily_df = fetch_daily_indicators()
    count = 0
    for _, row in daily_df.iterrows():
        code = str(row["code"])
        session.merge(StockDaily(
            code=code, date=row["date"], close=row["close"],
            volume=row["volume"], turnover_rate=row["turnover_rate"],
            pe_ttm=row["pe_ttm"], pb=row["pb"], roe=row["roe"],
            revenue_growth_3y=row["revenue_growth_3y"],
            ma5=row["ma5"], ma20=row["ma20"], ma60=row["ma60"],
            macd_signal=row["macd_signal"], market_cap=row["market_cap"],
            dividend_yield=row["dividend_yield"],
        ))
        count += 1
    session.commit()
    print(f"Seeded {count} daily records")

    session.close()


if __name__ == "__main__":
    seed()
