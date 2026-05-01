"""Data seeding: pull data from Sina and populate SQLite tables."""
import threading
import traceback

from database import SessionLocal, init_db
from models import StockBasic, StockConcept, StockDaily
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

            # Seed stock_daily — clear today's stale records first
            today = df.iloc[0]["date"]
            session.query(StockDaily).filter(StockDaily.date == today, StockDaily.close == 0).delete()
            daily_count = 0
            skip_suspended = 0
            suspended_codes = []
            for _, row in df.iterrows():
                if float(row["close"]) <= 0:
                    skip_suspended += 1
                    suspended_codes.append(row["code"])
                    continue
                session.merge(StockDaily(
                    code=row["code"], date=row["date"], close=row["close"],
                    volume=row["volume"], turnover_rate=row["turnover_rate"],
                    pe_ttm=row["pe_ttm"], pb=row["pb"], roe=row["roe"],
                    revenue_growth_3y=row["revenue_growth_3y"],
                    ma5=row["ma5"], ma20=row["ma20"], ma60=row["ma60"],
                    macd_signal=row["macd_signal"], market_cap=row["market_cap"],
                    nmc=row["nmc"], float_shares=row["float_shares"],
                    dividend_yield=row["dividend_yield"],
                    change_pct=row["change_pct"], volume_ratio=row["volume_ratio"],
                ))
                daily_count += 1
            if skip_suspended:
                print(f"  Skipped {skip_suspended} suspended stocks (close=0)")
            session.commit()

            # Seed suspended stocks with snapshot data (close=0 but valid PE/PB/ROE/MC)
            if suspended_codes:
                print(f"  Fetching snapshot data for {len(suspended_codes)} suspended stocks...")
                from services.data_fetcher import fetch_single_snapshot
                seeded_suspended = 0
                for code in suspended_codes:
                    try:
                        snap = fetch_single_snapshot(code)
                        session.merge(StockDaily(
                            code=code, date=today,
                            close=0.0, volume=0.0, turnover_rate=0.0,
                            pe_ttm=float(snap.get("pe_ttm", 0)) if snap.get("pe_ttm") else 0.0,
                            pb=float(snap.get("pb", 0)) if snap.get("pb") else 0.0,
                            roe=float(snap.get("roe", 0)) if snap.get("roe") else 0.0,
                            revenue_growth_3y=0.0,
                            ma5=0.0, ma20=0.0, ma60=0.0, macd_signal=0.0,
                            market_cap=float(snap.get("market_cap", 0)) if snap.get("market_cap") else 0.0,
                            nmc=0.0, float_shares=0.0,
                            dividend_yield=0.0,
                            change_pct=0.0, volume_ratio=0.0,
                        ))
                        seeded_suspended += 1
                    except Exception:
                        pass
                session.commit()
                print(f"  Suspended stocks seeded with snapshot data: {seeded_suspended}")

            # Batch-fetch industry info from Sina corporate pages
            codes = list(df["code"].tolist())
            print(f"  Fetching industry info for {len(codes)} stocks...")
            from services.data_fetcher import fetch_corp_info
            from concurrent.futures import ThreadPoolExecutor, as_completed
            updated_ind = 0
            with ThreadPoolExecutor(max_workers=20) as pool:
                fut = {pool.submit(fetch_corp_info, c): c for c in codes}
                for i, f in enumerate(as_completed(fut)):
                    c = fut[f]
                    try:
                        info = f.result()
                        ind = info.get("industry", "")
                        if ind:
                            session.query(StockBasic).filter(StockBasic.code == c).update({"industry": ind})
                            updated_ind += 1
                    except Exception:
                        pass
                    if (i + 1) % 500 == 0:
                        session.commit()
                        print(f"    industry: {i + 1}/{len(codes)}")
            session.commit()
            print(f"  Industry updated: {updated_ind} stocks")

            # Compute volume_ratio via K-line data (parallel fetches)
            print(f"  Computing volume_ratio for {len(codes)} stocks...")
            print(f"  Computing volume_ratio for {len(codes)} stocks...")
            from services.data_fetcher import batch_compute_volume_ratios
            vr_map = batch_compute_volume_ratios(codes)
            updated_vr = 0
            for code, vr in vr_map.items():
                if vr > 0:
                    session.query(StockDaily).filter(
                        StockDaily.code == code, StockDaily.date == df.iloc[0]["date"]
                    ).update({"volume_ratio": vr})
                    updated_vr += 1
            session.commit()
            print(f"  volume_ratio updated: {updated_vr} stocks")

            # Fetch financial growth data (revenue_growth, ROE) from Sina finance report API
            print(f"  Fetching financial growth data for {len(codes)} stocks...")
            from services.data_fetcher import batch_fetch_financial_growth
            fin_data = batch_fetch_financial_growth(codes)
            updated_fin = 0
            today = df.iloc[0]["date"]
            for code, (rev_growth, roe) in fin_data.items():
                updates = {}
                if rev_growth != 0:
                    updates["revenue_growth_3y"] = rev_growth
                if roe > 0:
                    updates["roe"] = roe
                if updates:
                    session.query(StockDaily).filter(
                        StockDaily.code == code, StockDaily.date == today
                    ).update(updates)
                    updated_fin += 1
            session.commit()
            print(f"  Financial growth updated: {updated_fin} stocks")

            # Compute dividend yields from dividend history
            print(f"  Computing dividend yields for {len(codes)} stocks...")
            from services.data_fetcher import compute_dividend_yield
            from concurrent.futures import ThreadPoolExecutor, as_completed
            updated_div = 0
            with ThreadPoolExecutor(max_workers=20) as pool:
                # Get current prices from the DataFrame
                price_map = dict(zip(df["code"], df["close"]))
                def _div_for(code):
                    return code, compute_dividend_yield(code, float(price_map.get(code, 0)))
                fut = {pool.submit(_div_for, c): c for c in codes}
                for i, f in enumerate(as_completed(fut)):
                    try:
                        code, dy = f.result()
                        if dy > 0:
                            session.query(StockDaily).filter(
                                StockDaily.code == code, StockDaily.date == today
                            ).update({"dividend_yield": dy})
                            updated_div += 1
                    except Exception:
                        pass
                    if (i + 1) % 500 == 0:
                        session.commit()
                        print(f"    dividend: {i + 1}/{len(codes)}")
            session.commit()
            print(f"  Dividend yield updated: {updated_div} stocks")

            # Seed concept board data
            print("  Fetching concept board data...")
            from services.data_fetcher import batch_fetch_concepts
            try:
                concepts = batch_fetch_concepts(top_n=80)
                if concepts:
                    # Clear old concept data
                    session.query(StockConcept).delete()
                    for item in concepts:
                        for cn in item["concept_name"]:
                            session.merge(StockConcept(code=item["code"], concept_name=cn))
                    session.commit()
                    print(f"  Concepts seeded: {len(concepts)} stock-concept pairs")
                else:
                    print("  No concept data fetched")
            except Exception as e:
                print(f"  Concept seeding error (non-fatal): {e}")

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
