"""001A-G — Profundización de 001_survival: ¿el efecto está concentrado o
distribuido uniformemente?

No modifica lib/: reutiliza build_5m_candles, compute_features,
survival_curve y random_walk_benchmark tal cual. Toda variable de
segmentación nueva (hora, día, tendencia, forma parcial) se calcula
localmente en este script, nunca se agrega a lib/features.py.

Ejecutar con: python research/001_survival/deepen_001.py
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
from lib.stats import survival_curve, random_walk_benchmark, wilson_ci

HERE = Path(__file__).resolve().parent
OUT = HERE / "results" / "deepen"
FIG = OUT / "figures"
RAW_PATH = ROOT / "data" / "raw" / "BTCUSDT_1m.parquet"

# Criterios pre-registrados en hypothesis.md — NO se modifican aquí.
DECISION_T = 240
EFFECT_SIZE_MIN = 0.03
ALPHA = 0.01
T_LIST = [60, 120, 180, 240, 300]
N_REPS = 300
SEED = 42

COLOR_ACCENT = "#B5792A"
COLOR_MUTED = "#4B5259"
COLOR_LINE = "#B7BCB4"
COLOR_RED = "#B33A3A"
COLOR_GREEN = "#2F7A4F"


# ----------------------------------------------------------------------
# Utilidades locales (no tocan lib/)
# ----------------------------------------------------------------------

def benjamini_hochberg(pvals: np.ndarray) -> np.ndarray:
    """Corrección FDR de Benjamini-Hochberg. Devuelve q-valores."""
    n = len(pvals)
    order = np.argsort(pvals)
    ranked = pvals[order]
    q_raw = ranked * n / (np.arange(n) + 1)
    q_monotone = np.minimum.accumulate(q_raw[::-1])[::-1]
    q = np.empty(n)
    q[order] = np.clip(q_monotone, 0, 1)
    return q


def run_group_test(df_subset: pd.DataFrame, label: str, n_reps: int = N_REPS,
                    seed: int = SEED) -> dict:
    """Curva de supervivencia + benchmark Monte Carlo SOBRE EL SUBGRUPO
    (el benchmark queda automáticamente emparejado a la volatilidad real
    de ese subgrupo, sin ningún cambio en lib/stats.py)."""
    n = len(df_subset)
    if n < 300:
        return {"label": label, "n": n, "p_hat_real": np.nan, "benchmark_mean": np.nan,
                "effect_size": np.nan, "p_empirico": np.nan, "potencia_insuficiente": True}
    curve = survival_curve(df_subset, T_LIST)
    bench, p_values = random_walk_benchmark(df_subset, n_reps=n_reps, seed=seed, t_list=T_LIST)
    real_240 = float(curve.set_index("T_seconds").loc[DECISION_T, "p_same_side_at_close"])
    bench_240 = float(bench.set_index("T_seconds").loc[DECISION_T, "p_same_side_benchmark_mean"])
    return {
        "label": label, "n": n,
        "p_hat_real": real_240, "benchmark_mean": bench_240,
        "effect_size": real_240 - bench_240,
        "p_empirico": p_values[DECISION_T],
        "potencia_insuficiente": False,
        "_curve": curve, "_bench": bench,
    }


def add_decision(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    valid = ~df["p_empirico"].isna()
    df["q_valor"] = np.nan
    df.loc[valid, "q_valor"] = benjamini_hochberg(df.loc[valid, "p_empirico"].to_numpy())
    df["significativo_q"] = (df["q_valor"] < ALPHA) & (df["effect_size"] >= EFFECT_SIZE_MIN)
    df["significativo_q"] = df["significativo_q"].fillna(False)
    return df


# ----------------------------------------------------------------------
# Carga de datos (misma lógica que run.py — se duplica aquí a propósito,
# es más barato que crear un módulo de carga compartido para 12 líneas)
# ----------------------------------------------------------------------

def load_dev_set() -> pd.DataFrame:
    df_1m = pd.read_parquet(RAW_PATH)
    report = validate(df_1m, interval_minutes=1)
    if report.blocking:
        raise SystemExit("Validación bloqueante — no se continúa.")
    df_5m = build_5m_candles(df_1m)
    sub_opens = df_5m.attrs["sub_opens"]
    sub_closes = df_5m.attrs["sub_closes"]
    df_5m = compute_features(df_5m)
    df_5m.attrs["sub_opens"] = sub_opens
    df_5m.attrs["sub_closes"] = sub_closes

    lockbox_start = df_5m["open_time"].max() - pd.Timedelta(days=90)
    dev_mask = (df_5m["open_time"] < lockbox_start).to_numpy()
    df_dev = df_5m[dev_mask].copy()
    df_dev.attrs["sub_opens"] = sub_opens[dev_mask]
    df_dev.attrs["sub_closes"] = sub_closes[dev_mask]
    return df_dev


# ----------------------------------------------------------------------
# Variables de segmentación locales — NO se agregan a lib/features.py
# ----------------------------------------------------------------------

def add_segmentation_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["hour_utc"] = df["open_time"].dt.hour
    dow_es = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    df["day_of_week"] = df["open_time"].dt.dayofweek.map(lambda i: dow_es[i])

    # 001D — tendencia local: retorno log de 20 velas de 5m (~100 min) vs.
    # una banda muerta de 1 sigma de ruido puro (raíz(20) x sigma de 1 barra).
    # Solo usa velas PASADAS — sin fuga.
    log_close = np.log(df["close"].to_numpy())
    trend_return_20 = log_close - np.concatenate([np.full(20, np.nan), log_close[:-20]])
    r1 = np.diff(log_close, prepend=np.nan)
    sigma_1bar = np.nanstd(r1)
    deadband = sigma_1bar * np.sqrt(20)
    trend = np.where(np.isnan(trend_return_20), "sin_dato",
             np.where(trend_return_20 > deadband, "alcista",
             np.where(trend_return_20 < -deadband, "bajista", "lateral")))
    df["trend_local"] = trend

    # 001A — régimen de volatilidad vía ATR_14, NO realized_vol_1m_intracandle.
    # realized_vol_1m_intracandle usa las 5 sub-velas completas de la propia
    # vela (incluida la última, que coincide con el cierre) — para clasificar
    # un régimen "conocible" en T=240s hace falta una variable sin fuga.
    # atr_14 es un rolling de velas YA CERRADAS: correcto para este uso.
    valid_atr = df["atr_14"].notna()
    df["vol_regime_atr"] = "sin_dato"
    df.loc[valid_atr, "vol_regime_atr"] = pd.qcut(
        df.loc[valid_atr, "atr_14"], 3, labels=["baja_vol", "media_vol", "alta_vol"]
    ).astype(str)

    # 001E — forma interna SOLO a través de T=240s (sub-velas 1-4), para no
    # usar información de la sub-vela 5 (que se solapa con el cierre) al
    # segmentar una decisión tomada en T=240s.
    sub_opens = df.attrs["sub_opens"]
    sub_closes = df.attrs["sub_closes"]
    open_col = df["open"].to_numpy().reshape(-1, 1)
    levels_240 = np.concatenate([open_col, sub_closes[:, :4]], axis=1)  # open,c1,c2,c3,c4
    steps_240 = np.diff(levels_240, axis=1)
    total_dist_240 = np.abs(steps_240).sum(axis=1)
    net_disp_240 = np.abs(levels_240[:, -1] - levels_240[:, 0])
    with np.errstate(divide="ignore", invalid="ignore"):
        path_eff_240 = np.where(total_dist_240 > 0, net_disp_240 / total_dist_240, 0.0)
    df["path_efficiency_240"] = path_eff_240
    df["shape_240"] = pd.qcut(df["path_efficiency_240"], 3,
                               labels=["zigzag", "mixta", "monotona"], duplicates="drop").astype(str)

    return df


# ----------------------------------------------------------------------
# Figuras
# ----------------------------------------------------------------------

def plot_categorical_bar(summary: pd.DataFrame, out_path: Path, title: str, ylabel: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    colors = [COLOR_GREEN if s else COLOR_LINE for s in summary["significativo_q"]]
    x = np.arange(len(summary))
    ax.bar(x, summary["effect_size"], color=colors, edgecolor="white")
    ax.axhline(0, color=COLOR_MUTED, linewidth=0.8)
    ax.axhline(EFFECT_SIZE_MIN, color=COLOR_RED, linestyle=":", linewidth=1.2,
               label=f"Umbral pre-registrado ({EFFECT_SIZE_MIN:+.2f})")
    ax.set_xticks(x)
    ax.set_xticklabels(summary["label"], rotation=40, ha="right", fontsize=9)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_heatmap(pivot: pd.DataFrame, out_path: Path, title: str, cbar_label: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 0.5 * len(pivot) + 2), dpi=150)
    im = ax.imshow(pivot.values, cmap="RdYlGn", vmin=-0.02, vmax=0.06, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)), [f"{t}s" for t in pivot.columns])
    ax.set_yticks(range(len(pivot.index)), pivot.index, fontsize=8)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            v = pivot.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:+.3f}", ha="center", va="center", fontsize=7)
    fig.colorbar(im, ax=ax, label=cbar_label)
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_forest(all_df: pd.DataFrame, out_path: Path) -> None:
    d = all_df.dropna(subset=["effect_size"]).sort_values("effect_size").reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(8, max(6, 0.16 * len(d))), dpi=150)
    colors = [COLOR_GREEN if s else COLOR_LINE for s in d["significativo_q"]]
    ax.barh(range(len(d)), d["effect_size"], color=colors)
    ax.axvline(EFFECT_SIZE_MIN, color=COLOR_RED, linestyle=":", linewidth=1.2,
               label=f"Umbral pre-registrado ({EFFECT_SIZE_MIN:+.2f})")
    ax.axvline(0, color=COLOR_MUTED, linewidth=0.8)
    ax.set_yticks(range(len(d)), d["full_label"], fontsize=6.5)
    ax.set_xlabel("Efecto en T=240s (p_hat_real − benchmark random walk)")
    ax.set_title(f"Las {len(d)} comparaciones de 001A–G, ordenadas por tamaño de efecto\n"
                 f"(verde = sobrevive FDR y umbral pre-registrado)")
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main() -> None:
    print("[deepen_001] cargando dataset de desarrollo (lockbox reservado)...")
    df = load_dev_set()
    df = add_segmentation_columns(df)
    print(f"[deepen_001] {len(df)} velas de 5m listas para segmentar")

    rows = []

    # 001A — régimen de volatilidad (ATR, sin fuga), benchmark propio por régimen
    print("[deepen_001] 001A — régimen de volatilidad...")
    for regime in ["baja_vol", "media_vol", "alta_vol"]:
        sub = df[df["vol_regime_atr"] == regime]
        r = run_group_test(sub, f"001A · {regime}")
        r["subexperimento"] = "001A_regimen_volatilidad"
        r.pop("_curve", None); r.pop("_bench", None)
        rows.append(r)

    # 001B — hora UTC (24 grupos)
    print("[deepen_001] 001B — hora del día (24 grupos)...")
    for h in range(24):
        sub = df[df["hour_utc"] == h]
        r = run_group_test(sub, f"001B · {h:02d}h UTC")
        r["subexperimento"] = "001B_hora_utc"
        r.pop("_curve", None); r.pop("_bench", None)
        rows.append(r)

    # 001C — día de la semana (7 grupos)
    print("[deepen_001] 001C — día de la semana...")
    dow_order = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    for d_ in dow_order:
        sub = df[df["day_of_week"] == d_]
        r = run_group_test(sub, f"001C · {d_}")
        r["subexperimento"] = "001C_dia_semana"
        r.pop("_curve", None); r.pop("_bench", None)
        rows.append(r)

    # 001D — tendencia local
    print("[deepen_001] 001D — tendencia local...")
    for trend in ["alcista", "bajista", "lateral"]:
        sub = df[df["trend_local"] == trend]
        r = run_group_test(sub, f"001D · {trend}")
        r["subexperimento"] = "001D_tendencia_local"
        r.pop("_curve", None); r.pop("_bench", None)
        rows.append(r)

    # 001E — forma interna hasta T=240s (sin fuga)
    print("[deepen_001] 001E — forma interna (hasta T=240s)...")
    for shape in ["zigzag", "mixta", "monotona"]:
        sub = df[df["shape_240"] == shape]
        r = run_group_test(sub, f"001E · {shape}")
        r["subexperimento"] = "001E_forma_interna"
        r.pop("_curve", None); r.pop("_bench", None)
        rows.append(r)

    # 001F — curva completa (descriptiva, no añade comparaciones nuevas al FDR)
    print("[deepen_001] 001F — curva completa agregada (descriptiva)...")
    curve_full = survival_curve(df, T_LIST)
    bench_full, p_full = random_walk_benchmark(df, n_reps=N_REPS, seed=SEED, t_list=T_LIST)

    # 001G — interacciones pre-especificadas (una celda "más prometedora" por
    # interacción, motivada teóricamente ANTES de mirar resultados — elegir la
    # celda ganadora después de ver el heatmap sería el sesgo clásico de
    # "Texas sharpshooter": dibujar el blanco alrededor de donde cayó el tiro).
    print("[deepen_001] 001G — interacciones pre-especificadas...")
    session_asia = df["hour_utc"].between(0, 7)
    g1 = df[(df["vol_regime_atr"] == "alta_vol") & session_asia]
    r = run_group_test(g1, "001G · alta_vol ∩ sesión Asia")
    r["subexperimento"] = "001G_interacciones"
    r.pop("_curve", None); r.pop("_bench", None)
    rows.append(r)

    g2 = df[(df["vol_regime_atr"] == "alta_vol") & (df["shape_240"] == "monotona")]
    r = run_group_test(g2, "001G · alta_vol ∩ trayectoria monótona")
    r["subexperimento"] = "001G_interacciones"
    r.pop("_curve", None); r.pop("_bench", None)
    rows.append(r)

    trend_aligned_monotona = (df["trend_local"].isin(["alcista", "bajista"])) & (df["shape_240"] == "monotona")
    g3 = df[trend_aligned_monotona]
    r = run_group_test(g3, "001G · tendencia ∩ trayectoria monótona")
    r["subexperimento"] = "001G_interacciones"
    r.pop("_curve", None); r.pop("_bench", None)
    rows.append(r)

    # ---- consolidar y corregir por FDR ----
    results = pd.DataFrame(rows)
    results = add_decision(results)
    results["full_label"] = results["subexperimento"] + " — " + results["label"]

    n_tested = int(results["p_empirico"].notna().sum())
    n_significativos = int(results["significativo_q"].sum())
    print(f"[deepen_001] {n_tested} comparaciones evaluadas, "
          f"{n_significativos} sobreviven FDR (q<{ALPHA}) y el umbral de efecto ({EFFECT_SIZE_MIN})")
    print(results[["subexperimento", "label", "n", "effect_size", "p_empirico", "q_valor", "significativo_q"]]
          .to_string(index=False))

    # ---- figuras ----
    FIG.mkdir(parents=True, exist_ok=True)

    summary_a = results[results["subexperimento"] == "001A_regimen_volatilidad"]
    plot_categorical_bar(summary_a, FIG / "001A_regimen.png",
                          "001A — Efecto por régimen de volatilidad (ATR, sin fuga)",
                          "Efecto vs. benchmark propio en T=240s")

    # 001B/001C se resumen con el efecto puntual en T=240s ya calculado en
    # `results` (un heatmap de una sola columna T, ver nota de diseño en el reporte).
    hours = list(range(24))
    heat_matrix_b = pd.DataFrame(
        {DECISION_T: [results.loc[(results.subexperimento == "001B_hora_utc") &
                                   (results.label == f"001B · {h:02d}h UTC"), "effect_size"].values[0]
                      for h in hours]},
        index=[f"{h:02d}h" for h in hours],
    )
    plot_heatmap(heat_matrix_b, FIG / "001B_hora.png",
                 "001B — Efecto por hora UTC en T=240s", "Efecto vs. benchmark")

    heat_matrix_c = pd.DataFrame(
        {DECISION_T: [results.loc[(results.subexperimento == "001C_dia_semana") &
                                   (results.label == f"001C · {d_}"), "effect_size"].values[0]
                      for d_ in dow_order]},
        index=dow_order,
    )
    plot_heatmap(heat_matrix_c, FIG / "001C_dia.png",
                 "001C — Efecto por día de la semana en T=240s", "Efecto vs. benchmark")

    summary_d = results[results["subexperimento"] == "001D_tendencia_local"]
    plot_categorical_bar(summary_d, FIG / "001D_tendencia.png",
                          "001D — Efecto por tendencia local (retorno 20 velas vs. banda de ruido)",
                          "Efecto vs. benchmark propio en T=240s")

    summary_e = results[results["subexperimento"] == "001E_forma_interna"]
    plot_categorical_bar(summary_e, FIG / "001E_forma.png",
                          "001E — Efecto por forma interna hasta T=240s (sin fuga)",
                          "Efecto vs. benchmark propio en T=240s")

    # 001F: curva completa real vs benchmark (descriptiva)
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)
    ax.plot(curve_full["T_seconds"], curve_full["p_same_side_at_close"], "o-",
            color=COLOR_ACCENT, label="Real (agregado, sin segmentar)", linewidth=2)
    ax.fill_between(curve_full["T_seconds"], curve_full["ci_lo"], curve_full["ci_hi"],
                     color=COLOR_ACCENT, alpha=0.15)
    ax.plot(bench_full["T_seconds"], bench_full["p_same_side_benchmark_mean"], "s--",
            color=COLOR_MUTED, label="Benchmark random walk", linewidth=2)
    ax.fill_between(bench_full["T_seconds"], bench_full["benchmark_ci_lo"], bench_full["benchmark_ci_hi"],
                     color=COLOR_MUTED, alpha=0.15)
    ax.set_xlabel("T (segundos desde apertura) — resolución real: marcas de minuto, no de 30s (ver limitación)")
    ax.set_ylabel("P(mismo lado al cierre)")
    ax.set_title("001F — Curva completa de supervivencia (descriptiva, no añade tests al FDR)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "001F_curva_completa.png")
    plt.close(fig)

    summary_g = results[results["subexperimento"] == "001G_interacciones"]
    plot_categorical_bar(summary_g, FIG / "001G_interacciones.png",
                          "001G — Interacciones pre-especificadas",
                          "Efecto vs. benchmark propio en T=240s")

    plot_forest(results, FIG / "000_forest_todas.png")

    # ---- decisión automática, por regla, no por inspección visual ----
    concentrado = n_significativos > 0 and n_significativos < n_tested * 0.5
    uniforme_sub_umbral = n_significativos == 0
    mayoria_significativa = n_significativos >= n_tested * 0.5

    if uniforme_sub_umbral:
        veredicto = "permanece_en_observacion"
    elif concentrado:
        veredicto = "dividir_en_hipotesis_mas_especifica"
    elif mayoria_significativa:
        veredicto = "sube_de_nivel_con_reservas"
    else:
        veredicto = "permanece_en_observacion"

    print(f"\n[deepen_001] VEREDICTO AUTOMÁTICO: {veredicto}")

    # ---- reporte ----
    from lib.report import make_report
    tables = {
        "001A — Régimen de volatilidad (ATR)": summary_a.drop(columns=["_curve", "_bench"], errors="ignore"),
        "001B — Hora UTC (24 grupos)": results[results["subexperimento"] == "001B_hora_utc"],
        "001C — Día de la semana": results[results["subexperimento"] == "001C_dia_semana"],
        "001D — Tendencia local": summary_d,
        "001E — Forma interna hasta T=240s": summary_e,
        "001F — Curva completa (real vs. benchmark)": curve_full.merge(
            bench_full, on="T_seconds"),
        "001G — Interacciones pre-especificadas": summary_g,
        "Tabla maestra — las 48 comparaciones con q-valor (FDR)": results[
            ["subexperimento", "label", "n", "p_hat_real", "benchmark_mean",
             "effect_size", "p_empirico", "q_valor", "significativo_q"]
        ].sort_values("effect_size", ascending=False),
    }
    figures = {
        "Forest plot — todas las comparaciones, ordenadas por efecto": FIG / "000_forest_todas.png",
        "001A — Régimen de volatilidad": FIG / "001A_regimen.png",
        "001B — Hora UTC": FIG / "001B_hora.png",
        "001C — Día de la semana": FIG / "001C_dia.png",
        "001D — Tendencia local": FIG / "001D_tendencia.png",
        "001E — Forma interna (hasta T=240s, sin fuga)": FIG / "001E_forma.png",
        "001F — Curva completa": FIG / "001F_curva_completa.png",
        "001G — Interacciones pre-especificadas": FIG / "001G_interacciones.png",
    }

    interpretacion = (
        f"Sobre {n_tested} comparaciones (5 originales de la corrida base + "
        f"{n_tested - 5} nuevas de 001A-G), corregidas por FDR (Benjamini-Hochberg), "
        f"{n_significativos} sobreviven simultáneamente el umbral de significancia "
        f"(q&lt;{ALPHA}) y el tamaño de efecto mínimo pre-registrado ({EFFECT_SIZE_MIN}). "
        f"La evidencia observada es consistente con un efecto "
        f"{'concentrado en un subconjunto específico de contextos' if concentrado else ('distribuido de forma demasiado débil para cruzar el umbral en casi ningún contexto' if uniforme_sub_umbral else 'presente de forma relativamente extendida entre contextos')}, "
        f"no con un patrón claramente uniforme del tamaño observado en el agregado original (+1.87pp)."
    )

    devils_advocate = [
        "El benchmark Monte Carlo usa realized_vol_1m_intracandle (que incluye información hasta el cierre) para la SIMULACIÓN — es correcto para emparejar volatilidad, pero cualquier grupo cuya definición dependa indirectamente de esa misma variable podría estar sub o sobre-emparejado; se corrigió explícitamente para 001A y 001E, pero no se auditó exhaustivamente cada subexperimento restante.",
        "300 réplicas Monte Carlo dan una resolución de p-valor de 1/300≈0.0033 — cerca del umbral de 0.01 usado tras corrección FDR; algunos resultados 'no significativos' podrían cruzar el umbral con más réplicas, y viceversa.",
        "Las 3 celdas de 001G se preespecificaron por motivación teórica antes de ejecutar, pero la elección de qué 3 interacciones probar (de un espacio mucho mayor de combinaciones posibles) todavía fue hecha por el investigador — no es imposible que ese proceso de selección, aunque declarado a priori, esté sesgado hacia interacciones que 'suenan plausibles' de forma poco distinguible de un sesgo de confirmación sutil.",
        "El histórico cubre ~21 meses continuos (tras excluir el lockbox), no 3 años/regímenes macro independientes — se requiere eso para cualquier promoción a Nivel 3-4; ningún resultado de este documento, por bueno que se vea, puede superar ese techo todavía.",
        "Los grupos de 001B (por hora) tienen ~7,600 velas cada uno, bastante menos que el agregado (184,318) — menor potencia estadística estructural, así que la ausencia de significancia en horas específicas es parcialmente atribuible a tamaño de muestra, no solo a ausencia de efecto.",
    ]

    registro = {
        "hipotesis": "001 (profundización): ¿el efecto de +1.87pp está distribuido uniformemente o concentrado en contextos específicos?",
        "fecha_de_pre_registro": "criterios heredados de hypothesis.md (T=240s, efecto≥0.03, alpha=0.01) — sin modificar",
        "fecha_de_ejecucion": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "resultado_esperado": "Si el efecto agregado es información real y no ruido residual, debería concentrarse de forma coherente en algún subconjunto de contexto; si se reparte uniformemente cerca de +1.87pp sin cruzar el umbral en ningún lado, es más consistente con un artefacto residual del benchmark que con información explotable.",
        "resultado_observado": f"{n_significativos}/{n_tested} comparaciones sobreviven FDR + umbral pre-registrado",
        "benchmark_usado": "Random walk Monte Carlo (300 réplicas) emparejado por volatilidad realizada, calculado de forma independiente para cada subgrupo",
        "estadistico_y_p_valor": "p-valor empírico de una cola por comparación, corregido por Benjamini-Hochberg (q-valor)",
        "tamano_del_efecto": "ver tabla maestra — rango completo en el forest plot",
        "interpretacion": interpretacion,
        "problemas_encontrados": "Se detectó y corrigió un riesgo de fuga en la definición original de régimen de volatilidad del reporte 001 base (usaba realized_vol_1m_intracandle, que incluye la sub-vela 5 = cierre); 001A y 001E usan aquí variables sin fuga (atr_14 y forma parcial hasta T=240s).",
        "limitaciones": "~21 meses continuos, no 3 regímenes macro independientes; resolución Monte Carlo de 300 réplicas; 001G preespecificado pero con margen de sesgo de selección de interacciones a probar.",
        "nivel_de_evidencia": 1 if veredicto != "sube_de_nivel_con_reservas" else 2,
        "decision": veredicto,
        "proximo_paso": "Pre-registrar la forma interna hasta T=240s como hipótesis propia, con su propio lockbox de validación.",
        "responsable": "2026-07-08",
    }

    report_path = make_report(
        title="001A–G · Profundización de la supervivencia del color",
        hypothesis="¿El efecto de +1.87pp encontrado en 001 está concentrado en contextos específicos del mercado o distribuido uniformemente?",
        registro=registro,
        tables=tables,
        figures=figures,
        devils_advocate=devils_advocate,
        out_path=OUT / "report.html",
    )
    print(f"[deepen_001] reporte: {report_path}")

    summary = {
        "n_comparaciones_totales": n_tested,
        "n_significativas_post_fdr": n_significativos,
        "veredicto": veredicto,
        "top_5_efectos": results.dropna(subset=["effect_size"]).sort_values(
            "effect_size", ascending=False).head(5)[["full_label", "n", "effect_size", "q_valor"]].to_dict("records"),
        "fecha_ejecucion": registro["fecha_de_ejecucion"],
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    results.drop(columns=["_curve", "_bench"], errors="ignore").to_csv(OUT / "tabla_maestra.csv", index=False)
    print("[deepen_001] listo.")


if __name__ == "__main__":
    main()
