"""001_survival — ejecución completa: carga -> valida -> features -> test -> reporte.

Ejecutar con:
    python research/001_survival/run.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from lib.validate import validate
from lib.features import build_5m_candles, compute_features
from lib.stats import survival_curve, random_walk_benchmark, T_LIST

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
FIGURES = RESULTS / "figures"
RAW_PATH = ROOT / "data" / "raw" / "BTCUSDT_1m.parquet"

EFFECT_SIZE_MIN = 0.03   # 3 puntos porcentuales, fijado en hypothesis.md ANTES de ver datos
ALPHA_EMPIRICAL = 0.01   # p-valor empírico requerido en T=240s
DECISION_T = 240


def plot_survival_curve(real_curve: pd.DataFrame, bench: pd.DataFrame, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)
    ax.plot(real_curve["T_seconds"], real_curve["p_same_side_at_close"], "o-",
            color="#B5792A", label="Real (BTCUSDT spot)", linewidth=2, zorder=3)
    ax.fill_between(real_curve["T_seconds"], real_curve["ci_lo"], real_curve["ci_hi"],
                     color="#B5792A", alpha=0.15, zorder=2)
    ax.plot(bench["T_seconds"], bench["p_same_side_benchmark_mean"], "s--",
            color="#4B5259", label="Benchmark: random walk (misma volatilidad)", linewidth=2, zorder=3)
    ax.fill_between(bench["T_seconds"], bench["benchmark_ci_lo"], bench["benchmark_ci_hi"],
                     color="#4B5259", alpha=0.15, zorder=1, label="IC 95% del benchmark (Monte Carlo)")
    ax.axhline(0.5, color="#B33A3A", linestyle=":", linewidth=1, label="50% (referencia trivial, NO el benchmark correcto)")
    ax.set_xlabel("Segundos desde la apertura de la vela (T)")
    ax.set_ylabel("P(cierra en el mismo lado que en T)")
    ax.set_title("Supervivencia del color — real vs. benchmark de random walk emparejado")
    ax.legend(fontsize=8, loc="lower right")
    ax.set_ylim(0.45, 1.02)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_lock_histogram(df: pd.DataFrame, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4), dpi=150)
    ax.hist(df["time_to_color_lock_sec"], bins=[30, 90, 150, 210, 270, 330],
            color="#B5792A", edgecolor="white", align="mid")
    ax.set_xlabel("Segundos hasta que el color queda fijo hasta el cierre")
    ax.set_ylabel("Número de velas")
    ax.set_title("Distribución de time_to_color_lock_sec")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_regime_heatmap(df: pd.DataFrame, out_path: Path) -> pd.DataFrame:
    df = df.copy()
    df["vol_tercile"] = pd.qcut(df["realized_vol_1m_intracandle"], 3,
                                 labels=["baja vol.", "media vol.", "alta vol."])
    rows = []
    for tercile, group in df.groupby("vol_tercile", observed=True):
        curve = survival_curve(group)
        for _, r in curve.iterrows():
            rows.append({"regimen": tercile, "T_seconds": r["T_seconds"], "p_hat": r["p_same_side_at_close"]})
    heat_df = pd.DataFrame(rows)
    pivot = heat_df.pivot(index="regimen", columns="T_seconds", values="p_hat")

    fig, ax = plt.subplots(figsize=(7, 3.2), dpi=150)
    im = ax.imshow(pivot.values, cmap="YlOrBr", vmin=0.5, vmax=1.0, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)), [f"{t}s" for t in pivot.columns])
    ax.set_yticks(range(len(pivot.index)), pivot.index)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(j, i, f"{pivot.values[i, j]:.2f}", ha="center", va="center", fontsize=9)
    fig.colorbar(im, ax=ax, label="P(mismo lado al cierre)")
    ax.set_title("Supervivencia por régimen de volatilidad (terciles de ATR intra-vela)")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return heat_df


def main() -> None:
    print("[001_survival] cargando datos crudos...")
    if not RAW_PATH.exists():
        raise SystemExit(f"No existe {RAW_PATH} — corre lib/ingest.py primero.")
    df_1m = pd.read_parquet(RAW_PATH)
    print(f"[001_survival] {len(df_1m)} velas de 1m cargadas "
          f"({df_1m['open_time'].min()} -> {df_1m['open_time'].max()})")

    print("[001_survival] validando...")
    report = validate(df_1m, interval_minutes=1)
    print(report.summary())
    if report.blocking:
        raise SystemExit("Validación bloqueante — no se continúa.")

    print("[001_survival] construyendo velas de 5m + features P0...")
    df_5m = build_5m_candles(df_1m)
    df_5m = compute_features(df_5m)
    print(f"[001_survival] {len(df_5m)} velas de 5m con features completas")

    # Lockbox: los últimos 90 días quedan reservados, no se usan en este experimento
    # exploratorio inicial — se usarán solo en la validación final.
    lockbox_start = df_5m["open_time"].max() - pd.Timedelta(days=90)
    df_dev = df_5m[df_5m["open_time"] < lockbox_start].copy()
    n_lockbox = int((df_5m["open_time"] >= lockbox_start).sum())
    print(f"[001_survival] lockbox reservado: {n_lockbox} velas de los últimos 90 días, "
          f"NO usadas en este experimento")

    print("[001_survival] calculando curva de supervivencia real...")
    real_curve = survival_curve(df_dev)
    print(real_curve.to_string(index=False))

    print("[001_survival] simulando benchmark de random walk (200 réplicas Monte Carlo)...")
    bench_df, p_values = random_walk_benchmark(df_dev, n_reps=200, seed=42)
    print(bench_df.to_string(index=False))
    print("p-valores empíricos por T:", {k: round(v, 4) for k, v in p_values.items()})

    FIGURES.mkdir(parents=True, exist_ok=True)
    plot_survival_curve(real_curve, bench_df, FIGURES / "survival_curve.png")
    plot_lock_histogram(df_dev, FIGURES / "lock_histogram.png")
    heat_df = plot_regime_heatmap(df_dev, FIGURES / "regime_heatmap.png")

    real_240 = real_curve.set_index("T_seconds").loc[DECISION_T, "p_same_side_at_close"]
    bench_240 = bench_df.set_index("T_seconds").loc[DECISION_T, "p_same_side_benchmark_mean"]
    effect_size = real_240 - bench_240
    p_emp_240 = p_values[DECISION_T]

    success = (p_emp_240 < ALPHA_EMPIRICAL) and (effect_size >= EFFECT_SIZE_MIN)
    if success:
        decision = "continuar"
        nivel = 2
    elif p_emp_240 >= 0.05 or effect_size < 0.01:
        decision = "abandonar (esta formulación específica)"
        nivel = "rechazada"
    else:
        decision = "requiere más datos"
        nivel = 1

    print(f"\n[001_survival] T={DECISION_T}s: p_hat_real={real_240:.4f} vs "
          f"benchmark={bench_240:.4f} (efecto={effect_size:+.4f}, p_empirico={p_emp_240:.4f})")
    print(f"[001_survival] DECISIÓN: {decision}")

    interpretacion = (
        f"La evidencia observada, a T={DECISION_T}s, es consistente con una diferencia de "
        f"{effect_size:+.4f} entre la probabilidad real de conservar el lado ({real_240:.4f}) y la "
        f"probabilidad esperada bajo un random walk con la misma volatilidad realizada "
        f"({bench_240:.4f}), con un p-valor empírico de {p_emp_240:.4f} sobre {len(df_dev)} velas de desarrollo. "
        f"{'La hipótesis de edge no ha sido refutada en esta primera pasada.' if success else 'No se encontró evidencia suficiente para distinguir el resultado real del benchmark de random walk, o el tamaño del efecto no alcanza la relevancia mínima pre-registrada.'}"
    )

    devils_advocate = [
        "El benchmark Monte Carlo asume retornos gaussianos i.i.d. dentro de la vela; si los retornos reales de BTC tienen colas más gruesas o autocorrelación de corto plazo no capturada por el sigma emparejado, el benchmark podría estar mal calibrado en cualquier dirección.",
        f"La resolución de 1 minuto (en vez de 30s) es más gruesa que la del diseño original — parte del efecto observado podría ser un artefacto de esa discretización, no información real.",
        f"El periodo cubierto (~{(df_dev['open_time'].max() - df_dev['open_time'].min()).days} días, excluyendo el lockbox) puede no cruzar suficientes regímenes de mercado distintos — se requieren al menos 3 regímenes independientes antes de hablar de edge confirmado, y este experimento por sí solo no lo verifica todavía.",
        "El número de réplicas Monte Carlo (200) es modesto; el p-valor empírico mínimo detectable es 1/200=0.005, cerca del umbral de 0.01 usado como criterio — el resultado del lado del umbral podría cambiar con más réplicas.",
        "Se evaluaron 5 valores de T simultáneamente; aunque T=240s se pre-registró como el punto de decisión, la mera existencia de 5 comparaciones internas aumenta la probabilidad de un falso positivo en al menos uno de ellos si se mirara cualquier T sin corrección.",
    ]

    registro = {
        "hipotesis": "Supervivencia del color contiene información más allá del artefacto mecánico de random walk",
        "fecha_de_pre_registro": "ver hypothesis.md (commit previo a esta ejecución)",
        "fecha_de_ejecucion": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "resultado_esperado": f"p_hat_real > IC 95% del benchmark en T={DECISION_T}s, con efecto >= {EFFECT_SIZE_MIN}",
        "resultado_observado": f"p_hat_real={real_240:.4f}, benchmark_mean={bench_240:.4f}, efecto={effect_size:+.4f}, p_empirico={p_emp_240:.4f}",
        "benchmark_usado": "Random walk Monte Carlo (200 réplicas) emparejado por volatilidad realizada intra-vela — NO 50% plano",
        "estadistico_y_p_valor": f"p-valor empírico de una cola en T={DECISION_T}s: {p_emp_240:.4f}",
        "tamano_del_efecto": f"{effect_size:+.4f} ({effect_size*100:+.2f} puntos porcentuales)",
        "interpretacion": interpretacion,
        "problemas_encontrados": "Resolución de supervivencia limitada a 1 minuto (no 30s) por disponibilidad de datos de Binance vía klines REST.",
        "limitaciones": "Un solo periodo de ~2 años, sin desglose todavía por régimen alcista/bajista completo (ver heatmap adjunto para desglose por volatilidad). Lockbox de 90 días reservado y no usado en este experimento.",
        "nivel_de_evidencia": nivel,
        "decision": decision,
        "proximo_paso": "002_shape (estructura interna) si continúa; documentar como rechazada en board.md y pasar directo a 002_shape igualmente si se abandona esta formulación." if decision != "continuar" else "Extender a validación multi-régimen antes de subir a Nivel 3; iniciar 002_shape en paralelo.",
        "responsable": "2026-07-07",
    }

    tables = {
        "Curva de supervivencia real": real_curve,
        "Benchmark de random walk (Monte Carlo)": bench_df,
        "Supervivencia por régimen de volatilidad": heat_df,
    }
    figures = {
        "Curva de supervivencia real vs. benchmark de random walk, con IC": FIGURES / "survival_curve.png",
        "Distribución de time_to_color_lock_sec": FIGURES / "lock_histogram.png",
        "Heatmap: régimen de volatilidad x T": FIGURES / "regime_heatmap.png",
    }

    from lib.report import make_report
    report_path = make_report(
        title="001 · Supervivencia del color",
        hypothesis=(
            "Si una vela de 5m sigue en el mismo lado del open a los T segundos, "
            "¿cierra en ese lado con probabilidad mayor a la de un random walk con la misma volatilidad?"
        ),
        registro=registro,
        tables=tables,
        figures=figures,
        devils_advocate=devils_advocate,
        out_path=RESULTS / "report.html",
    )
    print(f"[001_survival] reporte escrito en {report_path}")

    summary = {
        "hipotesis": "001_survival",
        "estado": {"continuar": "evidencia_debil", "abandonar (esta formulación específica)": "rechazada",
                   "requiere más datos": "requiere_mas_datos"}[decision],
        "nivel_de_evidencia": nivel,
        "T_decision": DECISION_T,
        "p_hat_real": round(float(real_240), 4),
        "benchmark_mean": round(float(bench_240), 4),
        "effect_size": round(float(effect_size), 4),
        "p_empirico": round(float(p_emp_240), 4),
        "n_velas_desarrollo": int(len(df_dev)),
        "n_velas_lockbox_reservadas": n_lockbox,
        "fecha_ejecucion": registro["fecha_de_ejecucion"],
        "proximo_paso": registro["proximo_paso"],
    }
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[001_survival] summary.json escrito")
    print("\n" + report.summary())


if __name__ == "__main__":
    main()
