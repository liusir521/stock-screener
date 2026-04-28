"""One-shot script: pull data from Sina and populate SQLite tables."""
from database import SessionLocal, init_db
from models import StockBasic, StockDaily
from services.data_fetcher import fetch_all_sina_data


def seed():
    init_db()
    session = SessionLocal()

    df = fetch_all_sina_data()
    if df.empty:
        print("No data fetched. Check network connectivity to Sina.")
        return

    # Seed stock_basic
    basic_count = 0
    for _, row in df.iterrows():
        existing = session.get(StockBasic, row["code"])
        if existing:
            existing.name = row["name"]
            existing.market = row["market"]
            existing.is_st = row["is_st"]
        else:
            session.add(StockBasic(
                code=row["code"], name=row["name"], market=row["market"],
                industry=row["industry"], list_date=row["list_date"],
                is_st=row["is_st"],
            ))
        basic_count += 1
    session.commit()
    print(f"Seeded {basic_count} stocks in stock_basic")

    # Seed stock_daily
    daily_count = 0
    for _, row in df.iterrows():
        session.merge(StockDaily(
            code=row["code"], date=row["date"], close=row["close"],
            volume=row["volume"], turnover_rate=row["turnover_rate"],
            pe_ttm=row["pe_ttm"], pb=row["pb"], roe=row["roe"],
            revenue_growth_3y=row["revenue_growth_3y"],
            ma5=row["ma5"], ma20=row["ma20"], ma60=row["ma60"],
            macd_signal=row["macd_signal"], market_cap=row["market_cap"],
            dividend_yield=row["dividend_yield"],
        ))
        daily_count += 1
    session.commit()
    print(f"Seeded {daily_count} daily records")

    session.close()


if __name__ == "__main__":
    seed()
