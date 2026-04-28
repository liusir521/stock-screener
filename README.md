# Stock Screener

Personal A-share stock screening tool. Filter stocks by fundamental and technical indicators.

## Quick Start

### Backend
```bash
cd backend
pip install -r requirements.txt
python seed_data.py        # Fetch data from akshare (~60s first run)
uvicorn main:app --reload  # API at http://localhost:8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev                # UI at http://localhost:5173
```

## Tech Stack
- Backend: Python 3.11+, FastAPI, SQLAlchemy, pandas, akshare
- Frontend: Vue 3 (Composition API), TypeScript, Vite
- Database: SQLite

## Features
- Multi-condition stock screening (PE, PB, ROE, market cap, dividend yield, turnover)
- Result table with sorting and pagination
- Stock detail drawer
- Strategy template save/load
- CSV export
