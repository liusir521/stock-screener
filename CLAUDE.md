# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend
```bash
cd backend
pip install -r ../requirements.txt
python seed_data.py           # Pull data from Sina finance API, populate SQLite (~60s)
uvicorn main:app --reload     # API at http://localhost:8000
```

No test runner or linter is configured for the backend.

### Frontend
```bash
cd frontend
npm install
npm run dev       # Dev server at http://localhost:5173 (proxies /api to :8000)
npm run build     # Type-check + production build
```

## Architecture

### Backend (FastAPI + SQLAlchemy + pandas)

- **`backend/main.py`** — App entry point. FastAPI with CORS (localhost:5173), lifespan hook calls `init_db()`, registers two routers.
- **`backend/database.py`** — SQLAlchemy engine setup. Connects to `../data/stocks.db` (SQLite) with `check_same_thread=False` for FastAPI async safety. `init_db()` imports models and calls `Base.metadata.create_all()`.
- **`backend/models.py`** — Two ORM models: `StockBasic` (code, name, market, industry, is_st) and `StockDaily` (code+date composite PK, close, volume, turnover_rate, pe_ttm, pb, roe, revenue_growth_3y, ma5/ma20/ma60, macd_signal, market_cap, dividend_yield). Tables are keyed by stock code (6-digit string).
- **`backend/services/screener.py`** — Core screening: `get_all_stocks_df()` JOINs basic+daily tables via raw SQL into a pandas DataFrame. `apply_filters()` applies all filter conditions in-memory on the DataFrame (market, PE/PB/ROE ranges, market cap, dividend yield, revenue growth, ST exclusion). `paginate()` slices and converts to list-of-dicts.
- **`backend/services/data_fetcher.py`** — Data fetching. `fetch_all_sina_data()` pulls bulk A-share PE/PB/market-cap/turnover from Sina finance API; `fetch_stock_list()` gets the stock list; `fetch_stock_history()` gets individual K-line data via akshare.
- **`backend/routers/stocks.py`** — `GET /api/stocks` (screening with query params), `GET /api/stocks/{code}` (detail with last 60 daily records), `GET /api/markets`.
- **`backend/routers/strategies.py`** — `GET /api/strategies` (list saved + built-in presets), `POST /api/strategies` (save/overwrite a named strategy). Persisted to `data/strategies.json`.
- **`backend/seed_data.py`** — One-shot seeding script: clears and repopulates both tables via Sina API.

Key design decisions:
- Screening bypasses SQLAlchemy ORM: raw SQL to DataFrame, then pandas filtering in Python memory. This means all stock records are loaded on every request — the dataset is ~5000 rows, so this is fine.
- SQLite file lives at `data/stocks.db`. The `data/` directory is git-ignored except for `.gitkeep`.

### Frontend (Vue 3 + TypeScript + Vite)

Single-page app, no Vue Router. Three-panel layout: sidebar (filters), main content (table), detail drawer.

- **`frontend/src/App.vue`** — Root component. Owns all state: `items`, `total`, `loading`, `selectedCode`, `currentFilters`. Passes handlers down to Sidebar and StockTable. Fetches via `api` module.
- **`frontend/src/api/index.ts`** — Typed HTTP client. `get<T>()` and `post<T>()` wrappers over fetch. All endpoints return typed responses. Vite dev server proxies `/api` to backend.
- **`frontend/src/types/index.ts`** — TypeScript interfaces: `StockItem`, `StockListResponse`, `MarketOption`, `Strategy`, `StockDetail`.
- **Components** (all in `src/components/`):
  - `Sidebar.vue` — Filter panel: keyword search (name/code), market selector, PE/PB/ROE/cap/dividend range inputs. Filters are isolated from keyword search. Emits `@search` with filter object.
  - `FilterGroup.vue` — Reusable filter row (label + min/max inputs).
  - `RangeSlider.vue` — Dual-thumb range slider for numeric filters.
  - `MarketFilter.vue` — Market tab selector (沪深/创业板/科创板/北交所).
  - `StockTable.vue` — Results table with sortable headers, row click emits. Delegates pagination to `Pagination.vue`.
  - `ResultHeader.vue` — Result count and CSV export.
  - `Pagination.vue` — Page navigation.
  - `StockDetail.vue` — Slide-out drawer showing stock basic info + daily K-line table. Hidden when `code` is null.
  - `StrategySave.vue` — Save/load dialog for named filter templates.

Vite proxies `/api` to `http://localhost:8000` in dev. No proxy in production build.
