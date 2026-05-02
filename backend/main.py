"""Stock Screener API entry point."""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from database import init_db


class ConnectionManager:
    """Manage WebSocket connections and broadcast messages to all active clients."""

    def __init__(self):
        self.active: list[WebSocket] = []
        self.loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict):
        for ws in self.active[:]:
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(ws)


manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    manager.loop = asyncio.get_running_loop()
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


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        # Send initial status on connect
        from seed_data import get_refresh_status
        await ws.send_json({"type": "status", "data": get_refresh_status()})
        while True:
            # Keep connection alive, wait for any message
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)


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
