"""Descarga klines de Binance y los persiste en Parquet."""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import requests

BINANCE_BASE_URL = "https://api.binance.com"
KLINE_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_volume", "num_trades", "taker_buy_base_volume",
    "taker_buy_quote_volume", "_ignore",
]
NUMERIC_COLUMNS = [
    "open", "high", "low", "close", "volume", "quote_volume",
    "taker_buy_base_volume", "taker_buy_quote_volume",
]


def _fetch_page(symbol: str, interval: str, start_ms: int, end_ms: int, limit: int = 1000) -> list:
    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": limit,
    }
    for attempt in range(5):
        resp = requests.get(f"{BINANCE_BASE_URL}/api/v3/klines", params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code in (429, 418):
            wait = int(resp.headers.get("Retry-After", 5)) + attempt * 2
            time.sleep(wait)
            continue
        resp.raise_for_status()
    raise RuntimeError(f"No se pudo descargar tras 5 intentos: {resp.status_code} {resp.text[:200]}")


def download_klines(symbol: str, interval: str, start: pd.Timestamp, end: pd.Timestamp,
                     out_path: str | Path, sleep_s: float = 0.15) -> pd.DataFrame:
    """Descarga klines paginados de Binance y los escribe en Parquet, sin transformarlos."""
    interval_ms = {"1m": 60_000, "5m": 300_000}[interval]
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    all_rows: list = []
    cursor = start_ms
    page_span_ms = 1000 * interval_ms
    n_pages = (end_ms - start_ms) // page_span_ms + 1
    page = 0
    while cursor < end_ms:
        page_end = min(cursor + page_span_ms - 1, end_ms)
        rows = _fetch_page(symbol, interval, cursor, page_end, limit=1000)
        if not rows:
            cursor = page_end + 1
            page += 1
            continue
        all_rows.extend(rows)
        last_open_time = rows[-1][0]
        cursor = last_open_time + interval_ms
        page += 1
        if page % 20 == 0 or cursor >= end_ms:
            print(f"  [ingest] página {page}/{int(n_pages)+1} — {len(all_rows)} velas acumuladas "
                  f"(hasta {pd.to_datetime(last_open_time, unit='ms')})")
        time.sleep(sleep_s)

    df = pd.DataFrame(all_rows, columns=KLINE_COLUMNS).drop(columns=["_ignore"])
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    df[NUMERIC_COLUMNS] = df[NUMERIC_COLUMNS].astype("float64")
    df["num_trades"] = df["num_trades"].astype("int64")
    df["symbol"] = symbol
    df = df.drop_duplicates(subset=["open_time"]).sort_values("open_time").reset_index(drop=True)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    print(f"  [ingest] guardado: {out_path} — {len(df)} filas, "
          f"{df['open_time'].min()} → {df['open_time'].max()}")
    return df


if __name__ == "__main__":
    end = pd.Timestamp.utcnow().floor("min")
    start = end - pd.Timedelta(days=730)
    download_klines("BTCUSDT", "1m", start, end, "data/raw/BTCUSDT_1m.parquet")
