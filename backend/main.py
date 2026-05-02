"""Stock Screener API entry point."""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Auto-fetch data on first startup (when DB is empty)
    from database import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM stock_basic")).scalar()
    if count == 0:
        from seed_data import seed
        asyncio.create_task(asyncio.to_thread(seed))
    yield


app = FastAPI(title="Stock Screener", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers.stocks import router as stocks_router
from routers.strategies import router as strategies_router
from routers.ai_config import router as ai_config_router
from routers.agent import router as agent_router
from routers.alerts import router as alerts_router

app.include_router(stocks_router)
app.include_router(strategies_router)
app.include_router(ai_config_router)
app.include_router(agent_router)
app.include_router(alerts_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
