# 001 · Supervivencia del color — notas del investigador

Ver `hypothesis.md` para la hipótesis pre-registrada, `run.py` para la
ejecución, `results/report.html` para el registro completo del
experimento.

_Esta sección se actualiza después de cada corrida, nunca antes._

## Corrida 2026-07-08 — primera ejecución real

BTCUSDT spot, 2 años de klines de 1m (2024-07-08 → 2026-07-08),
1,051,201 filas, 0 gaps, 0 duplicados, 0 violaciones OHLC. 210,239
velas de 5m construidas; lockbox de los últimos 90 días reservado
(25,921 velas) y no tocado en este experimento.

**Resultado**: a T=240s, la probabilidad real de conservar el lado del
open (0.8712) supera consistentemente al benchmark de random walk
emparejado por volatilidad (0.8525) — un efecto de +1.87 puntos
porcentuales, con p-valor empírico de 0.0000 sobre 200 réplicas Monte
Carlo (ninguna réplica del benchmark alcanzó el valor real). El mismo
patrón se repite, más modesto, en T=60/120/180s.

**Pero** el efecto (+1.87pp) queda por debajo del tamaño mínimo
pre-registrado en `hypothesis.md` (3pp) para declarar éxito directo. Por
eso la decisión formal es **"requiere más datos"** (Nivel 1), no
"continuar" ni "abandonar" — el estado intermedio previsto para
exactamente este caso.

**Nota honesta**: la gráfica de supervivencia (`results/figures/survival_curve.png`)
muestra con claridad por qué el benchmark de random walk era
indispensable — sin él, un investigador menos cuidadoso habría
comparado 0.87 contra "50%" y anunciado un edge enorme. El benchmark
correcto reduce ese "edge" aparente a un margen de menos de 2 puntos
porcentuales — exactamente el tipo de artefacto que había que vigilar.

**Próximo paso real**: antes de subir de nivel, repetir este mismo
análisis con el benchmark calculado *por régimen de volatilidad*
(el heatmap actual muestra P(mismo lado) real por régimen, pero no
compara cada régimen contra su propio benchmark simulado — eso quedó
fuera del alcance de esta primera corrida y es la limitación más
importante a resolver antes de tocar el lockbox). En paralelo, abrir
`002_shape`.

