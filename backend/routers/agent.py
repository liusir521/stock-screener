"""AI Agent chat endpoint."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api")


class ChatReq(BaseModel):
    message: str
    history: list[dict] | None = None


@router.post("/agent/chat")
async def agent_chat(req: ChatReq):
    from services.agent import run_agent_stream, _load_config

    config = _load_config()
    if not config.get("api_key"):
        raise HTTPException(status_code=400, detail="请先在设置中配置 AI API Key")

    if not req.message or len(req.message) > 2000:
        raise HTTPException(status_code=400, detail="message 不能为空且不能超过2000字")

    return StreamingResponse(
        run_agent_stream(req.message, req.history),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
