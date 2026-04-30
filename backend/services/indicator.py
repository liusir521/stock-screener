"""Technical indicator computation — pure functions, zero dependencies."""


def sma(data: list[float], period: int) -> list[float | None]:
    """Simple Moving Average."""
    if len(data) < period:
        return [None] * len(data)
    result: list[float | None] = []
    window_sum = sum(data[:period])
    for i in range(len(data)):
        if i < period - 1:
            result.append(None)
        else:
            if i >= period:
                window_sum += data[i] - data[i - period]
            result.append(round(window_sum / period, 4))
    return result


def ema(data: list[float], period: int) -> list[float | None]:
    """Exponential Moving Average. k = 2 / (period + 1)."""
    if len(data) < period:
        return [None] * len(data)
    k = 2 / (period + 1)
    result: list[float | None] = []
    prev = data[0]
    for i, v in enumerate(data):
        prev = v * k + prev * (1 - k)
        result.append(round(prev, 4))
    return result


def macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, list[float | None]]:
    """MACD indicator. Returns {dif, dea, bar}."""
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    n = len(closes)
    dif: list[float | None] = []
    for i in range(n):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            dif.append(round(ema_fast[i] - ema_slow[i], 4))  # type: ignore
        else:
            dif.append(None)
    dea = ema([v if v is not None else 0 for v in dif], signal)
    dea_adj: list[float | None] = []
    for i in range(n):
        if dif[i] is not None and i >= signal - 1:
            dea_adj.append(round(dea[i], 4))  # type: ignore
        else:
            dea_adj.append(None)
    bar: list[float | None] = []
    for i in range(n):
        if dif[i] is not None and dea_adj[i] is not None:
            bar.append(round((dif[i] - dea_adj[i]) * 2, 4))  # type: ignore
        else:
            bar.append(None)
    return {"dif": dif, "dea": dea_adj, "bar": bar}


def rsi(closes: list[float], period: int = 14) -> list[float | None]:
    """Relative Strength Index (Wilder's smoothing)."""
    if len(closes) < period + 1:
        return [None] * len(closes)
    result: list[float | None] = [None] * len(closes)
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(diff if diff > 0 else 0)
        losses.append(-diff if diff < 0 else 0)

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains) + 1):
        if avg_loss == 0:
            rsi_val = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_val = 100 - 100 / (1 + rs)
        result[period + (i - period)] = round(rsi_val, 2)
        if i < len(gains):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    return result


def kdj(
    highs: list[float], lows: list[float], closes: list[float],
    n: int = 9, m1: int = 3, m2: int = 3,
) -> dict[str, list[float | None]]:
    """KDJ indicator. Returns {k, d, j}."""
    length = len(closes)
    k_vals: list[float | None] = [None] * length
    d_vals: list[float | None] = [None] * length
    j_vals: list[float | None] = [None] * length

    if length < n:
        return {"k": k_vals, "d": d_vals, "j": j_vals}

    prev_k = 50.0
    prev_d = 50.0
    for i in range(n - 1, length):
        hh = max(highs[i - n + 1:i + 1])
        ll = min(lows[i - n + 1:i + 1])
        rsv = ((closes[i] - ll) / (hh - ll)) * 100 if hh != ll else 50.0
        k = (prev_k * (m1 - 1) + rsv) / m1
        d = (prev_d * (m2 - 1) + k) / m2
        j = 3 * k - 2 * d
        k_vals[i] = round(k, 2)
        d_vals[i] = round(d, 2)
        j_vals[i] = round(j, 2)
        prev_k, prev_d = k, d

    return {"k": k_vals, "d": d_vals, "j": j_vals}


def bollinger(closes: list[float], period: int = 20, std_dev: float = 2.0) -> dict[str, list[float | None]]:
    """Bollinger Bands. Returns {upper, middle, lower}."""
    n = len(closes)
    middle = sma(closes, period)
    upper: list[float | None] = [None] * n
    lower: list[float | None] = [None] * n

    for i in range(period - 1, n):
        window = closes[i - period + 1:i + 1]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        std = variance ** 0.5
        upper[i] = round(mean + std_dev * std, 4)
        lower[i] = round(mean - std_dev * std, 4)

    return {"upper": upper, "middle": middle, "lower": lower}


def latest_value(series: list[float | None]) -> float | None:
    """Return the most recent non-None value from a list."""
    for v in reversed(series):
        if v is not None:
            return v
    return None
