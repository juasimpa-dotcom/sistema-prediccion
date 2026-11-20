# Sistema inteligente de predicción del rendimiento de ventas

Sistema híbrido neuro-simbólico que predice el rendimiento de ventas y el
cumplimiento de metas de una cadena de retail de alimentos en Bolivia
(pollo, cerdo, embutidos y congelados), y que además razona, recomienda
acciones y explica sus decisiones.

## Estado del proyecto

| Fase | Alcance | Estado |
| ---- | ------- | ------ |
| 1 | Configuración base y generación del dataset | Completada |
| 2 | Preprocesamiento y modelo de Machine Learning | Completada |
| 3 | Sistema experto (reglas y factores de certeza) | Completada |
| 4 | Lógica difusa e integración con el sistema experto | Completada |
| 5 | Búsqueda y planificación de acciones comerciales | Completada |

## Estructura

```text
sistema_prediccion/
  config.py                  # Rutas, semilla, catálogos y parámetros del dominio
  data/
    generar_dataset.py       # Simulador de ventas semanales
    raw/                     # Dataset crudo generado (CSV)
    processed/               # Datasets limpios y transformados
  ml/                        # Preprocesamiento, entrenamiento, evaluación, SHAP
  models/                    # Modelos entrenados (joblib)
  expert_system/             # Memoria de trabajo, reglas, inferencia, difuso
  search/                    # Espacio de estados y planificación
    espacio_estados.py       # Problema abstracto, EstadoPlan, operadores y heurística
    resultado.py             # Resultado común a todos los algoritmos
    no_informada.py          # BFS, DFS, backtracking y costo uniforme
    informada.py             # Greedy, A* y heurística trivial de comparación
    minimax.py               # Competidor que responde, Minimax y alfa-beta
    benchmark.py             # Escenarios, tablas y gráfico comparativo
  api/                       # API FastAPI
  app/                       # Dashboard Streamlit
  notebooks/
    eda_ventas.py            # Análisis exploratorio y figuras
    figuras/                 # Gráficos generados
  tests/                     # Pruebas con pytest
  docs/                      # CommonKADS, informe y artefactos del benchmark
    benchmark_busqueda.csv   # Métricas por algoritmo y escenario
    benchmark_busqueda.md    # Tablas y verificación de optimalidad
    figuras/benchmark_busqueda.png
```

## Requisitos e instalación

- Python 3.11 o superior.
- Crear y activar el entorno virtual:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Uso de la Fase 1

Generar el dataset (comando único, reproducible):

```powershell
python -m data.generar_dataset
```

Opciones disponibles:

```powershell
python -m data.generar_dataset --semilla 2026 --salida data/raw/ventas_semanales.csv
```

Ejecutar el análisis exploratorio (requiere el dataset generado):

```powershell
python -m notebooks.eda_ventas
```

## Uso de la Fase 2

Entrenar, evaluar y guardar el modelo (comando único y reproducible):

```powershell
python -m ml.entrenamiento
```

Opciones disponibles:

```powershell
python -m ml.entrenamiento --semilla 2026 --sin-mlp
```

La convención es que la fila `t` predice las ventas de `t+1`: los lags y las
medias móviles se calculan solo con semanas cerradas, y el calendario (mes,
temporada y feriado) corresponde a la semana objetivo. El corte temporal deja
el entrenamiento hasta el 30 de junio de 2025 y la prueba después. La búsqueda
de hiperparámetros usa `TimeSeriesSplit` y la selección final se hace por MAE
en el conjunto de prueba.

Resultados obtenidos con la semilla 2026:

| Modelo | MAE | RMSE | R2 | MAPE |
| ------ | --- | ---- | -- | ---- |
| Ridge (seleccionado) | 2 298,48 | 3 488,88 | 0,7627 | 15,14 % |
| Gradient Boosting | 2 417,25 | 3 660,97 | 0,7387 | 15,79 % |
| Random Forest | 2 465,73 | 3 587,84 | 0,7490 | 16,29 % |
| MLPRegressor | 2 485,65 | 3 650,86 | 0,7401 | 16,35 % |
| Baseline (semana anterior) | 3 013,05 | 4 496,60 | 0,6058 | 19,71 % |

El modelo seleccionado mejora al baseline en un 23,72 % de MAE. La tabla
comparativa y las figuras quedan en `docs/`; el artefacto `models/predictor_ventas.joblib`
incluye el pipeline, los metadatos y el fondo de referencia para SHAP.

Predicción individual mediante la fachada:

```python
from ml.predictor import PredictorVentas

predictor = PredictorVentas()
resultado = predictor.predecir({"historial": historial_de_la_serie})
print(resultado.valor_predicho, resultado.confianza)
```

## Uso de la Fase 3

El sistema experto es independiente del dominio: el motor solo conoce reglas y
hechos. Las 38 reglas retail (30 crisp + 8 consumidoras de hechos difusos) se
declaran en `expert_system/reglas.json` y se validan al cargarse; también pueden
construirse como lista de objetos `Regla`.

Demostración completa (caso, traza y explicaciones):

```powershell
python -m expert_system.demo
```

Uso programático:

```python
from expert_system.base_conocimientos import BaseConocimientos
from expert_system.demo import hechos_del_caso
from expert_system.motor_inferencia import MotorInferencia
from expert_system.explicacion import explicar

base = BaseConocimientos.desde_json()
memoria = hechos_del_caso()
motor = MotorInferencia(base, memoria)
traza = motor.encadenar_adelante()
accion = memoria.consultar("accion_recomendada")
print(explicar("accion_recomendada", accion.valor, base, traza, memoria).a_texto())
```

El razonamiento inexacto usa factores de certeza MYCIN: `min` para
conjunciones, `max` para disyunciones, producto para propagar una regla y las
fórmulas de combinación para evidencia convergente. El encadenamiento hacia
atrás puede pedir datos al proveedor y explicar cada pregunta.

## Uso de la Fase 4

`expert_system/logica_difusa.py` implementa un sistema Mamdani con scikit-fuzzy.
Las cinco variables lingüísticas de entrada (`cumplimiento_esperado`,
`nivel_stock`, `merma`, `afluencia`, `intensidad_promocion`), las dos salidas
(`nivel_riesgo_incumplimiento`, `urgencia_accion`), sus funciones triangulares
o trapezoidales, las 22 reglas difusas y el mapeo de hechos numéricos viven en
`config.py`. La defuzzificación es por centroide.

**Imprecisión vs. incertidumbre.** La lógica difusa modela conceptos borrosos
(imprecisión): un cumplimiento del 82 % pertenece parcialmente a «bajo» y a
«medio». El factor de certeza modela duda (incertidumbre): «creo con CF 0.8 que
hay stock crítico». La interfaz `Fuzzificador` une ambos mundos: el motor
convierte cada valor numérico en hechos simbólicos cuyo **CF es el grado de
pertenencia**, y después aplica su aritmética MYCIN normal. El motor sigue sin
conocer scikit-fuzzy ni el dominio: basta cualquier objeto que implemente
`variables()`, `etiquetas()`, `pertenencia()`, `fuzzificar()` y `calcular()`.

```python
from expert_system.logica_difusa import SistemaDifuso
from expert_system.motor_inferencia import MotorInferencia

sistema = SistemaDifuso()
resultado = sistema.calcular({
    "cumplimiento_esperado_pct": 82.0,
    "stock_cobertura": 0.12,
    "merma_pct": 14.5,
    "afluencia_rel": 0.72,
    "descuento_pct": 0.0,
})
motor = MotorInferencia(base, memoria, fuzzificador=sistema)
traza = motor.encadenar_adelante()
print(resultado.descripcion(), motor.ultimo_resultado_difuso.hechos)
```

Comandos:

```powershell
python -m expert_system.logica_difusa   # cálculo, hechos simbólicos y gráficos
python -m expert_system.demo            # mismo caso con y sin lógica difusa
```

Los gráficos de las siete funciones de pertenencia se guardan en
`docs/figuras/pertenencia_<variable>.png`. La demo imprime el caso con y sin
difuso y comenta la diferencia de justificación y, si aplica, el cambio de
conclusión.

Calidad y pruebas (incluye cobertura del sistema experto):

```powershell
black --check .
ruff check .
pytest --cov=expert_system --cov=search --cov-report=term-missing
```

## Uso de la Fase 5

`search/espacio_estados.py` define la interfaz genérica `Problema` (estado
inicial, prueba de meta, acciones, sucesor y costo) y su instancia
`ProblemaPlanComercial`. El estado `EstadoPlan` es una `dataclass` inmutable y
hashable con stock, descuento, personal, merma, ventas proyectadas y
presupuesto restante. Los operadores son promoción por niveles, reposición,
reasignación entre sucursales, refuerzo de personal y reducción de merma; sus
efectos y precios se leen de `config.py` y reproducen el modelo de la Fase 1:
la promoción aumenta tráfico y conversión pero baja el precio, la merma reduce
calidad y unidades disponibles, el stock limita las ventas y el personal mejora
la conversión.

```python
from search.espacio_estados import ProblemaPlanComercial
from search.informada import a_estrella

problema = ProblemaPlanComercial(
    meta_bs=24_000.0,
    presupuesto_bs=9_000.0,
    stock_inicial=400,
    merma_inicial=12.0,
)
resultado = a_estrella(problema)
print(resultado.descripcion_plan, resultado.costo, resultado.nodos_expandidos)
```

**Heurística y optimalidad.** Con `déficit = meta - ventas_proyectadas`, `G` la
ganancia máxima de un paso, `c_min` el costo mínimo de un operador y `E` la
máxima eficiencia (Bs de venta por Bs invertido), se usa
`h = max(c_min · ceil(déficit / G), déficit / E)`. Hacen falta al menos
`ceil(déficit / G)` acciones y al menos `déficit / E` bolivianos, así que `h` no
sobreestima. Para cualquier sucesor con costo `c` y ganancia `g` se cumple
`h1(s) - h1(s') <= c_min <= c` y `h2(s) - h2(s') = g / E <= c`; por tanto
`h(s) <= c + h(s')`: es admisible y consistente, y A* con cierre de estados es
óptimo sin reabrir nodos. `heuristica_cero` permite medir cuánto aporta.

Todos los algoritmos devuelven el mismo `Resultado` (`plan`, `costo`,
`nodos_expandidos`, `nodos_generados`, `profundidad`, `tiempo`, `encontrado`).
`costo_uniforme` (Dijkstra) es la referencia óptima independiente usada para
verificar A* en las pruebas. `search/minimax.py` modela la respuesta del
competidor y comprueba que la poda alfa-beta conserva el valor de Minimax.

```powershell
python -m search.benchmark  # escenarios fácil, medio, difícil y sin solución
```

El benchmark guarda `docs/benchmark_busqueda.csv`,
`docs/benchmark_busqueda.md` y `docs/figuras/benchmark_busqueda.png` con nodos
expandidos, costo y tiempo por algoritmo.

## Dataset generado

`data/raw/ventas_semanales.csv` contiene 2 496 filas (104 semanas × 6 sucursales
× 4 categorías) con el siguiente esquema:

| Columna | Descripción |
| ------- | ----------- |
| `fecha_semana` | Lunes que inicia la semana |
| `sucursal` | Sopocachi, El Alto, Miraflores, Calacoto, Obrajes o San Pedro |
| `categoria` | pollo, cerdo, embutidos o congelados |
| `ventas_bs` | Ventas de la semana en bolivianos |
| `unidades_vendidas` | Unidades efectivamente vendidas |
| `precio_promedio` | Precio unitario realizado (con descuento aplicado) |
| `en_promocion` | Indica si la semana tuvo promoción |
| `descuento_pct` | Descuento aplicado (0 si no hubo promoción) |
| `stock_inicial` | Unidades disponibles al inicio de la semana |
| `merma_pct` | Porcentaje de stock perdido por merma |
| `temporada` | alta, media o baja |
| `es_feriado_semana` | La semana contiene un feriado boliviano |
| `temperatura_media` | Temperatura media semanal (°C) |
| `afluencia_clientes` | Clientes que ingresaron a la sucursal |
| `personal_asignado` | Personas asignadas a la categoría |
| `meta_ventas_bs` | Meta semanal fijada antes de vender |
| `cumplimiento_meta_pct` | `ventas_bs / meta_ventas_bs × 100` |

Decisiones de simulación relevantes:

- La meta se fija a partir de la demanda esperada, nunca de las ventas reales,
  para evitar fuga de información en fases posteriores.
- Un 2 % de valores faltantes se inyecta en columnas no críticas después de
  calcular el resultado, de modo que el dataset sirva para practicar limpieza.
- El stock puede limitar las ventas: cuando la demanda supera lo disponible
  (stock menos merma) se pierden unidades, lo que reproduce un quiebre real.
- Aproximadamente 1,5 % de las filas recibe un choque atípico (caída o pico de
  afluencia) que se propaga de forma consistente al resto de las variables.
- Todas las rutas, semillas y constantes viven en `config.py`.
