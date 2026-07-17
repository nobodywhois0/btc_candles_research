# Tablero de decisión

Generado a partir de `research/*/results/summary.json` — no se edita a mano.

| Hipótesis | Estado | Nivel | Evidencia clave | Próximo paso |
|---|---|---|---|---|
| 001_survival | Requiere más datos | 1 | T=240s: real=0.8712 vs. benchmark random-walk=0.8525 (efecto +1.87pp, p_empírico=0.0000 sobre 200 réplicas) — estadísticamente distinguible del benchmark, pero por debajo del efecto mínimo pre-registrado (3pp) | Extender a validación multi-régimen antes de subir de nivel; iniciar 002_shape en paralelo |
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

1 hipótesis probada hasta ahora (001_survival), 5 comparaciones internas
(T=60,120,180,240,300s). Umbral FDR efectivo a recalcular cuando se abra
002_shape.

_Última actualización: 2026-07-08, tras la primera corrida real de
001_survival sobre 2 años de BTCUSDT spot (klines de Binance)._
