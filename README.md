# btc_candles_research

Investigación cuantitativa sobre si existe una ventaja estadística
explotable al operar productos Up/Down sobre BTC sobre la dirección
de la siguiente vela de 5 minutos en Binance.

## Propósito

La pregunta que este proyecto intenta responder es una sola:

> ¿Existe evidencia estadísticamente significativa y económicamente
> relevante de que la dirección de la próxima vela de 5 minutos de
> BTC/USDT sea predecible más allá de lo que produciría un mercado
> eficiente?

No se parte de la premisa de que la respuesta sea sí. El objetivo es
diseñar un proceso capaz de refutar esa hipótesis tan rápido y con
tanto rigor como de confirmarla — un resultado negativo, documentado
correctamente, es un resultado válido.

## Metodología

El proyecto se construyó en fases, cada una documentada como un
entregable independiente antes de escribir la siguiente línea de
código:

| Fase | Documento | Contenido |
|---|---|---|
| 1 | [Diseño metodológico](docs/investigacion-velas-5m-diseno-v0.1.html) | Hipótesis, metodología científica, sesgos, validación temporal, formulaciones alternativas del problema |
| 1.5 | [Revisión crítica](docs/revision-critica-v0.2.html) | Auditoría adversarial del diseño: qué se elimina, qué se prioriza |
| 2 | [Diseño del dataset](docs/dataset-diseno-v0.3.html) | Diccionario de datos por familia de variables, arquitectura de tablas, priorización P0-P3 |
| 3 | [Arquitectura de la plataforma](docs/arquitectura-plataforma-v0.4.html) | RFC de una plataforma de investigación completa (referencia, no implementada en su totalidad) |
| 4 | [MVP científico](docs/mvp-cientifico-v0.5.html) | Reducción deliberada de la Fase 3 a lo mínimo necesario para aprender rápido |
| 5 | [Manual del investigador](docs/manual-investigador-v0.6.html) | Protocolo obligatorio: pre-registro, corrección por comparaciones múltiples, niveles de evidencia, disciplina de lenguaje |

El principio rector, heredado de la Fase 4, es que **cada semana debe
responder una pregunta científica sobre el mercado, no producir
software por sí mismo**. La infraestructura (`lib/`) se construyó
solo en la medida en que una hipótesis concreta la necesitaba.

Cada experimento sigue el mismo protocolo, fijado antes de ver
resultados: hipótesis falsable, criterio de éxito y de abandono
explícitos, benchmark comparativo definido de antemano, corrección
por el número total de comparaciones realizadas (FDR de
Benjamini-Hochberg), y una sección obligatoria de "por qué este
resultado podría ser falso" antes de aceptar cualquier hallazgo
positivo.

Ese protocolo, ya abstraído y con los patrones técnicos concretos
(diseño del benchmark, prevención de fuga, plantillas de código) está
en [`METODOLOGIA.md`](METODOLOGIA.md) — es la referencia a seguir para
abrir cualquier hipótesis nueva, sin tener que releer las seis fases.

## Estructura del repositorio

```
btc_candles_research/
├── docs/         Documentos de diseño de cada fase (HTML)
├── lib/          Pipeline mínimo: descarga, validación, features, estadística, reportes
├── research/     Una carpeta por hipótesis (001_survival, ...), cada una autocontenida
├── data/         Datos crudos y procesados (no versionado — regenerable con lib/ingest.py)
├── runs/         Artefactos de ejecuciones (no versionado)
├── notebooks/    Exploración libre, nunca dependencia del resto del código
└── board.md      Tablero de decisión: estado actual de cada hipótesis
```

`data/` y `runs/` están excluidos del control de versiones porque son
completamente regenerables a partir del código — no tiene sentido
versionar 2 años de klines de Binance cuando `lib/ingest.py` los
reconstruye en minutos.

## Cómo reproducir

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python3 lib/ingest.py                        # descarga 2 años de BTCUSDT spot 1m
python3 research/001_survival/run.py          # primer experimento: supervivencia del color
python3 research/001_survival/deepen_001.py   # profundización 001A-G
```

Cada corrida escribe su propio reporte HTML autocontenido en
`research/<hipótesis>/results/`.

## Resultados parciales

### 001 · Supervivencia del color

Pregunta: si una vela de 5 minutos sigue en el mismo lado del open a
los T segundos de su apertura, ¿la probabilidad de que cierre en ese
lado es mayor que la que produciría un random walk puro con la misma
volatilidad? (No 50% plano — cualquier random walk muestra una curva
ascendente con T solo porque queda menos tiempo para que algo
cambie; el benchmark correcto es una simulación Monte Carlo
emparejada por volatilidad real de cada vela.)

Sobre 2 años de klines de BTC/USDT spot (0 gaps, 0 duplicados, 0
inconsistencias OHLC), en T=240s: `p_hat_real=0.8712` vs.
`benchmark=0.8525` — un efecto de +1.87 puntos porcentuales,
estadísticamente distinguible del benchmark (p empírico ≈ 0 sobre
200 réplicas) pero por debajo del umbral de relevancia económica
fijado antes de correr el experimento (3pp). Resultado: **Nivel 1,
requiere más datos** — ni se confirma ni se descarta.

### 001A-G · ¿Dónde se concentra el efecto?

Profundización sobre la misma hipótesis: el +1.87pp agregado se
desagregó en 43 comparaciones adicionales (régimen de volatilidad,
hora UTC, día de la semana, tendencia local, forma interna de la
vela, e interacciones), corregidas por FDR.

La evidencia observada es consistente con que el efecto **no está
distribuido uniformemente**. Por calendario y por régimen de
volatilidad agregado, el efecto se mantiene plano en la misma banda
de ~1-2.5pp del agregado, sin cruzar el umbral en ningún subgrupo.
Pero al segmentar por la **forma interna de la propia vela hasta
T=240s** (trayectoria de las primeras 4 sub-velas de 1 minuto, sin
usar información posterior al punto de decisión) aparece un
gradiente fuerte y monótono: trayectoria en zigzag −13.1pp,
trayectoria mixta +7.1pp, trayectoria monótona +11.4pp — estas dos
últimas sobreviven la corrección por comparaciones múltiples, y el
mismo patrón se confirma de forma independiente en dos interacciones
distintas.

Decisión: la hipótesis general no se confirma ni se descarta como un
todo — **se divide**. La forma interna de la vela hasta T=240s pasa a
ser candidata a su propia hipótesis (Nivel 2), con el techo puesto en
que el historial disponible (~21 meses continuos) todavía no cubre
los regímenes de mercado independientes necesarios para una
confirmación completa.

Ver [board.md](board.md) para el estado detallado y actualizado de
cada hipótesis, y `research/001_survival/results/` para los reportes
completos con gráficas, tablas e intervalos de confianza.

## Próximos pasos

Pre-registrar la forma interna de la vela como hipótesis propia
(`002_shape`), con su propio lockbox de validación, antes de tocar
cualquier otro subconjunto de datos.
