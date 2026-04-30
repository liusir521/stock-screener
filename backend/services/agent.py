"""AI Agent: LLM function calling + stock analysis tools."""
import json
from pathlib import Path
from typing import Generator

import requests

from services.indicator import sma, ema, macd, rsi, kdj, bollinger, latest_value

AI_CONFIG_FILE = Path(__file__).parent.parent.parent / "data" / "ai_config.json"

SYSTEM_PROMPT = """你是一位 A 股技术分析专家，能用自然语言帮用户选股和分析股票。

你可以使用以下工具获取数据：
- analyze_stock: 对指定股票做多周期（日/周/月K）技术分析，返回 MA、MACD、RSI、KDJ、布林带等指标
- search_stocks: 按条件筛选股票（支持 PE、PB、ROE、市值、股息率、营收增长、涨跌幅、量比、换手率、行业、市场等）
- compare_stocks: 并排对比多只股票的技术面
- get_market_breadth: 获取今日市场全景（涨停板/跌停板统计、板块排名）

分析原则：
1. 引用具体数值，不要泛泛而谈。如"MA5=1520.35 位于 MA20=1498.72 上方，短期多头排列"
2. 结合多周期判断：日K看短期趋势，周K看中期方向，月K看长期格局
3. 当指标信号矛盾时，明确指出并给出权衡
4. 没有数据支撑的判断，说"数据不足，无法判断"，不要猜测
5. 用 Markdown 格式输出：表格、列表、加粗关键结论"""


def _load_config() -> dict:
    if not AI_CONFIG_FILE.exists():
        return {}
    try:
        with open(AI_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _api_params() -> tuple[str, str, str]:
    config = _load_config()
    api_url = config.get("api_url", "https://api.openai.com/v1").rstrip("/")
    model = config.get("model", "gpt-4o")
    api_key = config.get("api_key", "")
    if not api_key:
        raise RuntimeError("请先在设置中配置 AI API Key")
    return api_url, model, api_key


def _stream_llm(messages: list[dict], tools: list[dict] | None = None) -> Generator[dict, None, None]:
    """Stream LLM response tokens. Yields dicts: {type: 'token'|'tool_delta'|'finish', ...}."""
    api_url, model, api_key = _api_params()

    body: dict = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 2048,
        "stream": True,
        "stream_options": {"include_usage": True},
        "thinking": {"type": "disabled"},
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"

    resp = requests.post(
        f"{api_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=body,
        timeout=300,
        stream=True,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"LLM API 错误 ({resp.status_code}): {resp.text[:500]}")

    # Parse SSE stream
    tool_call_buf: dict[int, dict] = {}  # index -> {id, name, arguments}
    for line in resp.iter_lines(decode_unicode=True):
        if not line or line.strip() == "data: [DONE]":
            continue
        if not line.startswith("data: "):
            continue
        try:
            data = json.loads(line[6:])
        except json.JSONDecodeError:
            continue

        choices = data.get("choices", [])
        if not choices:
            continue

        delta = choices[0].get("delta", {})
        finish_reason = choices[0].get("finish_reason", "")

        # Text content token
        content = delta.get("content")
        if content:
            yield {"type": "token", "content": content}

        # Tool call delta
        tc_deltas = delta.get("tool_calls", [])
        for tc in tc_deltas:
            idx = tc.get("index", 0)
            if idx not in tool_call_buf:
                tool_call_buf[idx] = {"id": "", "name": "", "arguments": ""}
            buf = tool_call_buf[idx]
            if tc.get("id"):
                buf["id"] = tc["id"]
            func = tc.get("function", {})
            if func.get("name"):
                buf["name"] = func["name"]
            if func.get("arguments"):
                buf["arguments"] += func["arguments"]
            yield {"type": "tool_delta", "index": idx, "name": buf["name"], "id": buf["id"]}

        # Finish reason
        if finish_reason == "tool_calls" and tool_call_buf:
            yield {
                "type": "tool_calls",
                "calls": [
                    {"id": b["id"], "name": b["name"], "arguments": b["arguments"]}
                    for b in tool_call_buf.values()
                ],
            }
        elif finish_reason == "stop":
            yield {"type": "finish"}


# ─── Tool definitions ───

TOOL_ANALYZE_STOCK = {
    "type": "function",
    "function": {
        "name": "analyze_stock",
        "description": "对单只股票做多周期技术分析。返回日/周/月K的技术指标（MA5/MA20/MA60、MACD、RSI、KDJ、布林带），以及基本面和分时数据。",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "6位股票代码，如 600519"},
                "periods": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["daily", "weekly", "monthly"]},
                    "description": "分析周期，默认 ['daily', 'weekly', 'monthly']",
                },
            },
            "required": ["code"],
        },
    },
}

TOOL_SEARCH_STOCKS = {
    "type": "function",
    "function": {
        "name": "search_stocks",
        "description": "按条件筛选A股。支持 PE/PB/ROE/市值/股息率/营收增长/涨跌幅/量比/换手率/行业/市场/排除ST等条件。返回前20只匹配股票。",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "股票名称或代码关键词"},
                "industry": {"type": "string", "description": "行业名称"},
                "market": {"type": "string", "description": "市场: sh_sz(沪深A股), chinext(创业板), star(科创板), bse(北交所)"},
                "pe_min": {"type": "number"}, "pe_max": {"type": "number"},
                "pb_min": {"type": "number"}, "pb_max": {"type": "number"},
                "roe_min": {"type": "number"},
                "market_cap_min": {"type": "number"}, "market_cap_max": {"type": "number"},
                "dividend_yield_min": {"type": "number"},
                "revenue_growth_min": {"type": "number"}, "revenue_growth_max": {"type": "number"},
                "change_pct_min": {"type": "number"}, "change_pct_max": {"type": "number"},
                "volume_ratio_min": {"type": "number"},
                "turnover_rate_min": {"type": "number"},
                "exclude_st": {"type": "boolean", "description": "是否排除ST股票，默认true"},
                "sort_by": {"type": "string"}, "order": {"type": "string", "enum": ["asc", "desc"]},
            },
        },
    },
}

TOOL_COMPARE_STOCKS = {
    "type": "function",
    "function": {
        "name": "compare_stocks",
        "description": "并排对比多只股票的技术面和基本面。返回每只股票的关键指标表格数据。",
        "parameters": {
            "type": "object",
            "properties": {
                "codes": {
                    "type": "array", "items": {"type": "string"},
                    "description": "股票代码列表，如 ['600519', '000858', '000568']",
                },
            },
            "required": ["codes"],
        },
    },
}

TOOL_MARKET_BREADTH = {
    "type": "function",
    "function": {
        "name": "get_market_breadth",
        "description": "获取今日市场全景：涨停板/跌停板统计（数量、连板数、封单量）、行业板块涨跌幅排名（前10和后10）。",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

ALL_TOOLS = [TOOL_ANALYZE_STOCK, TOOL_SEARCH_STOCKS, TOOL_COMPARE_STOCKS, TOOL_MARKET_BREADTH]

# ─── Tool implementations ───


def _exec_analyze_stock(args: dict) -> dict:
    code = args["code"]
    periods = args.get("periods", ["daily", "weekly", "monthly"])
    from database import engine
    import pandas as pd
    from services.data_fetcher import fetch_kline_sina, fetch_intraday_sina, fetch_corp_info

    # ── Load basic info + latest daily from DB ──
    basic = {}
    latest: dict = {}
    try:
        with engine.connect() as conn:
            row = conn.execute(
                __import__("sqlalchemy").text("SELECT * FROM stock_basic WHERE code = :code"),
                {"code": code},
            ).fetchone()
        if row:
            basic = dict(row._mapping)
        corp = fetch_corp_info(code)
        if corp.get("industry"):
            basic["industry"] = corp["industry"]
        with engine.connect() as conn:
            row2 = conn.execute(
                __import__("sqlalchemy").text(
                    "SELECT close, pe_ttm, pb, roe, market_cap, turnover_rate, change_pct, volume_ratio, dividend_yield FROM stock_daily WHERE code = :code ORDER BY date DESC LIMIT 1"
                ),
                {"code": code},
            ).fetchone()
        if row2:
            latest = dict(row2._mapping)
    except Exception:
        pass

    # ── Fetch daily OHLCV via Sina K-line API ──
    df = fetch_kline_sina(code, days=250)
    if df.empty or len(df) < 20:
        return {
            "code": code, "name": basic.get("name", ""),
            "industry": basic.get("industry", ""), "market": basic.get("market", ""),
            "latest": {k: v for k, v in latest.items() if v is not None and k != "code"},
            "periods": {},
            "error": f"K线数据不足（仅{len(df)}条），请检查网络或稍后重试",
        }

    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()

    # ── Compute indicators ──
    period_analysis: dict = {}

    def _analyze(series: pd.DataFrame) -> dict | None:
        if len(series) < 20:
            return None
        closes = series["close"].tolist()
        highs = series["high"].tolist() if "high" in series.columns else closes
        lows = series["low"].tolist() if "low" in series.columns else closes
        volumes = series["volume"].tolist() if "volume" in series.columns else []
        dates = [str(d.date()) for d in series.index]

        ma5 = sma(closes, 5)
        ma20 = sma(closes, 20)
        ma60 = sma(closes, 60)
        macd_result = macd(closes)
        rsi14 = rsi(closes, 14)
        kdj_result = kdj(highs, lows, closes)
        boll_result = bollinger(closes)
        vol5 = sma(volumes, 5) if volumes else []
        vol20 = sma(volumes, 20) if volumes else []

        last_close = closes[-1]
        last_m = latest_value

        # MACD cross detection
        dif_vals, dea_vals = macd_result["dif"], macd_result["dea"]
        cross_signal = ""
        for i in range(max(0, len(dif_vals) - 5), len(dif_vals) - 1):
            if dif_vals[i] is None or dea_vals[i] is None:
                continue
            prev_dif, prev_dea = dif_vals[i - 1], dea_vals[i - 1]
            cur_dif, cur_dea = dif_vals[i], dea_vals[i]
            if prev_dif is not None and prev_dea is not None:
                if prev_dif <= prev_dea and cur_dif > cur_dea:
                    cross_signal = "金叉"
                elif prev_dif >= prev_dea and cur_dif < cur_dea:
                    cross_signal = "死叉"

        ma5_v, ma20_v, ma60_v = last_m(ma5), last_m(ma20), last_m(ma60)
        trend = "震荡"
        if ma5_v and ma20_v and ma60_v:
            if ma5_v > ma20_v > ma60_v:
                trend = "多头排列（上升趋势）"
            elif ma5_v < ma20_v < ma60_v:
                trend = "空头排列（下降趋势）"

        upper_v, lower_v = last_m(boll_result["upper"]), last_m(boll_result["lower"])
        vol5_v, vol20_v = last_m(vol5), last_m(vol20)
        boll_pos = None
        if upper_v and lower_v and upper_v != lower_v:
            boll_pos = round((last_close - lower_v) / (upper_v - lower_v) * 100, 1)

        return {
            "last_date": dates[-1] if dates else "",
            "last_close": last_close,
            "data_points": len(closes),
            "ma5": ma5_v, "ma20": ma20_v, "ma60": ma60_v,
            "trend": trend,
            "macd_dif": last_m(macd_result["dif"]),
            "macd_dea": last_m(macd_result["dea"]),
            "macd_bar": last_m(macd_result["bar"]),
            "macd_cross": cross_signal,
            "rsi14": last_m(rsi14),
            "kdj_k": last_m(kdj_result["k"]), "kdj_d": last_m(kdj_result["d"]), "kdj_j": last_m(kdj_result["j"]),
            "boll_upper": upper_v, "boll_middle": last_m(boll_result["middle"]), "boll_lower": lower_v,
            "boll_position": boll_pos,
            "vol5_avg": vol5_v, "vol20_avg": vol20_v,
            "vol_ratio": round(vol5_v / vol20_v, 2) if (vol5_v and vol20_v and vol20_v > 0) else None,
        }

    # Daily
    daily_slice = df.tail(120)
    da = _analyze(daily_slice)
    if da:
        period_analysis["daily"] = da

    # Weekly resample
    if "weekly" in periods:
        weekly = df.resample("W").agg({
            "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
        }).dropna().tail(60)
        wa = _analyze(weekly)
        if wa:
            period_analysis["weekly"] = wa

    # Monthly resample
    if "monthly" in periods:
        monthly = df.resample("ME").agg({
            "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
        }).dropna().tail(24)
        ma = _analyze(monthly)
        if ma:
            period_analysis["monthly"] = ma

    # Intraday (best-effort)
    intraday_info = {}
    try:
        from services.data_fetcher import fetch_intraday_sina
        idf = fetch_intraday_sina(code)
        if not idf.empty:
            lb, fb = idf.iloc[-1], idf.iloc[0]
            day_close = float(lb["close"])
            # Use second-to-last daily bar as previous close for correct change%
            prev_close = float(df["close"].iloc[-2]) if len(df) > 1 else 0
            change = ((day_close - prev_close) / prev_close * 100) if prev_close > 0 else 0
            intraday_info = {
                "open": round(float(fb["close"]), 2),
                "high": round(float(idf["high"].max()), 2),
                "low": round(float(idf["low"].min()), 2),
                "price": round(day_close, 2),
                "change_pct": round(change, 2),
                "prev_close": round(prev_close, 2),
            }
    except Exception:
        pass

    # Use the freshest close from K-line, fall back to DB
    kline_close = float(df["close"].iloc[-1]) if len(df) > 0 else None
    latest_out = {k: v for k, v in latest.items() if v is not None and k != "code"}
    if kline_close is not None:
        latest_out["close"] = kline_close

    return {
        "code": code, "name": basic.get("name", ""),
        "industry": basic.get("industry", ""), "market": basic.get("market", ""),
        "latest": latest_out,
        "intraday": intraday_info,
        "periods": period_analysis,
        "data_date": str(df.index[-1].date()) if len(df) > 0 else "",
    }


def _exec_search_stocks(args: dict) -> dict:
    from services.screener import get_all_stocks_df, apply_filters
    filters: dict = {}
    for k in ("keyword", "industry", "market", "industry_name"):
        if args.get(k):
            filters[k] = args[k]
    filters["exclude_st"] = args.get("exclude_st", True)
    for k in ("pe_min", "pe_max", "pb_min", "pb_max", "roe_min",
              "market_cap_min", "market_cap_max", "dividend_yield_min",
              "revenue_growth_min", "revenue_growth_max",
              "change_pct_min", "change_pct_max", "volume_ratio_min", "turnover_rate_min"):
        if k in args and args[k] is not None:
            filters[k] = args[k]
    if args.get("sort_by"):
        filters["sort_by"] = args["sort_by"]
    if args.get("order"):
        filters["order"] = args["order"]

    df = get_all_stocks_df()
    filtered = apply_filters(df, filters)
    total = len(filtered)
    top20 = filtered.head(20)
    cols = ["code", "name", "close", "change_pct", "pe_ttm", "pb", "roe",
            "market_cap", "turnover_rate", "volume_ratio", "industry"]
    available = [c for c in cols if c in top20.columns]
    stocks = top20[available].where(top20.notna(), None).to_dict(orient="records")
    return {"total": total, "shown": len(stocks), "stocks": stocks}


def _exec_compare_stocks(args: dict) -> dict:
    codes = args["codes"][:5]
    comparison = []
    for code in codes:
        try:
            analysis = _exec_analyze_stock({"code": code, "periods": ["daily"]})
            daily = analysis.get("periods", {}).get("daily", {})
            comparison.append({
                "code": analysis.get("code", ""), "name": analysis.get("name", ""),
                "close": daily.get("last_close"),
                "change_pct": analysis.get("latest", {}).get("change_pct"),
                "pe_ttm": analysis.get("latest", {}).get("pe_ttm"),
                "pb": analysis.get("latest", {}).get("pb"),
                "roe": analysis.get("latest", {}).get("roe"),
                "market_cap": analysis.get("latest", {}).get("market_cap"),
                "ma5": daily.get("ma5"), "ma20": daily.get("ma20"),
                "trend": daily.get("trend", ""),
                "rsi14": daily.get("rsi14"),
                "macd_cross": daily.get("macd_cross", ""),
            })
        except Exception:
            comparison.append({"code": code, "error": "获取数据失败"})
    return {"count": len(comparison), "comparison": comparison}


def _exec_market_breadth(_args: dict) -> dict:
    from services.data_fetcher import fetch_limit_stats, fetch_sector_ranking
    limits = fetch_limit_stats()
    sectors = fetch_sector_ranking()
    return {
        "limit_up_count": limits.get("zt_count", 0),
        "limit_down_count": limits.get("dt_count", 0),
        "limit_up_top": limits.get("zt_list", [])[:10],
        "limit_down_top": limits.get("dt_list", [])[:10],
        "sectors_top": sectors[:10],
        "sectors_bottom": sectors[-10:] if len(sectors) > 10 else [],
    }


TOOL_MAP = {
    "analyze_stock": _exec_analyze_stock,
    "search_stocks": _exec_search_stocks,
    "compare_stocks": _exec_compare_stocks,
    "get_market_breadth": _exec_market_breadth,
}


def run_agent(user_message: str, history: list[dict] | None = None) -> dict:
    """Non-streaming version — used for compatibility."""
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        for h in history[-20:]:
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    messages.append({"role": "user", "content": user_message})

    max_rounds = 5
    collected_data: dict = {}
    final_reply = ""

    for _round in range(max_rounds):
        api_url, model, api_key = _api_params()
        body: dict = {"model": model, "messages": messages, "temperature": 0.3, "max_tokens": 2048, "thinking": {"type": "disabled"}}
        body["tools"] = ALL_TOOLS
        body["tool_choice"] = "auto"

        resp = requests.post(
            f"{api_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body, timeout=300,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"LLM API 错误 ({resp.status_code}): {resp.text[:500]}")

        choice = resp.json()["choices"][0]
        msg = choice["message"]

        assistant_msg: dict = {"role": "assistant", "content": msg.get("content") or ""}
        if msg.get("tool_calls"):
            assistant_msg["tool_calls"] = msg["tool_calls"]
        if msg.get("reasoning_content"):
            assistant_msg["reasoning_content"] = msg["reasoning_content"]
        messages.append(assistant_msg)

        if not msg.get("tool_calls"):
            final_reply = msg.get("content") or ""
            break

        for tc in msg["tool_calls"]:
            func_name = tc["function"]["name"]
            try:
                func_args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                func_args = {}
            try:
                if func_name in TOOL_MAP:
                    result = TOOL_MAP[func_name](func_args)
                    collected_data[func_name] = result
                    tool_result = json.dumps(result, ensure_ascii=False, default=str)
                else:
                    tool_result = json.dumps({"error": f"Unknown tool: {func_name}"})
            except Exception as e:
                tool_result = json.dumps({"error": str(e)}, ensure_ascii=False)
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": tool_result})
    else:
        messages.append({"role": "user", "content": "请基于已获取的数据给出最终分析。"})
        try:
            api_url, model, api_key = _api_params()
            resp = requests.post(
                f"{api_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "temperature": 0.3, "max_tokens": 2048},
                timeout=300,
            )
            final_reply = resp.json()["choices"][0]["message"].get("content") or ""
        except Exception:
            final_reply = "分析超时，请简化问题重试。"

    return {"reply": final_reply, "data": collected_data}


def run_agent_stream(user_message: str, history: list[dict] | None = None) -> Generator[str, None, None]:
    """Streaming version: yields SSE-formatted strings."""
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        for h in history[-20:]:
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    messages.append({"role": "user", "content": user_message})

    def sse(event: str, data: dict | str) -> str:
        payload = json.dumps(data, ensure_ascii=False)
        return f"event: {event}\ndata: {payload}\n\n"

    max_rounds = 5
    collected_data: dict = {}

    for _round in range(max_rounds):
        tool_calls_info: list[dict] = []
        assistant_content = ""

        try:
            for chunk in _stream_llm(messages, ALL_TOOLS):
                if chunk["type"] == "token":
                    assistant_content += chunk["content"]
                    yield sse("token", chunk["content"])
                elif chunk["type"] == "tool_calls":
                    tool_calls_info = chunk["calls"]
        except RuntimeError as e:
            yield sse("error", str(e))
            return

        # Build assistant message for history
        assistant_msg: dict = {"role": "assistant", "content": assistant_content}
        if tool_calls_info:
            assistant_msg["tool_calls"] = [
                {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                for tc in tool_calls_info
            ]
        messages.append(assistant_msg)

        if not tool_calls_info:
            break

        # Execute tools
        for tc in tool_calls_info:
            yield sse("tool_start", {"name": tc["name"], "arguments": tc["arguments"]})
            try:
                func_args = json.loads(tc["arguments"])
            except json.JSONDecodeError:
                func_args = {}
            try:
                if tc["name"] in TOOL_MAP:
                    result = TOOL_MAP[tc["name"]](func_args)
                    collected_data[tc["name"]] = result
                    tool_result = json.dumps(result, ensure_ascii=False, default=str)
                else:
                    tool_result = json.dumps({"error": f"Unknown tool: {tc['name']}"})
            except Exception as e:
                tool_result = json.dumps({"error": str(e)}, ensure_ascii=False)
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": tool_result})
            yield sse("tool_done", {"name": tc["name"]})
    else:
        messages.append({"role": "user", "content": "请基于已获取的数据给出最终分析。"})
        try:
            for chunk in _stream_llm(messages):
                if chunk["type"] == "token":
                    yield sse("token", chunk["content"])
        except Exception:
            yield sse("error", "分析超时，请简化问题重试。")

    yield sse("done", {"data": collected_data})
