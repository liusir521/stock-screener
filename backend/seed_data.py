"""Data seeding: pull data from Sina and populate SQLite tables."""
import threading
import traceback

from database import SessionLocal, init_db
from models import StockBasic, StockDaily
from services.data_fetcher import fetch_all_sina_data

_refresh_lock = threading.Lock()
_refresh_status = {"running": False, "last_error": "", "last_time": "", "basic_count": 0, "daily_count": 0}


def get_refresh_status() -> dict:
    return dict(_refresh_status)


def seed() -> dict:
    """Run data refresh. Returns status dict. Thread-safe (only one refresh at a time)."""
    if _refresh_lock.locked():
        return {"status": "skipped", "reason": "刷新正在进行中"}
    with _refresh_lock:
        try:
            from datetime import datetime
            _refresh_status["running"] = True
            _refresh_status["last_error"] = ""
            init_db()
            session = SessionLocal()

            df = fetch_all_sina_data()
            if df.empty:
                _refresh_status["last_error"] = "无法连接到 Sina 财经，请检查网络"
                _refresh_status["running"] = False
                return {"status": "error", "reason": _refresh_status["last_error"]}

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
                    nmc=row["nmc"],
                    dividend_yield=row["dividend_yield"],
                ))
                daily_count += 1
            session.commit()
            session.close()

            _refresh_status["basic_count"] = basic_count
            _refresh_status["daily_count"] = daily_count
            _refresh_status["last_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _refresh_status["running"] = False
            return {"status": "ok", "basic_count": basic_count, "daily_count": daily_count}
        except Exception:
            _refresh_status["last_error"] = traceback.format_exc()
            _refresh_status["running"] = False
            return {"status": "error", "reason": _refresh_status["last_error"]}


if __name__ == "__main__":
    result = seed()
    print(result)
