"""
K-line pattern recognition for A-share stocks.

Pure functions operating on raw price lists (high, low, close, volume).
Zero dependencies beyond Python stdlib — no pandas, no numpy.
"""

from __future__ import annotations

from math import isclose
from typing import Any


# ---------------------------------------------------------------------------
# Pivot detection
# ---------------------------------------------------------------------------

def _find_pivot_highs(
    data: list[float],
    left: int = 2,
    right: int = 2,
) -> list[int]:
    """Return indices of pivot highs (local maxima) in *data*.

    A bar at index *i* is a pivot high when its value is strictly greater
    than the *left* bars before it **and** greater than or equal to the
    *right* bars after it (the equal-on-right rule keeps plateaus from
    producing multiple false pivots).
    """
    n = len(data)
    pivots: list[int] = []
    for i in range(left, n - right):
        val = data[i]
        # Must be higher than all left neighbours
        if any(val <= data[i - d] for d in range(1, left + 1)):
            continue
        # Must be >= all right neighbours (allow equality so plateaus collapse)
        if any(val < data[i + d] for d in range(1, right + 1)):
            continue
        pivots.append(i)
    return pivots


def _find_pivot_lows(
    data: list[float],
    left: int = 2,
    right: int = 2,
) -> list[int]:
    """Return indices of pivot lows (local minima) in *data*."""
    n = len(data)
    pivots: list[int] = []
    for i in range(left, n - right):
        val = data[i]
        if any(val >= data[i - d] for d in range(1, left + 1)):
            continue
        if any(val > data[i + d] for d in range(1, right + 1)):
            continue
        pivots.append(i)
    return pivots


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _last_n(items: list[int], n: int) -> list[int]:
    """Return the last *n* elements of *items* (or all if shorter)."""
    return items[-n:] if len(items) > n else items


def _pct_diff(a: float, b: float) -> float:
    """Percentage absolute difference between two prices."""
    if a == 0 and b == 0:
        return 0.0
    denom = (abs(a) + abs(b)) / 2
    if denom == 0:
        return 0.0
    return abs(a - b) / denom * 100


def _is_near(a: float, b: float, max_pct: float = 3.0) -> bool:
    """Return True when two prices are within *max_pct* percent of each other."""
    return _pct_diff(a, b) <= max_pct


def _avg(lst: list[float]) -> float:
    """Arithmetic mean, returns 0.0 for empty list."""
    if not lst:
        return 0.0
    return sum(lst) / len(lst)


def _round2(v: float) -> float:
    """Round to 2 decimal places."""
    return round(v, 2)


# ---------------------------------------------------------------------------
# Clustering for support / resistance levels
# ---------------------------------------------------------------------------

def _cluster_prices(
    pivots: list[float],
    prices: list[float],
    threshold: float = 0.02,
    min_touches: int = 2,
) -> list[dict[str, Any]]:
    """Cluster nearby pivot prices into levels.

    Returns list of dicts sorted by touches descending (then by price):
        {"price": float, "touches": int, "indices": list[int]}
    """
    if not pivots:
        return []

    # Sort pivot indices by price
    indexed = sorted(enumerate(pivots), key=lambda x: prices[x[1]])
    clusters: list[dict[str, Any]] = []

    for orig_idx, pivot_idx in indexed:
        price = prices[pivot_idx]
        placed = False
        for cluster in clusters:
            ref = cluster["price"]
            if ref == 0:
                continue
            if abs(price - ref) / ref <= threshold:
                cluster["indices"].append(pivot_idx)
                cluster["touches"] += 1
                # Update centre to weighted average
                cluster["price"] = _round2(
                    sum(prices[i] for i in cluster["indices"]) / len(cluster["indices"])
                )
                placed = True
                break
        if not placed:
            clusters.append({
                "price": _round2(price),
                "touches": 1,
                "indices": [pivot_idx],
            })

    # Filter by minimum touches, return sorted
    clusters = [c for c in clusters if c["touches"] >= min_touches]
    clusters.sort(key=lambda c: (-c["touches"], c["price"]))
    return clusters


# ---------------------------------------------------------------------------
# Double Bottom (W底)
# ---------------------------------------------------------------------------

def _detect_double_bottom(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float] | None,
    lookback: int,
) -> dict | None:
    """Detect a double-bottom pattern in the last *lookback* bars."""
    n = len(lows)
    if n < 5:
        return None

    start = max(0, n - lookback)
    window_lows = lows[start:]
    window_highs = highs[start:]
    window_vols = volumes[start:] if volumes else None

    pivot_low_idxs = _find_pivot_lows(window_lows)
    pivot_high_idxs = _find_pivot_highs(window_highs)

    if len(pivot_low_idxs) < 2:
        return None

    # We need two troughs with a peak between them.
    # Try consecutive pairs of pivot lows — the middle peak must sit between them.
    best = None  # (confidence, result_dict)

    for a_idx in range(len(pivot_low_idxs)):
        for b_idx in range(a_idx + 1, len(pivot_low_idxs)):
            il = pivot_low_idxs[a_idx]
            ir = pivot_low_idxs[b_idx]
            if ir - il < 2:  # too close
                continue

            price_left = window_lows[il]
            price_right = window_lows[ir]
            if price_left == 0 or price_right == 0:
                continue
            if not _is_near(price_left, price_right, 3.0):
                continue

            # Find the highest peak between the two troughs
            mid_peaks = [p for p in pivot_high_idxs if il < p < ir]
            if not mid_peaks:
                continue
            mid_peak_idx = max(mid_peaks, key=lambda p: window_highs[p])
            mid_peak_price = window_highs[mid_peak_idx]

            if mid_peak_price <= price_left or mid_peak_price <= price_right:
                continue  # peak must be above troughs

            confidence = 50

            # Price similarity bonus
            diff_pct = _pct_diff(price_left, price_right)
            if diff_pct <= 1.0:
                confidence += 20
            elif diff_pct <= 2.0:
                confidence += 10

            # Volume confirmation: second trough volume < first trough volume
            if window_vols:
                vol1 = window_vols[il]
                vol2 = window_vols[ir]
                if vol2 < vol1:
                    confidence += 15

            # Breakout confirmation: current price > middle peak
            current_price = closes[-1]
            if current_price > mid_peak_price:
                confidence += 15
            elif current_price > (price_left + mid_peak_price) / 2:
                confidence += 5

            confidence = min(confidence, 100)

            if best is None or confidence > best["confidence"]:
                best = {
                    "type": "double_bottom",
                    "name": "双重底 (W底)",
                    "confidence": confidence,
                    "description": (
                        f"两底价格{_round2(price_left):.2f}和{_round2(price_right):.2f}"
                        f"(价差{diff_pct:.1f}%)，颈线{_round2(mid_peak_price):.2f}"
                        + ("已突破" if closes[-1] > mid_peak_price else "尚未突破")
                    ),
                    "indices": [start + il, start + mid_peak_idx, start + ir],
                }

    if best:
        return {
            "type": best["type"],
            "name": best["name"],
            "confidence": best["confidence"],
            "description": best["description"],
            "indices": best["indices"],
        }
    return None


# ---------------------------------------------------------------------------
# Double Top (M顶)
# ---------------------------------------------------------------------------

def _detect_double_top(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float] | None,
    lookback: int,
) -> dict | None:
    """Detect a double-top pattern in the last *lookback* bars."""
    n = len(highs)
    if n < 5:
        return None

    start = max(0, n - lookback)
    window_highs = highs[start:]
    window_lows = lows[start:]
    window_vols = volumes[start:] if volumes else None

    pivot_high_idxs = _find_pivot_highs(window_highs)
    pivot_low_idxs = _find_pivot_lows(window_lows)

    if len(pivot_high_idxs) < 2:
        return None

    best = None

    for a_idx in range(len(pivot_high_idxs)):
        for b_idx in range(a_idx + 1, len(pivot_high_idxs)):
            il = pivot_high_idxs[a_idx]
            ir = pivot_high_idxs[b_idx]
            if ir - il < 2:
                continue

            price_left = window_highs[il]
            price_right = window_highs[ir]
            if price_left == 0 or price_right == 0:
                continue
            if not _is_near(price_left, price_right, 3.0):
                continue

            # Find the lowest trough between the two peaks
            mid_troughs = [p for p in pivot_low_idxs if il < p < ir]
            if not mid_troughs:
                continue
            mid_trough_idx = min(mid_troughs, key=lambda p: window_lows[p])
            mid_trough_price = window_lows[mid_trough_idx]

            if mid_trough_price >= price_left or mid_trough_price >= price_right:
                continue

            confidence = 50

            diff_pct = _pct_diff(price_left, price_right)
            if diff_pct <= 1.0:
                confidence += 20
            elif diff_pct <= 2.0:
                confidence += 10

            # Volume: second peak volume < first peak volume
            if window_vols:
                vol1 = window_vols[il]
                vol2 = window_vols[ir]
                if vol2 < vol1:
                    confidence += 15

            # Breakdown confirmation: current price < middle trough
            current_price = closes[-1]
            if current_price < mid_trough_price:
                confidence += 15

            confidence = min(confidence, 100)

            if best is None or confidence > best["confidence"]:
                best = {
                    "type": "double_top",
                    "name": "双重顶 (M顶)",
                    "confidence": confidence,
                    "description": (
                        f"两顶价格{_round2(price_left):.2f}和{_round2(price_right):.2f}"
                        f"(价差{diff_pct:.1f}%)，颈线{_round2(mid_trough_price):.2f}"
                        + ("已跌破" if closes[-1] < mid_trough_price else "尚未跌破")
                    ),
                    "indices": [start + il, start + mid_trough_idx, start + ir],
                }

    if best:
        return {
            "type": best["type"],
            "name": best["name"],
            "confidence": best["confidence"],
            "description": best["description"],
            "indices": best["indices"],
        }
    return None


# ---------------------------------------------------------------------------
# Head & Shoulders Bottom (头肩底)
# ---------------------------------------------------------------------------

def _detect_head_shoulders_bottom(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float] | None,
    lookback: int,
) -> dict | None:
    """Detect an inverse head-and-shoulders (head & shoulders bottom)."""
    n = len(lows)
    if n < 20:
        return None

    start = max(0, n - lookback)
    window_lows = lows[start:]
    window_highs = highs[start:]
    window_vols = volumes[start:] if volumes else None

    pivot_low_idxs = _find_pivot_lows(window_lows)
    if len(pivot_low_idxs) < 3:
        return None

    best = None

    for i in range(len(pivot_low_idxs) - 2):
        ls = pivot_low_idxs[i]       # left shoulder
        hd = pivot_low_idxs[i + 1]   # head
        rs = pivot_low_idxs[i + 2]   # right shoulder

        # Head must be lower than both shoulders
        head_price = window_lows[hd]
        ls_price = window_lows[ls]
        rs_price = window_lows[rs]

        if head_price >= ls_price or head_price >= rs_price:
            continue

        # Shoulders should be roughly at the same level (within 5%)
        if not _is_near(ls_price, rs_price, 5.0):
            continue

        # Neckline: line connecting the two highs between LS-H and H-RS
        peaks_between_ls_hd = [p for p in _find_pivot_highs(window_highs) if ls < p < hd]
        peaks_between_hd_rs = [p for p in _find_pivot_highs(window_highs) if hd < p < rs]

        confidence = 50

        neckline_price: float | None = None
        if peaks_between_ls_hd and peaks_between_hd_rs:
            neck_hi1 = max(peaks_between_ls_hd, key=lambda p: window_highs[p])
            neck_hi2 = max(peaks_between_hd_rs, key=lambda p: window_highs[p])
            neckline_price = _round2((window_highs[neck_hi1] + window_highs[neck_hi2]) / 2)
            # Neckline should be relatively flat
            if _is_near(window_highs[neck_hi1], window_highs[neck_hi2], 5.0):
                confidence += 10
        else:
            # Use the mid-point between shoulders as approximate neckline
            neckline_price = _round2((ls_price + rs_price) / 2)

        # Shoulder symmetry bonus
        if _is_near(ls_price, rs_price, 2.0):
            confidence += 10

        current_price = closes[-1]

        # Breakout: current price > neckline
        if neckline_price and current_price > neckline_price:
            confidence += 15
            if window_vols and len(window_vols) > 10:
                recent_vol = _avg(window_vols[-5:])
                older_vol = _avg(window_vols[-15:-5])
                if older_vol > 0 and recent_vol > older_vol:
                    confidence += 10

        confidence = min(confidence, 100)

        # Format description
        desc = (
            f"头肩底: 左肩{_round2(ls_price):.2f}, 头部{_round2(head_price):.2f}, "
            f"右肩{_round2(rs_price):.2f}, 颈线{_round2(neckline_price or 0):.2f}"
        )
        if neckline_price and current_price > neckline_price:
            desc += "已突破"
        else:
            desc += "尚未突破"

        if best is None or confidence > best["confidence"]:
            best = {
                "type": "head_shoulders_bottom",
                "name": "头肩底",
                "confidence": confidence,
                "description": desc,
                "indices": [start + ls, start + hd, start + rs],
            }

    if best:
        return {
            "type": best["type"],
            "name": best["name"],
            "confidence": best["confidence"],
            "description": best["description"],
            "indices": best["indices"],
        }
    return None


# ---------------------------------------------------------------------------
# Head & Shoulders Top (头肩顶)
# ---------------------------------------------------------------------------

def _detect_head_shoulders_top(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float] | None,
    lookback: int,
) -> dict | None:
    """Detect a head-and-shoulders top pattern."""
    n = len(highs)
    if n < 20:
        return None

    start = max(0, n - lookback)
    window_highs = highs[start:]
    window_lows = lows[start:]
    window_vols = volumes[start:] if volumes else None

    pivot_high_idxs = _find_pivot_highs(window_highs)
    if len(pivot_high_idxs) < 3:
        return None

    best = None

    for i in range(len(pivot_high_idxs) - 2):
        ls = pivot_high_idxs[i]       # left shoulder
        hd = pivot_high_idxs[i + 1]   # head
        rs = pivot_high_idxs[i + 2]   # right shoulder

        head_price = window_highs[hd]
        ls_price = window_highs[ls]
        rs_price = window_highs[rs]

        # Head must be higher than both shoulders
        if head_price <= ls_price or head_price <= rs_price:
            continue

        # Shoulders roughly at same level (within 5%)
        if not _is_near(ls_price, rs_price, 5.0):
            continue

        # Neckline: line connecting lows between LS-H and H-RS
        troughs_between_ls_hd = [p for p in _find_pivot_lows(window_lows) if ls < p < hd]
        troughs_between_hd_rs = [p for p in _find_pivot_lows(window_lows) if hd < p < rs]

        confidence = 50

        neckline_price: float | None = None
        if troughs_between_ls_hd and troughs_between_hd_rs:
            neck_lo1 = min(troughs_between_ls_hd, key=lambda p: window_lows[p])
            neck_lo2 = min(troughs_between_hd_rs, key=lambda p: window_lows[p])
            neckline_price = _round2((window_lows[neck_lo1] + window_lows[neck_lo2]) / 2)
            if _is_near(window_lows[neck_lo1], window_lows[neck_lo2], 5.0):
                confidence += 10
        else:
            neckline_price = _round2((ls_price + rs_price) / 2)

        if _is_near(ls_price, rs_price, 2.0):
            confidence += 10

        current_price = closes[-1]

        # Breakdown: current price < neckline
        if neckline_price and current_price < neckline_price:
            confidence += 15

        confidence = min(confidence, 100)

        desc = (
            f"头肩顶: 左肩{_round2(ls_price):.2f}, 头部{_round2(head_price):.2f}, "
            f"右肩{_round2(rs_price):.2f}, 颈线{_round2(neckline_price or 0):.2f}"
        )
        if neckline_price and current_price < neckline_price:
            desc += "已跌破"
        else:
            desc += "尚未跌破"

        if best is None or confidence > best["confidence"]:
            best = {
                "type": "head_shoulders_top",
                "name": "头肩顶",
                "confidence": confidence,
                "description": desc,
                "indices": [start + ls, start + hd, start + rs],
            }

    if best:
        return {
            "type": best["type"],
            "name": best["name"],
            "confidence": best["confidence"],
            "description": best["description"],
            "indices": best["indices"],
        }
    return None


# ---------------------------------------------------------------------------
# Ascending Triangle (上升三角形)
# ---------------------------------------------------------------------------

def _detect_ascending_triangle(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float] | None,
    lookback: int,
) -> dict | None:
    """Detect an ascending triangle: flat resistance + rising support."""
    n = len(highs)
    min_bars = 20

    if n < min_bars:
        return None

    # Analyse over the lookback window
    start = max(0, n - lookback)
    # But for triangles we require at least 20 bars; expand if needed
    if lookback < min_bars:
        start = max(0, n - min_bars)

    window_n = n - start
    if window_n < min_bars:
        return None

    window_highs = highs[start:]
    window_lows = lows[start:]

    # Pivot highs → resistance candidates
    pivot_high_idxs = _find_pivot_highs(window_highs)
    pivot_low_idxs = _find_pivot_lows(window_lows)

    if len(pivot_high_idxs) < 2 or len(pivot_low_idxs) < 2:
        return None

    # ---- Find horizontal resistance (flat top) ----
    # Cluster pivot high prices
    hi_prices = [window_highs[i] for i in pivot_high_idxs]
    clusters = _cluster_prices(
        pivot_high_idxs, window_highs, threshold=0.02, min_touches=2
    )
    if not clusters:
        return None

    # Use the cluster with most touches as the resistance level
    best_cluster = clusters[0]
    resistance_price = best_cluster["price"]
    resistance_touches = best_cluster["touches"]

    # Filter pivot highs that belong to this resistance (within 2%)
    res_high_idxs = [
        idx for idx in pivot_high_idxs
        if resistance_price > 0 and abs(window_highs[idx] - resistance_price) / resistance_price <= 0.02
    ]

    if len(res_high_idxs) < 2:
        return None

    # ---- Check rising lows ----
    # The pivot lows should be trending upward overall
    low_prices = [window_lows[i] for i in pivot_low_idxs]
    if len(low_prices) < 2:
        return None

    # Simple rising check: last low > first low, and majority of adjacent pairs are rising
    rising_count = 0
    for j in range(1, len(pivot_low_idxs)):
        if window_lows[pivot_low_idxs[j]] > window_lows[pivot_low_idxs[j - 1]]:
            rising_count += 1

    if len(pivot_low_idxs) <= 1:
        return None

    rising_ratio = rising_count / (len(pivot_low_idxs) - 1) if len(pivot_low_idxs) > 1 else 0
    first_low = window_lows[pivot_low_idxs[0]]
    last_low = window_lows[pivot_low_idxs[-1]]

    if rising_ratio < 0.5 or last_low <= first_low:
        return None

    # Confidence
    confidence = 40
    confidence += min(resistance_touches * 5, 25)  # up to +25 for more touches
    confidence += min(int(rising_ratio * 20), 20)  # up to +20 for consistent rising

    # Current price near resistance = breakout imminent
    current_price = closes[-1]
    if resistance_price > 0:
        proximity = 1 - abs(current_price - resistance_price) / resistance_price
        if proximity > 0.98:  # within 2% of resistance
            confidence += 10

    confidence = min(confidence, 100)

    return {
        "type": "ascending_triangle",
        "name": "上升三角形",
        "confidence": confidence,
        "description": (
            f"阻力位{_round2(resistance_price):.2f}(触及{resistance_touches}次), "
            f"低点从{_round2(first_low):.2f}抬高至{_round2(last_low):.2f}"
        ),
        "indices": [start] * 3,  # whole-window pattern
    }


# ---------------------------------------------------------------------------
# Descending Triangle (下降三角形)
# ---------------------------------------------------------------------------

def _detect_descending_triangle(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float] | None,
    lookback: int,
) -> dict | None:
    """Detect a descending triangle: flat support + falling resistance."""
    n = len(highs)
    min_bars = 20

    if n < min_bars:
        return None

    start = max(0, n - lookback)
    if lookback < min_bars:
        start = max(0, n - min_bars)

    window_n = n - start
    if window_n < min_bars:
        return None

    window_highs = highs[start:]
    window_lows = lows[start:]

    pivot_high_idxs = _find_pivot_highs(window_highs)
    pivot_low_idxs = _find_pivot_lows(window_lows)

    if len(pivot_low_idxs) < 2 or len(pivot_high_idxs) < 2:
        return None

    # ---- Find horizontal support (flat bottom) ----
    lo_prices = [window_lows[i] for i in pivot_low_idxs]
    clusters = _cluster_prices(
        pivot_low_idxs, window_lows, threshold=0.02, min_touches=2
    )
    if not clusters:
        return None

    best_cluster = clusters[0]
    support_price = best_cluster["price"]
    support_touches = best_cluster["touches"]

    # Filter pivot lows belonging to this support
    sup_low_idxs = [
        idx for idx in pivot_low_idxs
        if support_price > 0 and abs(window_lows[idx] - support_price) / support_price <= 0.02
    ]
    if len(sup_low_idxs) < 2:
        return None

    # ---- Check falling highs ----
    high_prices = [window_highs[i] for i in pivot_high_idxs]
    if len(high_prices) < 2:
        return None

    falling_count = 0
    for j in range(1, len(pivot_high_idxs)):
        if window_highs[pivot_high_idxs[j]] < window_highs[pivot_high_idxs[j - 1]]:
            falling_count += 1

    falling_ratio = falling_count / (len(pivot_high_idxs) - 1) if len(pivot_high_idxs) > 1 else 0
    first_high = window_highs[pivot_high_idxs[0]]
    last_high = window_highs[pivot_high_idxs[-1]]

    if falling_ratio < 0.5 or last_high >= first_high:
        return None

    # Confidence
    confidence = 40
    confidence += min(support_touches * 5, 25)
    confidence += min(int(falling_ratio * 20), 20)

    current_price = closes[-1]
    if support_price > 0:
        proximity = 1 - abs(current_price - support_price) / support_price
        if proximity > 0.98:
            confidence += 10

    confidence = min(confidence, 100)

    return {
        "type": "descending_triangle",
        "name": "下降三角形",
        "confidence": confidence,
        "description": (
            f"支撑位{_round2(support_price):.2f}(触及{support_touches}次), "
            f"高点从{_round2(first_high):.2f}降低至{_round2(last_high):.2f}"
        ),
        "indices": [start] * 3,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_patterns(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float] | None = None,
) -> list[dict[str, Any]]:
    """Detect K-line patterns from OHLCV data.

    Parameters
    ----------
    highs: High prices, oldest first.
    lows: Low prices, oldest first.
    closes: Close prices, oldest first.
    volumes: Volume data (optional). When provided enables volume-conformation checks.

    Returns
    -------
    list of pattern dicts, each with keys:
        type       — str, machine-readable pattern id
        name       — str, Chinese display name
        confidence — int, 0-100
        description— str, human-readable summary in Chinese
        indices    — list[int], key bar indices in the original arrays
    """
    if len(highs) < 5 or len(lows) < 5 or len(closes) < 5:
        return []

    # Basic data-quality check: all prices identical → no patterns
    if len(set(highs)) <= 1 and len(set(lows)) <= 1 and len(set(closes)) <= 1:
        return []

    lookback = min(60, len(highs))

    detectors = [
        _detect_double_bottom,
        _detect_double_top,
        _detect_head_shoulders_bottom,
        _detect_head_shoulders_top,
        _detect_ascending_triangle,
        _detect_descending_triangle,
    ]

    results: list[dict[str, Any]] = []
    for detector in detectors:
        try:
            found = detector(highs, lows, closes, volumes, lookback)
            if found:
                results.append(found)
        except Exception:
            continue

    # Sort by confidence descending
    results.sort(key=lambda p: p["confidence"], reverse=True)
    return results


def find_support_resistance(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    window: int = 60,
) -> dict[str, Any]:
    """Find support and resistance levels from recent pivot points.

    Parameters
    ----------
    highs / lows / closes: OHLC price arrays (oldest first).
    window: Number of recent bars to analyse.

    Returns
    -------
    dict with keys:
        resistance        — list[{"price": float, "touches": int}]
        support           — list[{"price": float, "touches": int}]
        current_price     — float
        nearest_resistance— float (or 0.0 if none)
        nearest_support   — float (or 0.0 if none)
    """
    if not highs or not lows or not closes:
        return {
            "resistance": [],
            "support": [],
            "current_price": 0.0,
            "nearest_resistance": 0.0,
            "nearest_support": 0.0,
        }

    n = len(highs)
    start = max(0, n - window)
    window_highs = highs[start:]
    window_lows = lows[start:]
    current_price = _round2(closes[-1])

    # Find pivot points in window
    ph = _find_pivot_highs(window_highs)
    pl = _find_pivot_lows(window_lows)

    # Cluster resistance levels from pivot highs
    res_raw = _cluster_prices(ph, window_highs, threshold=0.02, min_touches=1)
    resistance = [
        {"price": c["price"], "touches": c["touches"]}
        for c in res_raw
    ]

    # Cluster support levels from pivot lows
    sup_raw = _cluster_prices(pl, window_lows, threshold=0.02, min_touches=1)
    support = [
        {"price": c["price"], "touches": c["touches"]}
        for c in sup_raw
    ]

    # Nearest resistance = lowest resistance above current_price
    nearest_resistance = 0.0
    res_above = [r for r in resistance if r["price"] > current_price]
    if res_above:
        nearest_resistance = min(res_above, key=lambda r: r["price"])["price"]

    # Nearest support = highest support below current_price
    nearest_support = 0.0
    sup_below = [s for s in support if s["price"] < current_price]
    if sup_below:
        nearest_support = max(sup_below, key=lambda s: s["price"])["price"]

    return {
        "resistance": resistance,
        "support": support,
        "current_price": current_price,
        "nearest_resistance": _round2(nearest_resistance),
        "nearest_support": _round2(nearest_support),
    }
