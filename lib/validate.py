"""Gaps, duplicados, consistencia OHLC. Nada de timezone/outlier todavía —
eso es un chequeo manual hasta que haga falta más.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class ValidationReport:
    n_rows: int
    n_duplicates: int
    n_gaps: int
    gap_minutes_total: float
    n_ohlc_violations: int
    blocking: bool
    gap_details: pd.DataFrame = field(repr=False)
    ohlc_violation_details: pd.DataFrame = field(repr=False)

    def summary(self) -> str:
        lines = [
            f"Filas: {self.n_rows}",
            f"Duplicados (timestamp repetido): {self.n_duplicates}",
            f"Gaps detectados: {self.n_gaps} (total {self.gap_minutes_total:.0f} min faltantes, "
            f"{100 * self.gap_minutes_total / max(self.n_rows, 1):.3f}% del histórico)",
            f"Violaciones de consistencia OHLC: {self.n_ohlc_violations}",
            f"Estado: {'BLOQUEANTE — no continuar sin resolver' if self.blocking else 'OK, apto para continuar'}",
        ]
        return "\n".join(lines)


def validate(df: pd.DataFrame, interval_minutes: int = 1) -> ValidationReport:
    n_rows = len(df)

    # 1. Duplicados por timestamp
    dup_mask = df.duplicated(subset=["open_time"], keep=False)
    n_duplicates = int(dup_mask.sum())

    # 2. Gaps respecto a la grilla temporal esperada — indexado posicional (numpy),
    # nunca alineación por label, para evitar desalineces de índice tras sort/diff.
    df_sorted = df.sort_values("open_time").reset_index(drop=True)
    # to_numpy() sobre datetime64 tz-aware da un array de objetos Timestamp;
    # se despoja el timezone (ya normalizado a UTC en ingest.py) para operar
    # con datetime64[ns] nativo y poder restar contra timedelta64.
    times = df_sorted["open_time"].dt.tz_localize(None).to_numpy()
    expected_step = np.timedelta64(interval_minutes, "m")
    actual_steps = times[1:] - times[:-1]  # longitud n-1
    gap_mask = actual_steps > expected_step
    n_gaps = int(gap_mask.sum())
    missing = (actual_steps[gap_mask] - expected_step) / np.timedelta64(1, "m")
    gap_minutes_total = float(missing.sum())
    gap_details = pd.DataFrame({
        "gap_start": times[:-1][gap_mask],
        "gap_end": times[1:][gap_mask],
        "missing_minutes": missing,
    }).reset_index(drop=True)

    # 3. Consistencia OHLC
    high_bad = df["high"] < df[["open", "close", "low"]].max(axis=1)
    low_bad = df["low"] > df[["open", "close", "high"]].min(axis=1)
    vol_bad = df["volume"] < 0
    ohlc_bad_mask = high_bad | low_bad | vol_bad
    n_ohlc_violations = int(ohlc_bad_mask.sum())
    ohlc_violation_details = df.loc[ohlc_bad_mask, ["open_time", "open", "high", "low", "close", "volume"]]

    blocking = n_duplicates > 0 or n_ohlc_violations > 0

    return ValidationReport(
        n_rows=n_rows,
        n_duplicates=n_duplicates,
        n_gaps=n_gaps,
        gap_minutes_total=gap_minutes_total,
        n_ohlc_violations=n_ohlc_violations,
        blocking=blocking,
        gap_details=gap_details,
        ohlc_violation_details=ohlc_violation_details,
    )
