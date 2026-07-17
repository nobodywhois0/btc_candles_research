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
importante a resolver antes de tocar el lockbox). Resuelto en la
profundización de abajo.

## Profundización 001A-G (2026-07-08)

Ver `deepen_001.py` y `results/deepen/report.html`. Pregunta: ¿el
+1.87pp agregado está distribuido uniformemente o concentrado en algún
contexto? 43 comparaciones nuevas (regímenes de volatilidad, 24 horas,
7 días, tendencia local, forma interna hasta T=240s, y 3 interacciones
pre-especificadas), corregidas por FDR (Benjamini-Hochberg), sin
modificar `lib/` ni bajar el umbral pre-registrado (efecto≥0.03,
q&lt;0.01).

**Hallazgo**: el efecto NO está distribuido uniformemente. Por
calendario (hora, día) y por régimen de volatilidad agregado, el efecto
se queda plano en la misma banda de ~1-2.5pp del agregado original —
ninguna hora, día o régimen por sí solo cruza el umbral. Pero al
segmentar por la **forma interna de la propia vela hasta T=240s**
(`path_efficiency_ratio` calculado solo con las sub-velas 1-4, sin usar
la sub-vela 5 que se solapa con el cierre), aparece un gradiente fuerte
y monótono: trayectoria zigzag −13.1pp (peor que el random walk),
trayectoria mixta +7.1pp, trayectoria monótona +11.4pp (las dos
últimas, q=0.0000, sobreviven FDR y el umbral). Las dos interacciones
que incluyen "trayectoria monótona" (∩ alta volatilidad: +12.8pp;
∩ tendencia local: +13.0pp) confirman el mismo patrón desde un ángulo
independiente.

**Auditoría propia**: al construir las segmentaciones se detectó que el
heatmap de régimen del reporte original de esta misma página (arriba)
usaba una variable con fuga leve (`realized_vol_1m_intracandle`, incluye
la sub-vela del cierre). Corregido aquí con `atr_14` y una versión de
forma interna que solo mira hasta T=240s. No cambia la conclusión
agregada, pero queda documentado por disciplina de auditoría.

**Decisión**: la hipótesis general "001_survival" (sin segmentar) no se
confirma ni se descarta — se **divide**. La forma interna hasta T=240s
pasa a ser su propia hipótesis candidata (Nivel 2, con reservas: ~21
meses de datos no son 3 regímenes macro independientes). Ver `board.md`.

