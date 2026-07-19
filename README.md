# btc_candles_research

*[Leer en español ↓](#btc_candles_research-español)*

Quantitative research into whether there is an exploitable statistical
edge in trading Up/Down products on BTC based on the direction of the
next 5-minute candle on Binance.

## Purpose

The question this project tries to answer is a single one:

> Is there statistically significant and economically relevant
> evidence that the direction of the next 5-minute BTC/USDT candle is
> predictable beyond what an efficient market would produce?

The project does not start from the premise that the answer is yes.
The goal is to design a process capable of refuting that hypothesis as
fast and as rigorously as it could confirm it — a properly documented
negative result is a valid result.

## Methodology

The project was built in phases, each documented as an independent
deliverable before writing the next line of code:

| Phase | Document | Content |
|---|---|---|
| 1 | [Research design](docs/investigacion-velas-5m-diseno-v0.1.html) | Hypotheses, scientific methodology, biases, temporal validation, alternative problem formulations |
| 1.5 | [Critical review](docs/revision-critica-v0.2.html) | Adversarial audit of the design: what gets cut, what gets prioritized |
| 2 | [Dataset design](docs/dataset-diseno-v0.3.html) | Data dictionary by variable family, table architecture, P0-P3 prioritization |
| 3 | [Platform architecture](docs/arquitectura-plataforma-v0.4.html) | RFC for a full research platform (reference only, not fully implemented) |
| 4 | [Scientific MVP](docs/mvp-cientifico-v0.5.html) | Deliberate scope-down of Phase 3 to the minimum needed to learn fast |
| 5 | [Researcher manual](docs/manual-investigador-v0.6.html) | Binding protocol: pre-registration, multiple-comparisons correction, evidence levels, language discipline |

The guiding principle, inherited from Phase 4, is that **every week
must answer a scientific question about the market, not produce
software for its own sake**. The infrastructure (`lib/`) was only
built to the extent a concrete hypothesis actually needed it.

Every experiment follows the same protocol, fixed before looking at
results: a falsifiable hypothesis, explicit success and abandonment
criteria, a comparison benchmark defined in advance, correction for
the total number of comparisons performed (Benjamini-Hochberg FDR),
and a mandatory "why this result could be false" section before
accepting any positive finding.

That protocol, already abstracted with concrete technical patterns
(benchmark design, leakage prevention, code templates), lives in
[`METODOLOGIA.md`](METODOLOGIA.md) — it's the reference to follow when
opening any new hypothesis, without re-reading all six phases.

## Repository structure

```
btc_candles_research/
├── docs/         Design documents for each phase (HTML)
├── lib/          Minimal pipeline: ingestion, validation, features, statistics, reports
├── research/     One folder per hypothesis (001_survival, ...), each self-contained
├── data/         Raw and processed data (not versioned — regenerable with lib/ingest.py)
├── runs/         Run artifacts (not versioned)
├── notebooks/    Free-form exploration, never a dependency of the rest of the code
└── board.md      Decision board: current state of every hypothesis
```

`data/` and `runs/` are excluded from version control because they are
fully regenerable from the code — there's no point versioning 2 years
of Binance klines when `lib/ingest.py` rebuilds them in minutes.

## How to reproduce

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python3 lib/ingest.py                        # downloads 2 years of BTCUSDT spot 1m
python3 research/001_survival/run.py          # first experiment: color survival
python3 research/001_survival/deepen_001.py   # 001A-G deepening
```

Every run writes its own self-contained HTML report to
`research/<hypothesis>/results/`.

## Partial results

### 001 · Color survival

Question: if a 5-minute candle stays on the same side of its open T
seconds after opening, is the probability that it closes on that side
higher than what a pure random walk with the same volatility would
produce? (Not a flat 50% — any random walk shows a curve rising with T
simply because less time is left for something to change; the correct
benchmark is a Monte Carlo simulation matched to each candle's real
volatility.)

Over 2 years of BTC/USDT spot klines (0 gaps, 0 duplicates, 0 OHLC
inconsistencies), at T=240s: `p_hat_real=0.8712` vs.
`benchmark=0.8525` — an effect of +1.87 percentage points,
statistically distinguishable from the benchmark (empirical p ≈ 0 over
200 replicas) but below the economic-relevance threshold set before
running the experiment (3pp). Result: **Level 1, needs more data** —
neither confirmed nor rejected.

### 001A-G · Where does the effect concentrate?

Deepening pass on the same hypothesis: the aggregate +1.87pp was
broken down into 43 additional comparisons (volatility regime, UTC
hour, day of week, local trend, internal candle shape, and
interactions), FDR-corrected.

The observed evidence is consistent with the effect **not being
uniformly distributed**. By calendar and by aggregate volatility
regime, the effect stays flat in the same ~1-2.5pp band as the
aggregate, without crossing the threshold in any subgroup. But when
segmenting by the **candle's own internal shape up to T=240s** (the
path of the first 4 one-minute sub-bars, without using information
beyond the decision point), a strong, monotonic gradient appears:
zigzag path −13.1pp, mixed path +7.1pp, monotonic path +11.4pp — the
latter two survive the multiple-comparisons correction, and the same
pattern is independently confirmed in two distinct interactions.

Decision: the general hypothesis is neither confirmed nor rejected as
a whole — it **splits**. Internal candle shape up to T=240s becomes a
candidate for its own hypothesis (Level 2), capped by the fact that
the available history (~21 continuous months) still doesn't cover the
independent market regimes needed for full confirmation.

See [board.md](board.md) for the detailed, up-to-date state of every
hypothesis, and `research/001_survival/results/` for the full reports
with charts, tables, and confidence intervals.

## Next steps

Pre-register internal candle shape as its own hypothesis
(`002_shape`), with its own validation lockbox, before touching any
other data subset.

---

# btc_candles_research (Español)

*[Read in English ↑](#btc_candles_research)*

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
