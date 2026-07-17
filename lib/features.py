"""Construcción de velas de 5m y sus features de microestructura/supervivencia.

Nota de resolución: Binance solo da klines a resolución de 1 minuto vía
REST sin costo adicional, así que los instantes de supervivencia T se
miden en marcas de minuto: T ∈ {60,120,180,240,300}s, un punto por cada
sub-vela de 1m, no cada 30s.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def build_5m_candles(df_1m: pd.DataFrame) -> pd.DataFrame:
    """Agrega velas de 1m en velas de 5m, conservando las 5 sub-velas.

    Solo conserva buckets de 5 minutos con exactamente 5 sub-velas de 1m
    (sin gaps internos) — un bucket incompleto no permite reconstruir la
    trayectoria y se descarta explícitamente en vez de rellenarse.
    """
    df = df_1m.sort_values("open_time").reset_index(drop=True).copy()
    df["bucket"] = df["open_time"].dt.floor("5min")
    sizes = df.groupby("bucket")["open_time"].transform("size")
    df_clean = df[sizes == 5].sort_values(["bucket", "open_time"]).reset_index(drop=True)
    n = len(df_clean) // 5
    df_clean = df_clean.iloc[: n * 5]

    def reshaped(col):
        return df_clean[col].to_numpy().reshape(n, 5)

    opens, highs, lows, closes = reshaped("open"), reshaped("high"), reshaped("low"), reshaped("close")
    volumes = reshaped("volume")
    taker_buy = reshaped("taker_buy_base_volume")
    num_trades = reshaped("num_trades")
    buckets = df_clean["bucket"].to_numpy().reshape(n, 5)[:, 0]

    out = pd.DataFrame({
        "open_time": buckets,
        "open": opens[:, 0],
        "high": highs.max(axis=1),
        "low": lows.min(axis=1),
        "close": closes[:, -1],
        "volume": volumes.sum(axis=1),
        "taker_buy_base_volume": taker_buy.sum(axis=1),
        "num_trades": num_trades.sum(axis=1),
    })
    out.attrs["sub_opens"] = opens
    out.attrs["sub_closes"] = closes
    n_dropped = len(df_1m) - n * 5
    print(f"  [features] {n} velas de 5m construidas con las 5 sub-velas intactas "
          f"({n_dropped} filas de 1m descartadas por buckets incompletos)")
    return out


def _sign(x: np.ndarray) -> np.ndarray:
    return np.sign(x)


def _run_length_max(signs_row: np.ndarray) -> int:
    best = cur = 1
    for i in range(1, len(signs_row)):
        if signs_row[i] == signs_row[i - 1]:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    return best


def _color_sequence(signs_row: np.ndarray) -> str:
    m = {1: "G", -1: "R", 0: "F"}
    return "".join(m[s] for s in signs_row)


def _time_to_lock(signs_incl_close: np.ndarray) -> int:
    """Segundos (marca de minuto) a partir de los cuales el signo ya no cambia."""
    final_sign = signs_incl_close[-1]
    idx_last_diff = -1
    for i in range(len(signs_incl_close)):
        if signs_incl_close[i] != final_sign:
            idx_last_diff = i
    lock_index = idx_last_diff + 1  # primer índice que ya coincide con el final, de forma sostenida
    return int((lock_index + 1) * 60)  # +1 porque el índice 0 corresponde al minuto 1 (t=60s)


def compute_features(df_5m: pd.DataFrame) -> pd.DataFrame:
    out = df_5m.copy()
    sub_opens = df_5m.attrs["sub_opens"]
    sub_closes = df_5m.attrs["sub_closes"]
    n = len(out)

    open_col = out["open"].to_numpy().reshape(n, 1)
    levels = np.concatenate([open_col, sub_closes], axis=1)  # (n, 6): open, c1..c5
    step_moves = np.diff(levels, axis=1)  # (n, 5)
    signs = _sign(step_moves)  # signo de cada uno de los 5 pasos internos

    total_path_distance = np.abs(step_moves).sum(axis=1)
    net_displacement = np.abs(out["close"].to_numpy() - out["open"].to_numpy())
    with np.errstate(divide="ignore", invalid="ignore"):
        path_efficiency = np.where(total_path_distance > 0, net_displacement / total_path_distance, 0.0)

    with np.errstate(divide="ignore", invalid="ignore"):
        subbar_returns = np.log(levels[:, 1:] / levels[:, :-1])
    realized_vol_intracandle = np.nanstd(subbar_returns, axis=1, ddof=1)

    high = out["high"].to_numpy()
    low = out["low"].to_numpy()
    midpoint = (high + low) / 2
    occupation_upper = (sub_closes > midpoint.reshape(n, 1)).mean(axis=1)

    num_direction_changes = (np.diff(signs, axis=1) != 0).sum(axis=1)
    run_length_max = np.array([_run_length_max(row) for row in signs])
    color_sequence = np.array([_color_sequence(row) for row in signs])

    rng = np.where((high - low) > 0, (out["close"].to_numpy() - low) / (high - low), 0.5)

    volume = out["volume"].to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        taker_buy_ratio = np.where(volume > 0, out["taker_buy_base_volume"].to_numpy() / volume, np.nan)

    prev_close = out["close"].shift(1).to_numpy()
    true_range = np.maximum.reduce([
        high - low,
        np.abs(high - prev_close),
        np.abs(low - prev_close),
    ])
    atr_14 = pd.Series(true_range).rolling(14, min_periods=14).mean().to_numpy()

    # supervivencia: signo de (precio - open) en cada marca de minuto, incluido el cierre
    signs_vs_open_incl_close = _sign(sub_closes - open_col)  # (n,5): T=60..300s
    time_to_lock = np.array([_time_to_lock(row) for row in signs_vs_open_incl_close])
    time_above_open_sec = (signs_vs_open_incl_close > 0).sum(axis=1) * 60
    time_below_open_sec = (signs_vs_open_incl_close < 0).sum(axis=1) * 60

    out["path_efficiency_ratio"] = path_efficiency
    out["total_path_distance"] = total_path_distance
    out["occupation_time_upper_half"] = occupation_upper
    out["num_direction_changes"] = num_direction_changes
    out["run_length_max"] = run_length_max
    out["color_sequence_5tuple"] = color_sequence
    out["close_position_in_range"] = rng
    out["taker_buy_ratio"] = taker_buy_ratio
    out["atr_14"] = atr_14
    out["realized_vol_1m_intracandle"] = realized_vol_intracandle
    out["time_to_color_lock_sec"] = time_to_lock
    out["time_above_open_sec"] = time_above_open_sec
    out["time_below_open_sec"] = time_below_open_sec

    # estados de supervivencia por marca T, en formato ancho (se usan directo en 001_survival)
    for i, t in enumerate([60, 120, 180, 240, 300]):
        out[f"side_at_{t}s"] = signs_vs_open_incl_close[:, i]

    out["y_color_next"] = (out["close"] > out["open"]).astype(int)
    return out
