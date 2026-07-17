"""Motor estadístico mínimo — Wilson CI, benchmark de random walk, Monte Carlo.

Una curva de "supervivencia del color" ascendente con T aparece incluso
en un random walk puro, solo porque queda menos tiempo para que algo
cambie. El benchmark correcto no es 50% plano — es un random walk
simulado con la MISMA volatilidad realizada que los datos reales.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats


def wilson_ci(successes: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    if n == 0:
        return (np.nan, np.nan)
    lo, hi = scipy_stats.binomtest(int(successes), int(n)).proportion_ci(
        confidence_level=1 - alpha, method="wilson"
    )
    return float(lo), float(hi)


T_LIST = [60, 120, 180, 240, 300]


def survival_curve(df: pd.DataFrame, t_list: list[int] = T_LIST) -> pd.DataFrame:
    """P(el lado en T coincide con el color de cierre) por cada marca T, sobre datos reales."""
    final_sign = np.sign(df["close"].to_numpy() - df["open"].to_numpy())
    rows = []
    for t in t_list:
        side = df[f"side_at_{t}s"].to_numpy()
        if t == max(t_list):
            mask = np.ones(len(side), dtype=bool)
            same = np.ones(len(side), dtype=bool)
        else:
            mask = side != 0
            same = side[mask] == final_sign[mask]
        n = int(mask.sum())
        p_hat = float(same.mean()) if n > 0 else np.nan
        lo, hi = wilson_ci(int(same.sum()), n)
        rows.append({"T_seconds": t, "p_same_side_at_close": p_hat, "n": n, "ci_lo": lo, "ci_hi": hi})
    return pd.DataFrame(rows)


def simulate_random_walk_sides(sigma: np.ndarray, rng: np.random.Generator,
                                t_list: list[int] = T_LIST) -> np.ndarray:
    """Simula, para cada vela real, un camino aleatorio de 5 pasos con la MISMA
    volatilidad realizada (realized_vol_1m_intracandle) que esa vela concreta.
    Devuelve el signo (respecto al open=0) en cada marca T, shape (n, len(t_list))."""
    n = len(sigma)
    sigma_safe = np.where(np.isfinite(sigma) & (sigma > 0), sigma, np.nanmedian(sigma[sigma > 0]))
    steps = rng.normal(loc=0.0, scale=sigma_safe.reshape(-1, 1), size=(n, len(t_list)))
    cum_log_return = np.cumsum(steps, axis=1)
    return np.sign(cum_log_return)


def random_walk_benchmark(df: pd.DataFrame, n_reps: int = 200, seed: int = 42,
                           t_list: list[int] = T_LIST) -> tuple[pd.DataFrame, dict]:
    """Monte Carlo: n_reps réplicas del benchmark de random walk emparejado por
    volatilidad real de cada vela. Devuelve (curva promedio con IC, p-valores
    empíricos por T comparando el p_hat real contra la distribución nula)."""
    rng = np.random.default_rng(seed)
    sigma = df["realized_vol_1m_intracandle"].to_numpy()
    real_curve = survival_curve(df, t_list).set_index("T_seconds")["p_same_side_at_close"]

    reps = np.zeros((n_reps, len(t_list)))
    for r in range(n_reps):
        sides = simulate_random_walk_sides(sigma, rng, t_list)
        final_sign = sides[:, -1]
        for j, t in enumerate(t_list):
            side_t = sides[:, j]
            if t == max(t_list):
                reps[r, j] = 1.0
                continue
            mask = side_t != 0
            reps[r, j] = (side_t[mask] == final_sign[mask]).mean() if mask.sum() > 0 else np.nan

    bench_mean = reps.mean(axis=0)
    bench_lo = np.percentile(reps, 2.5, axis=0)
    bench_hi = np.percentile(reps, 97.5, axis=0)
    bench_df = pd.DataFrame({
        "T_seconds": t_list,
        "p_same_side_benchmark_mean": bench_mean,
        "benchmark_ci_lo": bench_lo,
        "benchmark_ci_hi": bench_hi,
    })

    p_values = {}
    for j, t in enumerate(t_list):
        real_p = real_curve.loc[t]
        # p-valor empírico de una cola: fracción de réplicas del benchmark que
        # igualan o superan el valor real observado
        p_values[t] = float((reps[:, j] >= real_p).mean())

    return bench_df, p_values
