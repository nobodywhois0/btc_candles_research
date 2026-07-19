# Metodología de investigación

Documento de referencia técnica, extraído y abstraído de las fases 1-5
(`docs/`) y de la ejecución real de la hipótesis `001_survival`
(`research/001_survival/`). No narra lo que se hizo — define cómo se
hace la siguiente hipótesis. Léase antes de abrir `002_shape`,
`003_microstructure`, `004_orderflow`, `005_entropy` o cualquier línea
de investigación nueva.

Para la disciplina ética/psicológica completa (sesgos, lenguaje,
autoengaño) ver [`docs/manual-investigador-v0.6.html`](docs/manual-investigador-v0.6.html) —
este documento la resume en la medida en que es operativa, pero no la
reemplaza.

---

## 0. Principio rector

El objetivo no es confirmar que hay un edge. Es diseñar el proceso más
rápido posible para **refutar** esa hipótesis, y solo aceptarla si
sobrevive el intento serio de refutación. Un resultado negativo,
documentado con el mismo rigor que uno positivo, es un resultado
completo — no una investigación fallida.

Cada decisión metodológica de este documento existe para resolver una
tensión concreta entre dos fuerzas: la que empuja a encontrar algo
(porque se invirtió tiempo, porque hay presión de resultados, porque
un patrón que "casi" cruza el umbral se siente como un descubrimiento)
y la que exige que un hallazgo sobreviva escrutinio antes de gastar un
solo dólar operándolo.

---

## 1. Ciclo de vida de un experimento

```
1. Pre-registro         hypothesis.md — hipótesis, benchmark, criterios, ANTES de tocar datos
2. Checklist previo      §9 de este documento
3. Ejecución             run.py — carga → valida → features → test → reporte
4. Checklist posterior   §10 de este documento
5. Abogado del diablo    §12 — obligatorio antes de aceptar cualquier resultado positivo
6. Registro obligatorio  formato fijo, §11 — se escribe funcione o no el experimento
7. Nivel de evidencia    §8 — asignación por regla, no por impresión
8. Actualizar board.md   nunca a mano — reflejar exactamente el resultado
9. (Opcional) Profundizar §7 — el patrón "00XA-G" cuando el resultado agregado es ambiguo
```

Ninguna etapa se salta. Si el paso 1 no está completo, el paso 3 no
se ejecuta — el checklist previo (§9) existe exactamente para hacer
cumplir esto.

---

## 2. Pre-registro (`hypothesis.md`)

Cada hipótesis nueva empieza con un archivo `hypothesis.md` que no se
edita después de ver resultados. Estructura fija (ver
`research/001_survival/hypothesis.md` como precedente real):

```markdown
# 00X · <nombre corto>

## Hipótesis
Una frase falsable. Debe poder ser verdadera o falsa, no ambigua.

## Mecanismo esperado
Por qué, en términos de microestructura/estadística/economía, se
esperaría que esto sea cierto si lo es. Sin mecanismo, no hay forma
de distinguir un hallazgo real de un patrón espurio del mismo tamaño.

## Benchmark
Contra qué se compara — nunca "cero" ni "50%" por defecto (ver §3).

## Criterio de éxito (escrito antes de ver datos)
Números exactos: estadístico, umbral de significancia, tamaño de
efecto mínimo. "Se ve bien" no es un criterio.

## Criterio de abandono (escrito antes de ver datos)
Igual de exacto que el de éxito. Sin esto, ningún resultado negativo
se puede declarar limpiamente negativo.

## Qué resultado refutaría la hipótesis
Una frase. Si no se puede escribir, la hipótesis no está bien
formulada todavía.

## Datos
Universo, rango, resolución real disponible (declarar explícitamente
cualquier limitación — p. ej. resolución de 1 minuto cuando el diseño
ideal pedía 30s).

## Test estadístico
Cuál, y por qué ese y no otro (ver §5).

## Número de comparaciones
Cuántas pruebas suma este experimento al conteo acumulado de FDR del
proyecto (ver §5.3).

## Lockbox
Confirmar explícitamente que no se toca el lockbox reservado (ver §6).
```

Regla dura: si después de correr el experimento se quiere cambiar
cualquier campo de este archivo, el experimento se descarta y se
vuelve a pre-registrar como uno nuevo. No se edita el original.

---

## 3. Diseño del benchmark — la lección central del proyecto

**El error más caro que se puede cometer en este proyecto es comparar
contra un benchmark trivial.**

Precedente concreto: en `001_survival`, la probabilidad cruda de que
una vela conserve su lado a T=240s es 0.8712. Comparado contra 50%,
eso parece un edge enorme. Pero **cualquier random walk puro, sin
ninguna información direccional, produce una curva de "supervivencia"
ascendente con T** — simplemente porque queda menos tiempo para que
algo cambie. El benchmark correcto no es una constante: es una
simulación del proceso nulo más parecido posible a los datos reales
en todo lo que no es la hipótesis que se está probando.

### Procedimiento general

1. Identificar qué parámetros de nulo (volatilidad, tendencia,
   autocorrelación de corto plazo) podrían por sí solos producir un
   patrón parecido al que se busca, sin que exista información real.
2. Simular ese proceso nulo **emparejado observación por observación**
   con esos parámetros — no con un promedio global. En `001_survival`,
   cada vela real tiene su propia volatilidad realizada
   (`realized_vol_1m_intracandle`), y la simulación usa exactamente
   esa sigma para el random walk de esa vela específica
   (`lib/stats.py::simulate_random_walk_sides`).
3. Repetir la simulación N veces (Monte Carlo, 200-300 réplicas en la
   práctica de este proyecto) para obtener una distribución del
   estadístico bajo el nulo, no un solo valor puntual.
4. Comparar el resultado real contra esa distribución completa (media
   + percentiles 2.5/97.5), nunca contra un solo número de referencia.

```python
# lib/stats.py — patrón general, reutilizable para cualquier hipótesis
# que necesite un benchmark "¿esto es más de lo que el ruido produciría?"
def simulate_random_walk_sides(sigma, rng, t_list):
    steps = rng.normal(loc=0.0, scale=sigma.reshape(-1, 1), size=(len(sigma), len(t_list)))
    cum_log_return = np.cumsum(steps, axis=1)
    return np.sign(cum_log_return)
```

### Regla de aplicación a experimentos futuros

Antes de escribir el test estadístico de cualquier hipótesis nueva,
responder por escrito: **"¿qué produciría este mismo estadístico si
la hipótesis fuera falsa pero todo lo demás sobre el mercado (volumen,
volatilidad, hora) fuera idéntico?"** Esa respuesta, simulada, es el
benchmark. Si la respuesta es "50%" o "cero", probablemente se está
subestimando el efecto trivial y hay que reconsiderar.

---

## 4. Prevención de fuga de información (leakage)

### Regla general

> Antes de usar una variable X para explicar o segmentar una decisión
> tomada en el instante T, preguntar: **¿el cálculo de X usa algún
> dato con timestamp posterior a T?** Si sí, X puede describir la vela
> a posteriori (valor diagnóstico) pero **no puede usarse como
> variable de condicionamiento en tiempo real**.

### Caso real detectado y corregido en este proyecto

Durante la profundización `001A-G` se auditó el propio reporte base de
`001_survival` y se encontró que el heatmap de régimen de volatilidad
usaba `realized_vol_1m_intracandle` — una variable calculada con las
5 sub-velas completas de la vela, **incluida la última, que coincide
con el cierre**. Usar esa variable para clasificar "régimen" en una
decisión tomada en T=240s es fuga: en T=240s todavía no se conoce la
sub-vela 5.

Corrección aplicada, y patrón a repetir:

| Necesidad | Variable con fuga | Variable corregida | Por qué la corregida no filtra |
|---|---|---|---|
| Régimen de volatilidad conocible en T | `realized_vol_1m_intracandle` (usa las 5 sub-velas) | `atr_14` | Rolling de velas **ya cerradas**, ninguna posterior a la vela actual |
| Forma interna hasta T=240s | `path_efficiency_ratio` (usa las 5 sub-velas) | `path_efficiency_240` calculada solo con sub-velas 1-4 | Se trunca explícitamente antes del cálculo — nunca toca la sub-vela 5 |
| Tendencia local | — | `trend_return_20` = retorno log de 20 velas **pasadas** | Usa `close.shift(20)`, estrictamente anterior |

Nota importante: usar una variable "con fuga" **dentro del motor de
benchmark** (p. ej. `realized_vol_1m_intracandle` como sigma de la
simulación Monte Carlo) sigue siendo correcto — ahí no se usa como
señal operable, se usa para emparejar volatilidad estadísticamente.
La fuga solo importa cuando la variable se presenta implícitamente
como algo que un operador podría conocer en tiempo real.

### Checklist rápido de auditoría de leakage para cualquier feature nueva

- [ ] ¿Se calcula con datos estrictamente anteriores al instante de
      decisión, o incluye la propia vela/ventana que se está evaluando?
- [ ] Si incluye la vela actual, ¿qué sub-parte exactamente, y esa
      sub-parte ya ocurrió antes del punto de decisión?
- [ ] ¿Se usa como variable de condicionamiento (implica "esto se
      pudo saber antes") o como variable diagnóstica (solo para
      entender el resultado después)? Declarar explícitamente cuál.

---

## 5. Motor estadístico

### 5.1 Intervalos de confianza — Wilson

Para cualquier proporción (p. ej. "P(cierra en el mismo lado)"), usar
el intervalo de Wilson, no el normal aproximado — es más estable con
proporciones cercanas a 0 o 1 y con muestras moderadas.

```python
# lib/stats.py::wilson_ci(successes, n, alpha=0.05)
lo, hi = scipy_stats.binomtest(successes, n).proportion_ci(
    confidence_level=1 - alpha, method="wilson"
)
```

### 5.2 Por qué NO usar un permutation test de shuffle de etiquetas aquí

Sería el default razonable en la mayoría de contextos, pero **no** en
un experimento de supervivencia intra-vela: barajar la etiqueta final
manteniendo la variable de "lado en T" rompería exactamente la
continuidad del camino de precio que genera el artefacto mecánico
descrito en §3. El resultado sería que hasta datos de ruido puro
parecerían "significativos" frente a ese null incorrecto. Por eso
`lib/stats.py::random_walk_benchmark` usa Monte Carlo paramétrico
(simular el proceso, no barajar las etiquetas) — la elección del test
estadístico depende de qué mecanismo genera el patrón que se quiere
descartar, no es una elección genérica.

Regla general: antes de elegir un test, preguntar qué tipo de
dependencia estructural podría producir el patrón observado por
razones triviales, y verificar que el test elegido no la destruya
accidentalmente (invalidando la comparación) ni la ignore (inflando
falsos positivos).

### 5.3 Corrección por comparaciones múltiples — Benjamini-Hochberg (FDR)

Todo proyecto con más de una hipótesis, y toda hipótesis con más de
un subgrupo de análisis, acumula un conteo de comparaciones que debe
corregirse. Implementación de referencia:

```python
def benjamini_hochberg(pvals: np.ndarray) -> np.ndarray:
    n = len(pvals)
    order = np.argsort(pvals)
    ranked = pvals[order]
    q_raw = ranked * n / (np.arange(n) + 1)
    q_monotone = np.minimum.accumulate(q_raw[::-1])[::-1]
    q = np.empty(n)
    q[order] = np.clip(q_monotone, 0, 1)
    return q
```

Reglas de aplicación:

- El conteo es **acumulado por hipótesis**, no por corrida. `001` lleva
  48 comparaciones acumuladas (5 de la corrida base + 43 de `001A-G`).
  Al abrir `002_shape`, su propio conteo empieza en cero, pero si más
  adelante se comparan hipótesis entre sí, el conteo relevante es el
  del conjunto completo evaluado.
- La decisión final usa el **q-valor** (p-valor corregido), nunca el
  p-valor crudo, salvo en la primerísima observación exploratoria
  (Nivel 1, ver §8) antes de que exista corrección que aplicar.
- El número de réplicas Monte Carlo limita la resolución del p-valor
  empírico (con 300 réplicas, la resolución mínima es 1/300≈0.0033).
  Si un resultado queda cerca del umbral post-FDR, subir las réplicas
  antes de decidir, no forzar la decisión con resolución insuficiente.

### 5.4 Significancia vs. relevancia — dos condiciones, no una

Ningún resultado se acepta por significancia estadística sola. La
regla operativa usada en `001_survival` y heredable a cualquier
hipótesis:

```python
significativo = (q_valor < ALPHA) and (effect_size >= EFFECT_SIZE_MIN)
```

`ALPHA` y `EFFECT_SIZE_MIN` se fijan en el pre-registro (§2), a partir
de razonamiento económico (punto de equilibrio del producto que se
quiere operar), nunca copiados mecánicamente de otra hipótesis sin
volver a justificarlos.

---

## 6. Lockbox y validación temporal

- Se reserva un tramo final del histórico (90 días en `001_survival`)
  **antes** de correr cualquier análisis exploratorio.
- Se prohíbe leer, describir o graficar ese tramo hasta la validación
  final de una hipótesis que ya alcanzó Nivel 3.
- Todo desarrollo exploratorio (incluida la profundización §7) ocurre
  exclusivamente sobre el conjunto de desarrollo (`df_dev`), nunca
  sobre el lockbox.
- Mirar el lockbox una sola vez, aunque sea "solo para explorar",
  quema ese lockbox — se reserva uno nuevo y el incidente se
  documenta.

---

## 7. Profundización de una hipótesis (patrón "00XA-G")

Cuando el resultado agregado de una hipótesis es ambiguo (ni claramente
confirmado ni claramente rechazado — Nivel 1), antes de abandonarla o
subirla de nivel, se pregunta: **¿el efecto está distribuido
uniformemente o concentrado en un contexto específico?** El patrón
aplicado en `001A-G` es reutilizable como procedimiento estándar.

### 7.1 Ejes de estratificación estándar

| Eje | Cómo se construye sin fuga | Ejemplo en `001A-G` |
|---|---|---|
| Régimen de una variable de contexto | Terciles/cuantiles de una variable conocida **antes** del punto de decisión | `atr_14` en terciles (001A) |
| Calendario | Determinístico, nunca tiene fuga por construcción | Hora UTC (001B), día de la semana (001C) |
| Tendencia local | Retorno sobre una ventana de lookback estrictamente pasada, con banda muerta = `sigma_1bar × √lookback` (el umbral de "esto es ruido puro bajo un random walk") | `trend_return_20` (001D) |
| Estructura interna parcial | Solo hasta el instante de decisión, nunca la vela completa (§4) | `path_efficiency_240` (001E) |
| Interacciones | Un puñado (2-4) de celdas **preespecificadas por motivación teórica antes de ejecutar**, nunca elegidas después de ver el heatmap completo | 001G: 3 celdas, no 24×3 combinaciones |

### 7.2 Por qué las interacciones se preespecifican

Elegir la celda "más prometedora" después de ver todos los resultados
es el sesgo de Texas sharpshooter: dibujar el blanco alrededor de
donde cayó el tiro. La disciplina es escribir, antes de correr nada,
la motivación teórica de cada celda que se va a probar, y limitarse a
esas — no fuerza bruta sobre el producto cartesiano completo de ejes.

### 7.3 Cada subgrupo es su propia prueba, con su propio benchmark

`run_group_test(df_subset, label)` en `research/001_survival/deepen_001.py`
reutiliza exactamente `survival_curve` y `random_walk_benchmark` de
`lib/stats.py` sobre el subconjunto — el benchmark Monte Carlo queda
automáticamente emparejado a la volatilidad real de ese subgrupo sin
ningún cambio de código. Grupos con menos de ~300 observaciones se
marcan explícitamente como de potencia insuficiente en vez de forzar
una conclusión.

### 7.4 Veredicto automático — regla, no impresión visual

```
n_significativos = comparaciones que sobreviven FDR + umbral de efecto
n_tested          = comparaciones totales evaluadas

si n_significativos == 0                                  → permanece en observación
si 0 < n_significativos < 0.5 × n_tested                  → dividir en hipótesis más específica
si n_significativos >= 0.5 × n_tested                      → sube de nivel (con reservas de §8)
```

El umbral 0.5 es un default razonable, no un dogma — pero debe fijarse
**antes** de ver los resultados de la profundización, igual que
cualquier otro criterio de este documento.

---

## 8. Niveles de evidencia

| Nivel | Nombre | Criterio objetivo de entrada |
|---|---|---|
| 0 | Idea | `hypothesis.md` completo, ningún dato tocado |
| 1 | Observación | Checklist previo (§9) completo, primera corrida documentada, sin corrección FDR todavía |
| 2 | Hipótesis apoyada | Sobrevive test individual con FDR preliminar, en una sola ventana/régimen |
| 3 | Evidencia robusta | Estable en **≥3 regímenes/años independientes**, sobrevive el abogado del diablo (§12), tamaño de efecto documentado |
| 4 | Edge validado | Todo lo anterior + EV neto positivo con IC que excluye cero, validado sobre el lockbox nunca antes tocado |

Reglas:

- Subir de nivel exige cumplir el criterio objetivo del nivel
  siguiente — nunca por consenso subjetivo.
- Bajar de nivel es inmediato ante cualquier violación detectada en
  auditoría, sin importar cuánto tiempo llevaba arriba.
- **Techo estructural**: con un histórico de ~21 meses continuos (el
  caso actual de `001_survival`/`001E`), ningún resultado, por bueno
  que se vea, puede superar Nivel 2 — Nivel 3 exige 3 regímenes macro
  independientes que ese rango de fechas todavía no cubre. Esto se
  declara explícitamente en cualquier resultado que se vea fuerte pero
  no tenga cobertura temporal suficiente.

---

## 9. Checklist previo a ejecutar un experimento

- [ ] Hipótesis escrita como frase falsable, con mecanismo esperado
- [ ] Criterio de éxito exacto (número, no impresión)
- [ ] Criterio de abandono exacto
- [ ] Benchmark definido explícitamente (§3) — nunca 0/50% por defecto
- [ ] Test estadístico elegido y justificado antes de ver datos (§5.2)
- [ ] Tamaño de efecto mínimo económicamente relevante, no solo p-valor
- [ ] Número de comparaciones que suma al conteo FDR del proyecto
- [ ] Ventana de datos exacta, confirmando que no toca el lockbox
- [ ] Ruta de resultados fijada de antemano
- [ ] Resultado que refutaría la hipótesis, escrito en una frase

## 10. Checklist posterior a un experimento

- [ ] ¿Hay leakage? (auditoría §4 sobre cada feature nueva usada)
- [ ] ¿Hay overfitting? (brecha in-sample vs. walk-forward)
- [ ] ¿Se recalculó el q-valor con el conteo FDR actualizado? (§5.3)
- [ ] ¿Hay estabilidad temporal? (≥3 regímenes, o se declara el techo del §8)
- [ ] ¿El efecto es económicamente relevante, no solo estadístico? (§5.4)
- [ ] ¿Podría explicarse por el benchmark correcto, no uno trivial? (§3)
- [ ] ¿Sobrevive el abogado del diablo? (§12)
- [ ] ¿Se documentó en el registro obligatorio (§11), funcione o no?
- [ ] ¿Se actualizó `board.md`?

---

## 11. Registro obligatorio — formato fijo

Todo experimento, sin excepción, produce este registro (implementado
como el diccionario `registro` en `run.py`/`deepen_001.py`, volcado
al reporte HTML vía `lib/report.py::make_report`):

```
hipotesis:              una frase falsable
fecha_de_pre_registro:   antes de tocar datos de prueba
fecha_de_ejecucion:      —
resultado_esperado:      escrito ANTES de ver datos
resultado_observado:     —
benchmark_usado:         qué se simuló y por qué (§3)
estadistico_y_p_valor:   con corrección FDR aplicada (§5.3)
tamano_del_efecto:       número, en las unidades que importan económicamente
interpretacion:          lenguaje de §13 — nunca "descubrimos que..."
problemas_encontrados:   —
limitaciones:            —
nivel_de_evidencia:      0-4, por regla (§8)
decision:                continuar / abandonar / requiere más datos / dividir
proximo_paso:            concreto, accionable
responsable:             fecha (sin narrar "sesión" ni proceso de generación)
```

---

## 12. El abogado del diablo

Sección obligatoria antes de aceptar cualquier resultado positivo,
titulada exactamente: **"Las cinco mejores razones por las que este
resultado probablemente sea falso."** Deben ser específicas al
resultado concreto — no genéricas ni reciclables entre experimentos.
Categorías que casi siempre aplican y vale la pena revisar primero:

1. ¿El benchmark pudo estar mal calibrado (supuestos de la simulación
   que no se cumplen exactamente, p. ej. colas más gruesas que una
   gaussiana)?
2. ¿La resolución de datos disponible es más gruesa que la ideal, y
   ese artefacto de discretización explica parte del efecto?
3. ¿El periodo cubierto cruza suficientes regímenes, o el resultado
   podría ser específico de uno solo?
4. ¿La resolución del test (réplicas Monte Carlo, tamaño de muestra
   del subgrupo) es suficiente para el umbral que se está aplicando?
5. ¿El número de comparaciones realizadas (incluida la elección de
   qué comparar) está correctamente contado en el FDR?

---

## 13. Disciplina de lenguaje

| Prohibido | Obligatorio |
|---|---|
| "El modelo descubrió X" | "La evidencia observada es consistente con X" |
| "Los datos demuestran X" | "Los datos disponibles no refutan X" |
| "Existe un patrón" | "Se observa una regularidad que no ha sido refutada por las pruebas aplicadas" |
| "Esto prueba que hay un edge" | "La hipótesis de edge no ha sido refutada tras N pruebas; nivel de evidencia: X" |
| "Confirmamos que no hay memoria" | "No encontramos evidencia de memoria con el poder estadístico disponible" |
| "Esto es obvio en retrospectiva" | Prohibida sin excepción — es la firma verbal del sesgo de retrospección |

Ninguna hipótesis se "prueba". Solo se falla en refutarla. El lenguaje
debe reflejar esa asimetría siempre.

---

## 14. Catálogo de sesgos — versión operativa

Lista completa con detección/mitigación/auditoría en
`docs/manual-investigador-v0.6.html`, Parte 5. Los que más
probablemente aparecen en el trabajo técnico de este proyecto
específicamente:

| Sesgo | Dónde aparece aquí específicamente |
|---|---|
| Data snooping | Generar una hipótesis mirando un gráfico y probarla en la misma ventana que la inspiró |
| Texas sharpshooter | Elegir la celda de interacción "ganadora" después de ver el heatmap completo (§7.2) |
| HARKing | Ajustar `EFFECT_SIZE_MIN` o el benchmark después de ver que el resultado casi cruza el umbral |
| Optimizer's curse | Reportar la métrica de la mejor configuración probada sin re-evaluarla en datos frescos |
| Leakage silencioso | Usar una feature de la vela completa para condicionar una decisión de mitad de vela (§4) |
| Regime blindness | Declarar Nivel 3-4 sin haber cruzado 3 regímenes independientes (§8) |

---

## 15. Árboles de decisión

**Señal interesante aparece** → ¿pre-registrada antes de verla? No:
re-registrar y probar en datos frescos. Sí → ¿sobrevive checklist
posterior (§10)? No: "evidencia débil", no se borra. Sí → ¿sobrevive
abogado del diablo (§12)? No: degradar un nivel. Sí → ¿económicamente
relevante neto de costos? No: tope Nivel 2. Sí → subir de nivel y
actualizar `board.md`.

**Señal desaparece** → ¿fue en el lockbox o en validación regular?
Lockbox: aceptar y degradar a "rechazada" sin excepción. Regular →
¿cambió el régimen de mercado? Sí: "evidencia condicionada a
régimen", tope Nivel 3. No: sospechar leakage, re-auditar §4 y §10.

**Señal inestable entre folds** → ¿la muestra por fold es suficiente?
No: "requiere más datos" (Nivel 2), no es evidencia en ningún sentido.
Sí → ¿correlaciona con régimen/volatilidad/liquidez? Sí: reformular
como hipótesis condicional a ese régimen. No: tratar como ruido,
degradar con fecha de revisión futura.

**Contradice otra hipótesis ya aceptada** → ¿mismo periodo/definición
de datos? No: no es contradicción real, es diferencia de muestra —
documentar, no forzar reconciliación. Sí → ¿alguna de las dos no pasó
el checklist completo? Sí: esa es la sospechosa por defecto. No
(ambas limpias): tratar la contradicción como información real sobre
un régimen no identificado — abrir una hipótesis nueva sobre por qué
contradicen, nunca elegir la que "gusta más".

---

## 16. Estructura de una hipótesis nueva

```
research/00X_<nombre>/
├── hypothesis.md      # plantilla de §2
├── run.py              # carga → valida → features → test → reporte
├── results/
│   ├── report.html        # generado por lib/report.py::make_report
│   ├── figures/
│   └── summary.json         # estado, nivel, métricas clave — alimenta board.md
└── README.md                # notas del investigador, actualizadas después de cada corrida
```

Regla de independencia: ninguna carpeta de `research/` importa de
otra. Solo de `lib/` (funciones puras) y de `data/` (solo lectura). Si
una hipótesis necesita algo genuinamente reutilizable, se agrega a
`lib/`, nunca se copia entre carpetas de hipótesis.

Si una hipótesis se profundiza (patrón §7), su script vive junto al
original: `research/00X_<nombre>/deepen_00X.py`, resultados en
`results/deepen/`, sin tocar los resultados de la corrida base.

---

## 17. Plantillas listas para copiar

### Umbral de tendencia sin fuga (banda muerta basada en ruido)

```python
log_close = np.log(df["close"].to_numpy())
lookback = 20  # ajustar por hipótesis
trend_return = log_close - np.concatenate([np.full(lookback, np.nan), log_close[:-lookback]])
r1 = np.diff(log_close, prepend=np.nan)
sigma_1bar = np.nanstd(r1)
deadband = sigma_1bar * np.sqrt(lookback)
trend = np.where(np.isnan(trend_return), "sin_dato",
         np.where(trend_return > deadband, "alcista",
         np.where(trend_return < -deadband, "bajista", "lateral")))
```

### Prueba de un subgrupo contra su propio benchmark Monte Carlo

```python
def run_group_test(df_subset, label, n_reps=300, seed=42, decision_t=240):
    if len(df_subset) < 300:
        return {"label": label, "potencia_insuficiente": True}
    curve = survival_curve(df_subset)
    bench, p_values = random_walk_benchmark(df_subset, n_reps=n_reps, seed=seed)
    real = curve.set_index("T_seconds").loc[decision_t, "p_same_side_at_close"]
    bmk = bench.set_index("T_seconds").loc[decision_t, "p_same_side_benchmark_mean"]
    return {"label": label, "n": len(df_subset), "effect_size": real - bmk,
            "p_empirico": p_values[decision_t]}
```

### Fila de `board.md`

```markdown
| <hipótesis> | <estado> | <nivel> | <evidencia clave, con números> | <próximo paso concreto> |
```

Estados válidos: `Confirmada`, `Evidencia débil`, `Requiere más
datos`, `Rechazada` — definidos por regla en §8, nunca a mano.

---

## 18. Checklist definitivo — resumen ejecutivo

Antes de declarar cualquier hipótesis confirmada, verificar las siete
preguntas que resumen todo este documento:

1. ¿El benchmark es una simulación del proceso nulo correcto, no una
   constante trivial? (§3)
2. ¿Ninguna variable de condicionamiento usa datos posteriores al
   punto de decisión? (§4)
3. ¿El p-valor reportado está corregido por el conteo total de
   comparaciones del proyecto, no solo de este experimento? (§5.3)
4. ¿El efecto es económicamente relevante, no solo estadísticamente
   distinguible de cero? (§5.4)
5. ¿Es estable en al menos 3 regímenes/años independientes, o se
   declaró explícitamente el techo de nivel por falta de cobertura? (§8)
6. ¿Sobrevivió un intento serio y específico de encontrar por qué es
   falso? (§12)
7. ¿Está documentado en el formato fijo, con el lenguaje correcto,
   independientemente de si el resultado fue positivo? (§11, §13)

Si alguna respuesta es no, el nivel de evidencia se limita en
consecuencia — no se fuerza una conclusión.
