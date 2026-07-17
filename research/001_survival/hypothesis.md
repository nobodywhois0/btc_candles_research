# 001 · Supervivencia del color

Pre-registrado antes de tocar ningún resultado. Ningún campo de este
archivo se edita después de ver los resultados — cualquier ajuste
posterior invalida el experimento.

## Hipótesis

Si una vela de 5 minutos de BTCUSDT (spot) sigue en el mismo lado del
open a los T segundos desde su apertura, la probabilidad de que cierre
en ese mismo lado es **mayor que la que produciría un random walk puro
con la misma volatilidad realizada** — es decir, hay información
explotable más allá del artefacto mecánico de "queda menos tiempo para
que algo cambie".

## Mecanismo esperado

Micro-momentum de order flow / agotamiento de liquidez de un lado del
libro dentro de la ventana de 5 minutos. Si existe, se espera que la
curva de supervivencia real se separe hacia arriba de la curva de
benchmark de random walk emparejado por volatilidad, de forma creciente
con T.

## Benchmark

**No es 50% plano.** Es una simulación Monte Carlo (200 réplicas) de un
random walk de 5 pasos con volatilidad gaussiana igual a
`realized_vol_1m_intracandle` de cada vela real.

## Criterio de éxito (escrito antes de ver datos)

Para T=240s: `p_hat_real` cae por encima del intervalo [percentil 2.5,
percentil 97.5] de las 200 réplicas del benchmark, con un p-valor
empírico de una cola &lt; 0.01, **y** la diferencia `p_hat_real -
benchmark_mean` en T=240s es ≥ 0.03 (3 puntos porcentuales — tamaño de
efecto mínimo considerado económicamente relevante para este ejercicio
inicial; el umbral definitivo depende del payout real del producto
Up/Down, no fijado todavía).

## Criterio de abandono (escrito antes de ver datos)

`p_hat_real` cae dentro del intervalo del benchmark en T=240s (p-valor
empírico ≥ 0.05), o la diferencia es &lt; 0.01 aunque sea
"significativa" por el tamaño de muestra.

## Qué resultado refutaría la hipótesis

Que la curva real sea indistinguible de la curva de benchmark de random
walk en todos los T, con p-valores empíricos altos y diferencias por
debajo del tamaño de efecto mínimo.

## Datos

BTCUSDT spot, klines de 1 minuto, Binance REST API. Rango: últimos ~2
años hasta la fecha de ejecución. **Limitación documentada**: la
resolución de supervivencia real es de 1 minuto (T ∈
{60,120,180,240,300}s), más gruesa que los 30s originalmente
imaginados — Binance no da klines por debajo de 1m sin datos de trade
a nivel de tick, que quedan fuera del alcance de este experimento.

## Test estadístico

Monte Carlo (no permutation test de shuffle de etiquetas — ver nota
metodológica en el reporte: shufflear la etiqueta final rompería
también la continuidad del camino que genera el artefacto mecánico, y
haría que cualquier dato, incluso puro ruido, pareciera "significativo"
frente a ese null incorrecto). Intervalos de Wilson para las
proporciones reales.

## Número de comparaciones

Este experimento evalúa 5 valores de T (60,120,180,240,300s). Se cuentan
como 5 comparaciones para el conteo acumulado de FDR del proyecto
(actualmente: 1 experimento, 5 comparaciones internas).

## Lockbox

No se toca ningún dato reservado — este es el primer experimento del
proyecto, no hay lockbox definido todavía. Se definirá antes del
próximo checkpoint de decisión.
