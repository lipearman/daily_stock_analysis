#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bitkub crypto analyzer — Thai decision-dashboard reports for Bitkub pairs.

Data pipeline (per symbol, e.g. THB_BTC):
  1. Bitkub public ticker  -> local THB price, 24h change, THB volume
  2. Bitkub daily history  -> OHLCV in THB from Bitkub itself (primary source,
     no geo-block, no API key); Binance klines (USD) and Coingecko are
     fallbacks for symbols Bitkub does not chart
  3. Technical indicators  -> MA5/10/20/50, RSI(14), MACD(12,26,9), Bollinger(20,2), ATR(14)
  4. LLM (optional)        -> Thai decision dashboard via any OpenAI-compatible channel
                              (default: local Ollama; set BITKUB_LLM_* to use another)
  5. Telegram (optional)   -> send the Thai report (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID)

Prices: when candles come from Bitkub they are already in THB (no conversion).
For USD fallback candles, all displayed levels are converted to THB using the
implied THB/USDT rate from Bitkub's local price.

Usage:
  python scripts/bitkub_crypto_analyzer.py --symbols THB_BTC,THB_ETH
  python scripts/bitkub_crypto_analyzer.py --no-llm --no-telegram
  python scripts/bitkub_crypto_analyzer.py --json
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

import httpx

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, "buffer") else sys.stdout

ROOT = Path(__file__).resolve().parent.parent
TH_TZ = timezone(timedelta(hours=7))

BITKUB_BASE = "https://api.bitkub.com"
BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
COINGECKO_OHLC = "https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc?vs_currency=usd&days={days}"
COINGECKO_IDS = {
    "THB_BTC": "bitcoin",
    "THB_ETH": "ethereum",
    "THB_KUB": "bitkub-coin",
    "THB_XRP": "ripple",
    "THB_SOL": "solana",
    "THB_DOGE": "dogecoin",
    "THB_ADA": "cardano",
    "THB_GAS": "gas",
    "THB_JFIN": "jfin-chain",
}

DEFAULT_SYMBOLS = "THB_BTC,THB_ETH,THB_KUB"
DEFAULT_LLM_BASE = "http://llm-server:11434/v1"
DEFAULT_LLM_MODEL = "typhoon-thai:latest"

# Symbols whose Binance pair is not simply <base>USDT
SYMBOL_MAP_OVERRIDES = {"THB_KUB": "KUBUSDT"}


def load_env() -> None:
    env_file = ROOT / ".env"
    if env_file.exists():
        from dotenv import load_dotenv

        load_dotenv(env_file, override=False)


def http_get_json(url: str, timeout: int = 30) -> Any:
    resp = httpx.get(url, timeout=timeout, headers={"User-Agent": "dsa-bitkub-analyzer/1.0"})
    resp.raise_for_status()
    return resp.json()


def http_post_json(url: str, payload: dict, timeout: int = 600) -> Any:
    api_key = os.getenv("LLM_API_KEY", "") or os.getenv("LLM_OPENAI_API_KEY", "")
    resp = httpx.post(
        url,
        headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# data layer
# ---------------------------------------------------------------------------

def bitkub_tickers(symbols: list[str]) -> dict[str, dict]:
    """Fetch Bitkub tickers (single request) and filter to wanted pairs."""
    raw = http_get_json(f"{BITKUB_BASE}/api/market/ticker")
    want = {s.upper() for s in symbols}
    return {k: v for k, v in raw.items() if k.upper() in want}


def fetch_bitkub_history(symbol: str, limit: int = 100) -> list[dict]:
    """Daily OHLCV in THB straight from Bitkub's TradingView history endpoint.

    Works from any region (no geo-block, no API key) and reflects Bitkub's own
    THB market, so no FX conversion is needed."""
    base = symbol.split("_")[1].upper()
    now = int(time.time())
    frm = now - limit * 86400
    raw = http_get_json(
        f"{BITKUB_BASE}/tradingview/history?symbol={base}_THB&resolution=D&from={frm}&to={now}",
        timeout=30,
    )
    stamps = raw.get("t") or []
    if not stamps:
        raise RuntimeError(f"bitkub history empty for {symbol}: {str(raw)[:120]}")
    volumes = raw.get("v") or [0.0] * len(stamps)
    candles = [
        {
            "ts": int(t) * 1000,
            "o": float(o),
            "h": float(h),
            "l": float(l),
            "c": float(c),
            "v": float(v),
        }
        for t, o, h, l, c, v in zip(stamps, raw["o"], raw["h"], raw["l"], raw["c"], volumes)
    ]
    return candles


def fetch_ohlcv(symbol: str, interval: str = "1d", limit: int = 100) -> tuple[list[dict], str]:
    """OHLCV candles for the symbol's base asset.

    Source order: Bitkub THB history (no geo-block) -> Binance USD klines ->
    Coingecko USD daily aggregation.

    Returns (ascending candles {ts, o, h, l, c, v}, currency)."""
    try:
        return fetch_bitkub_history(symbol, limit=limit), "THB"
    except Exception as exc:
        print(f"  [warn] Bitkub history failed for {symbol}: {exc} -- trying Binance")

    binance_symbol = SYMBOL_MAP_OVERRIDES.get(symbol.upper(), f"{symbol.split('_')[1].upper()}USDT")
    try:
        raw = http_get_json(
            f"{BINANCE_KLINES}?symbol={binance_symbol}&interval={interval}&limit={limit}", timeout=30
        )
        candles = []
        for row in raw:
            candles.append(
                {
                    "ts": row[0],
                    "o": float(row[1]),
                    "h": float(row[2]),
                    "l": float(row[3]),
                    "c": float(row[4]),
                    "v": float(row[5]),
                }
            )
        return candles, "USD"
    except Exception as exc:
        print(f"  [warn] Binance klines failed for {symbol}: {exc} -- trying Coingecko")

    coin_id = COINGECKO_IDS.get(symbol.upper())
    if not coin_id:
        coin_id = symbol.split("_")[1].lower()
    # Coingecko market_chart gives hourly prices for days<=90 — aggregate them
    # into daily candles ourselves (o/c = day open/close, h/l = day extremes)
    days = 90 if interval == "1d" else 2
    raw = None
    for attempt in range(2):  # public tier sometimes answers 429 — retry once
        try:
            raw = http_get_json(
                f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days={days}",
                timeout=30,
            )
            break
        except Exception as exc:
            if attempt == 0:
                print(f"  [warn] Coingecko attempt 1 failed ({exc}) -- retrying in 6s")
                time.sleep(6)
            else:
                raise
    prices = raw.get("prices", [])
    volumes = raw.get("total_volumes", [])
    if not prices:
        return [], "USD"
    candles: list[dict] = []
    current_day: Optional[str] = None
    day_open = day_high = day_low = None
    day_volume = 0.0
    for point in prices:
        ts = point[0]
        price = float(point[1])
        day = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        if current_day is None:
            current_day = day
            day_open = price
            day_high = price
            day_low = price
        elif day != current_day:
            candles.append(
                {
                    "ts": int(datetime.fromisoformat(current_day).replace(tzinfo=timezone.utc).timestamp() * 1000),
                    "o": day_open,
                    "h": day_high,
                    "l": day_low,
                    "c": price,
                    "v": day_volume,
                }
            )
            current_day = day
            day_open = price
            day_high = price
            day_low = price
        day_high = max(day_high, price)
        day_low = min(day_low, price)
    if current_day is not None:
        candles.append(
            {
                "ts": int(datetime.fromisoformat(current_day).replace(tzinfo=timezone.utc).timestamp() * 1000),
                "o": day_open,
                "h": day_high,
                "l": day_low,
                "c": prices[-1][1],
                "v": day_volume,
            }
        )
    vol_by_day = {}
    for ts, vol in volumes:
        day = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        vol_by_day[day] = float(vol)
    for candle in candles:
        day = datetime.fromtimestamp(candle["ts"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        candle["v"] = vol_by_day.get(day, 0.0)
    return candles, "USD"


# ---------------------------------------------------------------------------
# indicators (pure python)
# ---------------------------------------------------------------------------

def sma(values: list[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def ema_series(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    k = 2 / (period + 1)
    series = [values[0]]
    for v in values[1:]:
        series.append(v * k + series[-1] * (1 - k))
    return series


def rsi(closes: list[float], period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def macd(closes: list[float]) -> tuple[Optional[float], Optional[float], Optional[float]]:
    if len(closes) < 35:
        return None, None, None
    ema12 = ema_series(closes, 12)
    ema26 = ema_series(closes, 26)
    macd_line = [a - b for a, b in zip(ema12, ema26)]
    signal = ema_series(macd_line, 9)
    hist = macd_line[-1] - signal[-1]
    return macd_line[-1], signal[-1], hist


def bollinger(closes: list[float], period: int = 20, mult: float = 2.0) -> tuple[Optional[float], Optional[float], Optional[float]]:
    if len(closes) < period:
        return None, None, None
    mid = sma(closes, period)
    window = closes[-period:]
    variance = sum((c - mid) ** 2 for c in window) / period
    sd = variance ** 0.5
    return mid - mult * sd, mid, mid + mult * sd


def atr(candles: list[dict], period: int = 14) -> Optional[float]:
    if len(candles) < period + 1:
        return None
    trs = []
    for i in range(1, len(candles)):
        high, low, prev_close = candles[i]["h"], candles[i]["l"], candles[i - 1]["c"]
        trs.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return sum(trs[-period:]) / period


def analyze_technicals(candles: list[dict]) -> dict:
    closes = [c["c"] for c in candles]
    last = closes[-1]
    prev = closes[-2] if len(closes) > 1 else last
    macd_line, macd_signal, macd_hist = macd(closes)
    bb_lower, bb_mid, bb_upper = bollinger(closes)
    rsi_value = rsi(closes)
    atr_value = atr(candles)
    vol_now = candles[-1]["v"]
    vol_avg = sum(c["v"] for c in candles[-10:-1]) / max(1, len(candles[-10:-1]))

    score = 50
    notes = []
    if last > (sma(closes, 20) or 0):
        score += 10
        notes.append("ราคาเหนือ MA20")
    else:
        score -= 10
        notes.append("ราคาใต้ MA20")
    if macd_hist is not None:
        if macd_hist > 0:
            score += 10
            notes.append("MACD histogram เป็นบวก")
        else:
            score -= 10
            notes.append("MACD histogram เป็นลบ")
    if rsi_value is not None:
        if rsi_value >= 70:
            score -= 5
            notes.append(f"RSI {rsi_value:.0f} เข้าเขต overbought")
        elif rsi_value <= 30:
            score += 5
            notes.append(f"RSI {rsi_value:.0f} เข้าเขต oversold")
        else:
            notes.append(f"RSI {rsi_value:.0f} เป็นกลาง")
    if bb_upper and last >= bb_upper:
        score -= 5
        notes.append("ราคาแตะ Bollinger upper")
    if vol_avg and vol_now > vol_avg * 1.5:
        score += 5
        notes.append("วอลุ่มพุ่งเกินค่าเฉลี่ย 10 แท่ง")

    trend = "ขาขึ้น" if score >= 60 else "ขาลง" if score <= 40 else "ออกข้าง"
    advice = "ถือ/เฝ้าดู" if 40 < score < 60 else "พิจารณาซื้อทีละส่วน" if score >= 60 else "ระวังฝั่งขาย"
    return {
        "last_usd": last,
        "prev_usd": prev,
        "ma20": sma(closes, 20),
        "ma50": sma(closes, 50),
        "rsi": rsi_value,
        "macd_hist": macd_hist,
        "bb_lower": bb_lower,
        "bb_upper": bb_upper,
        "atr": atr_value,
        "score": max(0, min(100, score)),
        "trend": trend,
        "advice": advice,
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def fmt_thb(value: Optional[float]) -> str:
    if value is None:
        return "-"
    if value >= 1000:
        return f"{value:,.0f}"
    return f"{value:,.2f}"


def build_technical_report(symbol: str, ticker: dict, tech: dict, rate: float, currency: str = "USD") -> str:
    last_thb = ticker.get("last", 0)
    change24 = ticker.get("percentChange", 0)
    vol_thb = ticker.get("quoteVolume", 0)
    last_usd = tech["last_usd"]

    entry = tech["ma20"]
    stop = last_usd - 1.5 * (tech["atr"] or 0)
    target = last_usd + 2.0 * (tech["atr"] or 0)
    conv = rate or 1.0
    source_note = (
        "ข้อมูลเทคนิคจากกราฟรายวันของ Bitkub (หน่วยบาท) โดยตรง"
        if currency == "THB"
        else "ข้อมูลเทคนิคจากตลาด global (USD) แปลงเป็นบาทด้วยอัตราโดยปริมาณจากราคา Bitkub"
    )
    plan_heading = (
        "**แผนอ้างอิงระดับราคา (บาท):**"
        if currency == "THB"
        else "**แผนอ้างอิง (แปลงเป็นบาทจากราคา global):**"
    )

    lines = [
        f"📊 **รายงานคริปโต {symbol} (Bitkub)**",
        f"🕒 {datetime.now(TH_TZ).strftime('%d/%m/%Y %H:%M')} น. (เวลาไทย)",
        "",
        f"**ราคาล่าสุด (Bitkub):** {fmt_thb(last_thb)} บาท  |  24ชม.: {change24:+.2f}%",
        f"**วอลุ่ม 24ชม. (THB):** {fmt_thb(vol_thb)}",
        "",
        f"**คะแนนเทคนิค:** {tech['score']}/100 — {tech['trend']} — {tech['advice']}",
        "",
        "**สัญญาณเทคนิค:**",
    ]
    lines += [f"- {note}" for note in tech["notes"]]
    lines += [
        "",
        f"**MA20:** {fmt_thb(tech['ma20'] * conv)} บาท | **MA50:** {fmt_thb(tech['ma50'] * conv)} บาท",
        f"**Bollinger:** {fmt_thb(tech['bb_lower'] * conv)} — {fmt_thb(tech['bb_upper'] * conv)} บาท",
        "",
        plan_heading,
        f"- จุดเข้าอ้างอิง: {fmt_thb(entry * conv)} บาท",
        f"- จุดตัดขาดทุน: {fmt_thb(stop * conv)} บาท",
        f"- จุดทำกำไรเป้าหมาย: {fmt_thb(target * conv)} บาท",
        "",
        source_note,
        "⚠️ AI/เทคนิควิเคราะห์เพื่ออ้างอิงเท่านั้น ไม่ใช่คำแนะนำการลงทุน",
    ]
    return "\n".join(lines)


LLM_PROMPT = """คุณเป็นนักวิเคราะห์คริปโตมืออาชีพ วิเคราะห์ข้อมูลต่อไปนี้ของ {symbol} (ตลาด Bitkub หน่วยบาท)
และเขียนรายงานตัดสินใจภาษาไทย โครงสร้าง:

📊 รายงานคริปโต {symbol} (Bitkub)
- สรุปหนึ่งบรรทัด
- คะแนน 0-100 และแนวโน้ม (ขาขึ้น/ขาลง/ออกข้าง)
- สัญญาณเทคนิคสำคัญ 3-5 ข้อ
- จุดเข้า / จุดตัดขาดทุน / เป้าหมาย (หน่วยบาท)
- ความเสี่ยงที่ต้องเฝ้าดู 3 ข้อ
- ปิดท้าย: ข้อความว่าเป็นการวิเคราะห์อ้างอิง ไม่ใช่คำแนะนำการลงทุน

ข้อมูล:
{data}
"""


def build_llm_report(symbol: str, ticker: dict, tech: dict, rate: float, currency: str = "USD") -> Optional[str]:
    base_url = os.getenv("BITKUB_LLM_BASE_URL", DEFAULT_LLM_BASE).rstrip("/")
    model = os.getenv("BITKUB_LLM_MODEL", DEFAULT_LLM_MODEL)
    data = json.dumps(
        {
            "bitkub_thb_last": ticker.get("last"),
            "change_24h_pct": ticker.get("percentChange"),
            "quote_volume_thb": ticker.get("quoteVolume"),
            "candle_currency": currency,
            "fx_rate_applied": rate,
            "technical": {k: v for k, v in tech.items() if k != "notes"},
            "signals": tech["notes"],
        },
        ensure_ascii=False,
        default=str,
    )
    payload = {
        "model": model,
        "max_tokens": 2000,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": "คุณเป็นนักวิเคราะห์คริปโต ตอบเป็นภาษาไทยเสมอ กระชับและมีโครงสร้างชัดเจน"},
            {"role": "user", "content": LLM_PROMPT.format(symbol=symbol, data=data)},
        ],
    }
    try:
        body = http_post_json(f"{base_url}/chat/completions", payload)
        content = body["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(block.get("text", "") for block in content if isinstance(block, dict))
        return content.strip() or None
    except Exception as exc:
        print(f"  [warn] LLM report failed: {exc} -- falling back to technical report")
        return None


def send_telegram(text: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not (token and chat_id):
        print("  [skip] Telegram ยังไม่ได้ตั้งค่า (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID)")
        return False
    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4000], "parse_mode": "Markdown"},
            timeout=30,
        )
        return resp.json().get("ok", False)
    except Exception as exc:
        print(f"  [warn] Telegram send failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def implied_thb_rate(ticker: dict, last_usd: float) -> float:
    bitkub_last = ticker.get("last") or 0
    if bitkub_last > 0 and last_usd > 0:
        return bitkub_last / last_usd
    return 1.0


def analyze_symbol(symbol: str, use_llm: bool, use_telegram: bool, as_json: bool) -> str:
    print(f"▶ {symbol}")
    tickers = bitkub_tickers([symbol])
    ticker = tickers.get(symbol.upper())
    if not ticker:
        return f"❌ {symbol}: ไม่พบข้อมูล ticker บน Bitkub"

    candles, currency = fetch_ohlcv(symbol)
    if len(candles) < 35:
        return f"❌ {symbol}: ข้อมูลราคาไม่เพียงพอสำหรับวิเคราะห์"

    tech = analyze_technicals(candles)
    if currency == "THB":
        # Bitkub candles are already in THB — no FX conversion needed.
        rate = 1.0
    else:
        rate = implied_thb_rate(ticker, tech["last_usd"])

    report: Optional[str] = None
    if use_llm:
        report = build_llm_report(symbol, ticker, tech, rate, currency)
    if not report:
        report = build_technical_report(symbol, ticker, tech, rate, currency)

    if as_json:
        return json.dumps(
            {
                "symbol": symbol,
                "bitkub_thb": ticker.get("last"),
                "score": tech["score"],
                "trend": tech["trend"],
                "currency": currency,
                "rate_implied": round(rate, 4),
                "report": report,
            },
            ensure_ascii=False,
            indent=1,
        )

    print("  ✔ สร้างรายงานแล้ว")
    if use_telegram:
        if send_telegram(report):
            print("  ✔ ส่ง Telegram แล้ว")
    return report


def main() -> None:
    load_env()
    parser = argparse.ArgumentParser(description="Bitkub crypto analyzer (Thai reports)")
    parser.add_argument("--symbols", default=os.getenv("BITKUB_SYMBOLS", DEFAULT_SYMBOLS))
    parser.add_argument("--no-llm", action="store_true", help="technical-only report (no LLM)")
    parser.add_argument("--no-telegram", action="store_true", help="do not send to Telegram")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    reports = []
    for symbol in symbols:
        try:
            report = analyze_symbol(
                symbol,
                use_llm=not args.no_llm,
                use_telegram=False,  # sending happens once per symbol below or as digest
                as_json=args.json,
            )
            reports.append(report)
            print(report)
            print("\n" + "—" * 40 + "\n")
        except Exception as exc:
            reports.append(f"❌ {symbol}: วิเคราะห์ไม่สำเร็จ — {exc}")
            print(f"  [error] {exc}")

    if not args.no_telegram and not args.json and reports:
        digest = "\n\n———\n\n".join(reports)
        if send_telegram(digest):
            print("📤 ส่งรายงานรวมเข้า Telegram แล้ว")


if __name__ == "__main__":
    main()
