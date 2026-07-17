# Tablero de decisión

Generado a partir de `research/*/results/summary.json` — no se edita a mano.

| Hipótesis | Estado | Nivel | Evidencia clave | Próximo paso |
|---|---|---|---|---|
| 001_survival (general, sin segmentar) | Evidencia débil / no se confirma como hipótesis única | 1 | Efecto agregado +1.87pp; al desagregar en 43 comparaciones (001A-G), 39 se quedan en la misma banda estrecha (~1-2.5pp) sin cruzar el umbral pre-registrado tras FDR | Dividida — ver fila siguiente |
| 001E · trayectoria interna hasta T=240s (nueva, más específica) | **Confirmada localmente** (Nivel 2, con reservas por cobertura de régimen) | 2 | Monótona: +11.4pp (q=0.0000); mixta: +7.1pp (q=0.0000); zigzag: **−13.1pp** (dirección opuesta); confirmado de forma independiente en 001G (interacción con alta_vol: +12.8pp; con tendencia: +13.0pp) | Pre-registrar como hipótesis propia con su propio lockbox de validación; requiere ≥3 regímenes macro antes de Nivel 3-4 |
| 002_shape | Pendiente | — | — | Semanas 6-7 |
| 003_microstructure | Pendiente | — | — | Semanas 9-10 |
| 004_orderflow | Pendiente | — | — | Semanas 11-12 |
| 005_entropy | Pendiente | — | — | Semana 13 |

## Estados posibles

- **Confirmada** — sobrevive permutation/Monte Carlo test con corrección FDR (p<0.01), efecto económicamente relevante, estable en ≥3 regímenes/años.
- **Evidencia débil** — p<0.05 sin sobrevivir corrección estricta, o efecto pequeño, o inestable entre regímenes.
- **Requiere más datos** — muestra insuficiente en el subconjunto relevante para potencia estadística adecuada.
- **Rechazada** — no sobrevive ni el test más permisivo.

## Conteo de comparaciones múltiples

48 comparaciones acumuladas sobre la hipótesis 001 (5 originales + 43 de
la profundización 001A-G, corrección Benjamini-Hochberg aplicada sobre
las 43). 4 sobreviven FDR + umbral de efecto pre-registrado, las 4
asociadas a trayectoria interna monótona. Umbral FDR efectivo a
recalcular cuando se abra 002_shape.

## Auditoría interna descubierta durante 001A-G

Se detectó que el heatmap de régimen del reporte base de 001 (corrida
2026-07-08) usaba `realized_vol_1m_intracandle`, una variable que
incluye la sub-vela 5 (=cierre) — fuga leve respecto a un punto de
decisión en T=240s. Corregido en 001A/001E usando `atr_14` (rolling de
velas cerradas) y una versión de `path_efficiency_ratio` calculada solo
con las sub-velas 1-4. No invalida la conclusión original (el efecto
agregado de +1.87pp se mantiene con la variable correcta), pero se deja
registrado por disciplina de auditoría.

_Última actualización: 2026-07-08, tras la profundización 001A-G de la
hipótesis 001 (research/001_survival/deepen_001.py)._
