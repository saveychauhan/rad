"""
RAD NEURAL TOOL BLUEPRINT v1.0
--------------------------------
Tool: Market Analyzer (market_analyzer)
Creator: Rad. Creator: Sawan Chauhan.
Purpose: Autonomous share market data fetching, technical analysis,
         trend prediction, and signal generation.
Stage: INCUBATION (Stage 1)

ARCHITECTURE:
- Pure Python, zero heavy dependencies (no pandas/numpy).
- Async HTTP fetcher targeting Yahoo Finance v8 API.
- Manual computation of SMA, EMA, RSI, MACD, Bollinger Bands.
- Lightweight linear regression for 5-day price projection.
- Optimized for MacBook Air 2017 (low memory, low CPU).
"""

import asyncio
import json
import math
import ssl
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any


# ── CONFIGURATION ──────────────────────────────────────────
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
DEFAULT_RANGE = "6mo"
DEFAULT_INTERVAL = "1d"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


# ── DATA STRUCTURES ────────────────────────────────────────
@dataclass
class TechnicalSnapshot:
    ticker: str
    timestamp: str
    current_price: float
    prev_close: float
    change: float
    change_percent: float
    volume: int
    sma_20: float
    sma_50: float
    ema_12: float
    ema_26: float
    macd: float
    macd_signal: float
    rsi_14: float
    bb_upper: float
    bb_middle: float
    bb_lower: float
    volatility: float
    support: float
    resistance: float
    signal: str           # BUY / SELL / HOLD / NEUTRAL
    confidence: float     # 0.0 - 1.0
    prediction_5d_low: float
    prediction_5d_high: float
    prediction_direction: str  # BULLISH / BEARISH / SIDEWAYS
    analysis_summary: str


# ── LOW-LEVEL FETCHER ──────────────────────────────────────
async def _fetch_json(ticker: str, range_period: str = DEFAULT_RANGE,
                      interval: str = DEFAULT_INTERVAL) -> Optional[Dict]:
    """
    Asynchronously fetches OHLCV data from Yahoo Finance v8 API.
    Returns raw JSON dict or None on failure.
    """
    url = (
        f"{YAHOO_CHART_URL.format(ticker=ticker)}"
        f"?interval={interval}&range={range_period}&includeAdjustedClose=true"
    )
    print(f"[MARKET ANALYZER] Fetching {ticker} ...")

    try:
        loop = asyncio.get_running_loop()
        req = urllib.request.Request(url, headers=HEADERS)
        # Default SSL context; Yahoo requires TLS.
        ctx = ssl.create_default_context()

        def _ blocking_get():
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                return json.loads(resp.read().decode("utf-8"))

        data = await loop.run_in_executor(None, _blocking_get)
        return data
    except Exception as exc:
        print(f"[MARKET ANALYZER] FETCH ERROR for {ticker}: {exc}")
        return None


# ── MATHEMATICAL UTILITIES (Pure Python) ─────────────────────
def _sma(values: List[float], window: int) -> List[float]:
    """Simple Moving Average. Returns list same length as input (pad front with None)."""
    if len(values) < window:
        return [None] * len(values)
    result = [None] * (window - 1)
    for i in range(window - 1, len(values)):
        result.append(sum(values[i - window + 1:i + 1]) / window)
    return result


def _ema(values: List[float], window: int) -> List[float]:
    """Exponential Moving Average."""
    if len(values) < window:
        return [None] * len(values)
    k = 2.0 / (window + 1)
    ema_values = [None] * (window - 1)
    # Seed EMA with SMA of first window
    seed = sum(values[:window]) / window
    ema_values.append(seed)
    for i in range(window, len(values)):
        ema_values.append(values[i] * k + ema_values[-1] * (1 - k))
    return ema_values


def _std_dev(values: List[float], window: int) -> List[float]:
    """Rolling population standard deviation."""
    if len(values) < window:
        return [None] * len(values)
    result = [None] * (window - 1)
    for i in range(window - 1, len(values)):
        subset = values[i - window + 1:i + 1]
        mean = sum(subset) / window
        variance = sum((x - mean) ** 2 for x in subset) / window
        result.append(math.sqrt(variance))
    return result


def _rsi(closes: List[float], window: int = 14) -> List[float]:
    """Relative Strength Index."""
    if len(closes) < window + 1:
        return [None] * len(closes)
    gains, losses = [0.0], [0.0]
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0))
        losses.append(abs(min(delta, 0)))

    avg_gains = [None] * window
    avg_losses = [None] * window
    # Initial averages
    avg_gains.append(sum(gains[1:window + 1]) / window)
    avg_losses.append(sum(losses[1:window + 1]) / window)

    for i in range(window + 1, len(closes)):
        avg_gains.append((avg_gains[-1] * (window - 1) + gains[i]) / window)
        avg_losses.append((avg_losses[-1] * (window - 1) + losses[i]) / window)

    rsi_vals = [None] * window
    for i in range(window, len(closes)):
        ag = avg_gains[i]
        al = avg_losses[i]
        if al == 0:
            rsi_vals.append(100.0)
        else:
            rs = ag / al
            rsi_vals.append(100.0 - (100.0 / (1 + rs)))
    return rsi_vals


def _linear_regression_slope(values: List[float], window: int = 5) -> float:
    """Returns slope of least-squares fit over the last `window` points."""
    subset = values[-window:]
    n = len(subset)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(subset) / n
    numerator = sum((i - x_mean) * (subset[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _support_resistance(lows: List[float], highs: List[float],
                        window: int = 20) -> Tuple[float, float]:
    """Naive support / resistance from recent min/max."""
    recent_lows = lows[-window:]
    recent_highs = highs[-window:]
    return min(recent_lows), max(recent_highs)


# ── CORE ANALYZER ────────────────────────────────────────────
def _parse_ohlcv(raw: Dict) -> Optional[Dict[str, List]]:
    """Extracts timestamp, open, high, low, close, volume lists."""
    try:
        result = raw["chart"]["result"][0]
        meta = result["meta"]
        timestamps = result.get("timestamp", [])
        ohlc = result["indicators"]["quote"][0]
        adjclose = result["indicators"]["adjclose"][0]["adjclose"] if "adjclose" in result["indicators"] else ohlc["close"]

        # Filter out None values (Yahoo sometimes returns nulls)
        clean = []
        for i in range(len(timestamps)):
            if (ohlc["open"][i] is not None and ohlc["high"][i] is not None and
                ohlc["low"][i] is not None and ohlc["close"][i] is not None and
                ohlc["volume"][i] is not None):
                clean.append(i)

        return {
            "timestamps": [timestamps[i] for i in clean],
            "open": [ohlc["open"][i] for i in clean],
            "high": [ohlc["high"][i] for i in clean],
            "low": [ohlc["low"][i] for i in clean],
            "close": [adjclose[i] if i < len(adjclose) and adjclose[i] is not None else ohlc["close"][i] for i in clean],
            "volume": [ohlc["volume"][i] for i in clean],
            "currency": meta.get("currency", "USD"),
            "regularMarketPrice": meta.get("regularMarketPrice"),
            "previousClose": meta.get("previousClose"),
            "regularMarketVolume": meta.get("regularMarketVolume"),
        }
    except Exception as exc:
        print(f"[MARKET ANALYZER] PARSE ERROR: {exc}")
        return None


def _compute_all(closes: List[float], lows: List[float], highs: List[float],
                 volumes: List[float]) -> Dict[str, Any]:
    """Runs the full technical indicator suite."""
    sma_20 = _sma(closes, 20)
    sma_50 = _sma(closes, 50)
    ema_12 = _ema(closes, 12)
    ema_26 = _ema(closes, 26)
    rsi_14 = _rsi(closes, 14)
    std_20 = _std_dev(closes, 20)

    # MACD
    macd_line = []
    for i in range(len(closes)):
        if ema_12[i] is not None and ema_26[i] is not None:
            macd_line.append(ema_12[i] - ema_26[i])
        else:
            macd_line.append(None)
    macd_signal = _ema([m for m in macd_line if m is not None], 9) if any(m is not None for m in macd_line) else []
    # Re-align MACD signal to macd_line length (simple forward-fill for blueprint)
    aligned_signal = [None] * len(closes)
    sig_idx = 0
    for i in range(len(closes)):
        if macd_line[i] is not None:
            if sig_idx < len(macd_signal) and macd_signal[sig_idx] is not None:
                aligned_signal[i] = macd_signal[sig_idx]
                sig_idx += 1
            elif sig_idx > 0:
                aligned_signal[i] = macd_signal[sig_idx - 1]

    # Bollinger Bands
    bb_upper, bb_middle, bb_lower = [], [], []
    for i in range(len(closes)):
        if sma_20[i] is not None and std_20[i] is not None:
            bb_middle.append(sma_20[i])
            bb_upper.append(sma_20[i] + 2 * std_20[i])
            bb_lower.append(sma_20[i] - 2 * std_20[i])
        else:
            bb_upper.append(None)
            bb_middle.append(None)
            bb_lower.append(None)

    # Support / Resistance
    support, resistance = _support_resistance(lows, highs, 20)

    # Volatility (annualized based on daily std)
    if std_20[-1] is not None and sma_20[-1] is not None and sma_20[-1] != 0:
        volatility = (std_20[-1] / sma_20[-1]) * math.sqrt(252) * 100
    else:
        volatility = 0.0

    return {
        "sma_20": sma_20,
        "sma_50": sma_50,
        "ema_12": ema_12,
        "ema_26": ema_26,
        "macd": macd_line,
        "macd_signal": aligned_signal,
        "rsi_14": rsi_14,
        "bb_upper": bb_upper,
        "bb_middle": bb_middle,
        "bb_lower": bb_lower,
        "volatility": volatility,
        "support": support,
        "resistance": resistance,
    }


def _generate_signal_and_prediction(
    close: float,
    prev_close: float,
    indicators: Dict[str, Any],
    closes: List[float],
) -> Tuple[str, float, str, float, float, str]:
    """
    Generates signal, confidence, direction, 5d low/high, summary.
    Uses a weighted scoring system (0-100).
    """
    score = 50  # Neutral baseline
    reasons = []

    sma_20_last = indicators["sma_20"][-1]
    sma_50_last = indicators["sma_50"][-1]
    rsi = indicators["rsi_14"][-1]
    macd = indicators["macd"][-1]
    macd_sig = indicators["macd_signal"][-1]
    bb_up = indicators["bb_upper"][-1]
    bb_low = indicators["bb_lower"][-1]

    # 1. SMA Crossover (Golden/Death Cross)
    if sma_20_last is not None and sma_50_last is not None:
        if sma_20_last > sma_50_last:
            score += 10
            reasons.append("SMA20 > SMA50 (bullish bias)")
        else:
            score -= 10
            reasons.append("SMA20 < SMA50 (bearish bias)")

    # 2. RSI
    if rsi is not None:
        if rsi < 30:
            score += 15
            reasons.append(f"RSI oversold ({rsi:.1f})")
        elif rsi > 70:
            score -= 15
            reasons.append(f"RSI overbought ({rsi:.1f})")
        elif 40 <= rsi <= 60:
            reasons.append(f"RSI neutral ({rsi:.1f})")
        else:
            if rsi < 45:
                score += 5
            else:
                score -= 5

    # 3. MACD
    if macd is not None and macd_sig is not None:
        if macd > macd_sig:
            score += 10
            reasons.append("MACD above signal")
        else:
            score -= 10
            reasons.append("MACD below signal")

    # 4. Bollinger Position
    if bb_up is not None and bb_low is not None:
        if close >= bb_up:
            score -= 10
            reasons.append("Price at upper Bollinger (potential reversal)")
        elif close <= bb_low:
            score += 10
            reasons.append("Price at lower Bollinger (potential bounce)")

    # 5. Price vs Support/Resistance
    sup = indicators["support"]
    res = indicators["resistance"]
    dist_to_sup = ((close - sup) / close) * 100 if close else 0
    dist_to_res = ((res - close) / close) * 100 if close else 0
    if dist_to_sup < 2:
        score += 8
        reasons.append("Price near support")
    if dist_to_res < 2:
        score -= 8
        reasons.append("Price near resistance")

    # Clamp score
    score = max(0, min(100, score))

    # Signal classification
    if score >= 65:
        signal = "BUY"
    elif score <= 35:
        signal = "SELL"
    elif 45 <= score <= 55:
        signal = "NEUTRAL"
    else:
        signal = "HOLD"

    # Confidence = distance from 50
    confidence = abs(score - 50) / 50.0

    # Prediction via linear regression slope on last 10 closes
    slope = _linear_regression_slope(closes, 10)
    if slope > 0.01 * close:
        direction = "BULLISH"
    elif slope < -0.01 * close:
        direction = "BEARISH"
    else:
        direction = "SIDEWAYS"

    # 5-day projection: slope * 5 ± 1 ATR (use std dev as proxy)
    recent_std = indicators["bb_upper"][-1] - indicators["bb_middle"][-1] if indicators["bb_upper"][-1] else close * 0.02
    projected = close + slope * 5
    pred_low = projected - recent_std
    pred_high = projected + recent_std

    summary = (
        f"Signal: {signal} (confidence {confidence:.0%}). "
        f"Direction: {direction}. "
        + " | ".join(reasons)
    )

    return signal, confidence, direction, pred_low, pred_high, summary


# ── PUBLIC API ───────────────────────────────────────────────
async def analyze_stock(ticker: str, range_period: str = DEFAULT_RANGE) -> Dict[str, Any]:
    """
    Fetches and analyzes a single stock ticker.

    Args:
        ticker (str): Yahoo Finance ticker (e.g., 'RELIANCE.NS', 'AAPL', 'BTC-USD').
        range_period (str): Data range (1d, 5d, 1mo, 3mo, 6mo, 1y, 5y).

    Returns:
        Dict: Full analysis payload or error dict.
    """
    print(f"[MARKET ANALYZER] === ANALYZING {ticker} ===")

    raw = await _fetch_json(ticker, range_period)
    if raw is None:
        return {"error": f"Failed to fetch data for {ticker}. Check ticker symbol or network."}

    data = _parse_ohlcv(raw)
    if data is None:
        return {"error": f"Failed to parse OHLCV for {ticker}."}

    closes = data["close"]
    lows = data["low"]
    highs = data["high"]
    volumes = data["volume"]

    if len(closes) < 50:
        return {"error": f"Insufficient data points ({len(closes)}) for {ticker}. Need >= 50."}

    indicators = _compute_all(closes, lows, highs, volumes)

    current = data["regularMarketPrice"] if data["regularMarketPrice"] is not None else closes[-1]
    prev = data["previousClose"] if data["previousClose"] is not None else closes[-2]
    change = current - prev
    change_pct = (change / prev * 100) if prev else 0.0
    vol = data["regularMarketVolume"] if data["regularMarketVolume"] is not None else volumes[-1]

    signal, confidence, direction, pred_low, pred_high, summary = _generate_signal_and_prediction(
        current, prev, indicators, closes
    )

    snapshot = TechnicalSnapshot(
        ticker=ticker.upper(),
        timestamp=datetime.utcnow().isoformat() + "Z",
        current_price=round(current, 2),
        prev_close=round(prev, 2),
        change=round(change, 2),
        change_percent=round(change_pct, 2),
        volume=int(vol),
        sma_20=round(indicators["sma_20"][-1], 2) if indicators["sma_20"][-1] else 0.0,
        sma_50=round(indicators["sma_50"][-1], 2) if indicators["sma_50"][-1] else 0.0,
        ema_12=round(indicators["ema_12"][-1], 2) if indicators["ema_12"][-1] else 0.0,
        ema_26=round(indicators["ema_26"][-1], 2) if indicators["ema_26"][-1] else 0.0,
        macd=round(indicators["macd"][-1], 4) if indicators["macd"][-1] else 0.0,
        macd_signal=round(indicators["macd_signal"][-1], 4) if indicators["macd_signal"][-1] else 0.0,
        rsi_14=round(indicators["rsi_14"][-1], 2) if indicators["rsi_14"][-1] else 0.0,
        bb_upper=round(indicators["bb_upper"][-1], 2) if indicators["bb_upper"][-1] else 0.0,
        bb_middle=round(indicators["bb_middle"][-1], 2) if indicators["bb_middle"][-1] else 0.0,
        bb_lower=round(indicators["bb_lower"][-1], 2) if indicators["bb_lower"][-1] else 0.0,
        volatility=round(indicators["volatility"], 2),
        support=round(indicators["support"], 2),
        resistance=round(indicators["resistance"], 2),
        signal=signal,
        confidence=round(confidence, 2),
        prediction_5d_low=round(pred_low, 2),
        prediction_5d_high=round(pred_high, 2),
        prediction_direction=direction,
        analysis_summary=summary,
    )

    result = asdict(snapshot)
    print(f"[MARKET ANALYZER] {ticker} → {signal} @ {confidence:.0%} confidence. {direction}.")
    return result


async def compare_stocks(tickers: List[str], range_period: str = DEFAULT_RANGE) -> List[Dict[str, Any]]:
    """
    Batch analysis for multiple tickers.
    Returns a list of analysis dicts.
    """
    print(f"[MARKET ANALYZER] Batch comparing {len(tickers)} tickers.")
    tasks = [analyze_stock(t, range_period) for t in tickers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    output = []
    for t, r in zip(tickers, results):
        if isinstance(r, Exception):
            output.append({"ticker": t, "error": str(r)})
        else:
            output.append(r)
    return output


# ── STAGE 2: TEST CASE ─────────────────────────────────────
if __name__ == "__main__":
    # Demo: Analyze a blue-chip and a crypto asset
    demo_tickers = ["AAPL", "BTC-USD"]
    for sym in demo_tickers:
        out = asyncio.run(analyze_stock(sym, "3mo"))
        print(json.dumps(out, indent=2))
        print("-" * 60)
