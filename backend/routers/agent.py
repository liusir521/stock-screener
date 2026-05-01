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
    import traceback, json
    from services.agent import run_agent_stream, _load_config

    config = _load_config()
    if not config.get("api_key"):
        raise HTTPException(status_code=400, detail="请先在设置中配置 AI API Key")

    if not req.message or len(req.message) > 8000:
        raise HTTPException(status_code=400, detail="message 不能为空且不能超过2000字")

    print(f"[agent] msg={req.message[:60]} history={len(req.history) if req.history else 0}", flush=True)

    def safe_stream():
        try:
            yield from run_agent_stream(req.message, req.history)
        except Exception as e:
            traceback.print_exc()
            yield f"event: error\ndata: {json.dumps(str(e), ensure_ascii=False)}\n\n"

    return StreamingResponse(
        safe_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
