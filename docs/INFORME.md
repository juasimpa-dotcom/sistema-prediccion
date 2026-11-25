# Informe ejecutivo: qué acciones ejecutar esta semana

**Sistema inteligente de predicción de ventas y apoyo a la decisión**

- Fecha: 24 de noviembre de 2026
- Audiencia: dueño o encargado de sucursal
- Pregunta que responde el sistema: **¿qué hacemos esta semana?**
- Documento técnico completo: [`INFORME_TECNICO.md`](INFORME_TECNICO.md)
- Guion técnico de 10 minutos: [`guion_demo.md`](guion_demo.md)

---

## 1. Resumen ejecutivo

El dashboard ya no empieza explicando cómo funciona el sistema. Empieza
diciendo **qué hacer**. En la primera pantalla aparecen, en este orden:

1. **La decisión**: una a tres acciones concretas, su inversión estimada y el
   motivo principal en una frase.
2. **Cuatro cifras de contexto**: ventas proyectadas, meta, cumplimiento y
   riesgo.
3. **Una frase de lectura rápida** que conecta esas cifras con la decisión.
4. **Tres apartados cerrados** con el detalle: por qué se decidió eso, cómo se
   exploraron las opciones y comparación técnica. Este último tiene tres
   pestañas: comparación de algoritmos, reglas aplicadas y catálogo completo.

Dentro del apartado técnico la comparación no se limita a barras: dice con
palabras qué algoritmo entrega el plan más barato, cuál es el más rápido y cuáles
no llegan a la meta. Las reglas se muestran con código, nombre legible,
condición SI, conclusión ENTONCES, certeza y prioridad; en las difusas, la
certeza es la fuerza real con la que se activaron.

La lógica de negocio no cambió. El modelo de Machine Learning, las reglas del
experto, la lógica difusa y los algoritmos de búsqueda siguen siendo los mismos.
Lo que cambió es **el orden de la información**: el texto técnico sigue
disponible, pero solo se abre cuando alguien lo pide.

> Frase para memorizar: *"Primero decimos qué hacer; si te interesa, después
> mostramos cómo llegamos ahí."*

---

## 2. La decisión de la semana (ejemplo reproducible)

Con el escenario de riesgo usado en la demostración:

| Dato | Resultado esperado |
| ---- | ------------------ |
| Sucursal / categoría | El Alto / pollo |
| Meta | 1,20 veces la meta base |
| Ventas proyectadas | 35 740,90 Bs |
| Cumplimiento | 67,0 % de la meta |
| Riesgo | Alto |
| Causas principales | Operación crítica y merma alta |
| **Acción recomendada** | **Reponer stock (+400 u)** |
| **Inversión estimada** | **4 400 Bs** |
| Estados de búsqueda | 56 creados · 29 evaluados · 18 descartados · 2 en la ruta |

Los valores salen de una simulación con semilla fija (2026). Si cambias la
sucursal, la meta o los datos observados, el sistema recalcula todo; por eso la
decisión debe leerse como **salida del escenario elegido**, no como un pronóstico
externo.

### Cómo leer la pantalla en 30 segundos

1. Mira el recuadro **«Decisión de esta semana»**: ahí está la acción.
2. Mira la **inversión estimada** y compárala con tu presupuesto.
3. Mira la frase de contexto: te dice si el problema es de stock, merma,
   afluencia o precio.
4. Solo si quieres profundizar, abre los tres apartados de abajo; en el último,
   cambia entre sus tres pestañas según lo que necesites.

---

## 3. Uso en tres pasos

### Paso 1. Levantar el sistema

```powershell
# Terminal A: API
.\venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000

# Terminal B: dashboard
.\venv\Scripts\python.exe -m streamlit run app/dashboard.py --server.port 8501
```

Abre <http://localhost:8501>. Si la API no responde, el dashboard lo indica con
un mensaje claro en español.

### Paso 2. Elegir el escenario

En el panel lateral:

1. Sucursal **El Alto**, categoría **pollo**.
2. Meta de ventas **1,20**.
3. Presupuesto disponible **9 000 Bs** (valor inicial).
4. Abrir **«Datos observados (opcional)»**, marcar **«Personalizar escenario»** y
   poner cobertura de stock **0,18**, afluencia relativa **0,70** y merma
   **14,5 %**.
5. Pulsar **«Calcular plan»**.

> Para reproducir el caso exacto del ejemplo con todos sus datos de contexto
> (precio versus competencia, excedente en otra sucursal y reposición tardía),
> ejecuta `python -m core.demo`. El dashboard expone solo los tres datos
> observados indicados arriba.

### Paso 3. Leer y decidir

La pantalla mostrará **«1. Reponer stock (+400 u)»**, inversión de **4 400 Bs** y
riesgo **alto**. Esa es la acción a ejecutar esta semana en el escenario de
ejemplo.

Si subes o bajas la meta o el presupuesto, vuelve a pulsar **«Calcular plan»**.
El sistema recalcula y avisa si ya no existe un plan dentro del presupuesto.

### Cómo responder preguntas concretas

| Pregunta | Dónde mirar |
| -------- | ----------- |
| ¿Qué algoritmo da el mejor plan? | **«Comparación y detalle técnico» → «Comparación de algoritmos»**. |
| ¿Qué reglas se usaron en este caso? | Pestaña **«Reglas aplicadas»**. |
| ¿Qué reglas existen en el sistema? | Pestaña **«Todas las reglas del sistema»**. |
| ¿Por qué hay riesgo alto? | **«¿Por qué esta decisión?»**: causa en palabras, certeza y palanca. |

---

## 4. Guion de exposición (5 minutos)

| Tiempo | Mostrar | Decir |
| ------ | ------- | ----- |
| 0:00 – 0:30 | Solo la parte superior del dashboard. | *"En menos de 30 segundos: reponer 400 unidades de pollo, cuesta 4 400 bolivianos y el riesgo es alto. Eso es lo que se hace esta semana."* |
| 0:30 – 1:15 | Las cuatro cifras y la frase de contexto. | *"La proyección es de 35 740 bolivianos, apenas 67 % de la meta. El diagnóstico apunta a operación crítica y merma alta: hay producto, pero no llega o se pierde antes de venderse."* |
| 1:15 – 2:15 | Abrir **«¿Por qué esta decisión?»**. | *"Cada causa aparece en palabras, con certeza alta, media o baja y qué acción permite o bloquea. Detrás están SHAP, las reglas y la lógica difusa, pero no hacen falta para entender el motivo."* |
| 2:15 – 3:15 | Abrir **«Cómo se exploraron las opciones»**. | *"Esto no es una ilustración: son los 56 estados reales que creó la búsqueda. 29 se evaluaron, 18 se descartaron y solo 2 están en la ruta ganadora. La línea dorada es el camino a la meta; la línea de tiempo respeta el orden exacto de evaluación."* |
| 3:15 – 4:15 | Abrir **«Comparación y detalle técnico»** y recorrer sus tres pestañas. | *"La primera pestaña dice con palabras quién da el plan más barato, quién es más rápido y quién no llega a la meta; las barras solo acompañan. La segunda muestra las reglas que realmente se aplicaron, con su SI, su ENTONCES y su certeza. La tercera contiene el catálogo completo de las 60 reglas del sistema."* |
| 4:15 – 5:00 | Cerrar los expanders y volver a la decisión. | *"La acción de esta semana es reponer stock. Si cambia el presupuesto o la meta, el sistema vuelve a calcular y nos dice si el plan sigue siendo viable."* |

**Consejo para mañana:** deja los tres apartados cerrados al empezar. Si
preguntan por algoritmos o reglas, abre el último apartado y usa sus pestañas en
ese orden: comparación, reglas aplicadas y catálogo. Eso mantiene la atención en
la decisión y evita que la audiencia se pierda en términos técnicos.

---

## 5. Preguntas frecuentes

**¿Esto no era solo un modelo de predicción?**
El modelo da la cifra, pero por sí solo no dice qué hacer. El sistema añade
reglas de negocio, riesgo difuso y un plan de acciones; por eso la respuesta
final es una decisión, no un número.

**¿Qué significa la confianza 0,24?**
Es una medida de confianza calibrada del modelo para esa predicción. No es la
probabilidad de acertar. Se reutiliza como duda inicial en el razonamiento
simbólico: cuanto menor es, más cautelosas son las reglas.

**¿Cómo sé que el plan es el mejor?**
A* comparó las opciones permitidas y eligió la de menor costo que alcanza la
meta dentro del presupuesto. La ruta y el orden de evaluación se muestran en la
traza real, no en un dibujo decorativo.

**¿Cómo sé qué algoritmo conviene más?**
La pestaña «Comparación de algoritmos» lo dice en texto: cuál logra el menor
costo, cuál resuelve más rápido y cuáles no alcanzan la meta. La tabla y el
gráfico son la prueba, no la explicación principal.

**¿Dónde veo las reglas que se aplicaron?**
En la pestaña «Reglas aplicadas». Cada fila trae el orden real de disparo, el
código, el nombre legible, la condición SI, la conclusión ENTONCES, la certeza y
la prioridad. Las reglas difusas muestran su fuerza de activación.

**¿Puedo ver todas las reglas del sistema?**
Sí: la pestaña «Todas las reglas del sistema» muestra las 60 reglas (38 expertas
y 22 difusas) con condición y conclusión en español. También se consultan con
`GET /reglas` sin ejecutar ningún análisis.

**¿Por qué no propone una promoción?**
Porque el diagnóstico dice que el problema es operativo (stock y merma). Las
reglas excluyen acciones que no atacan la causa principal. Si el diagnóstico
cambiara, el plan también cambiaría.

**¿Los datos son reales?**
No. El dataset es simulado y reproducible (2 496 filas, 6 sucursales, 4
categorías, semilla 2026). Es un prototipo para demostrar el método de decisión,
no una conexión a las ventas reales de la empresa.

---

## 6. Anexo técnico breve

**Arquitectura.** Streamlit → API FastAPI → fachada `SistemaInteligente` →
predictor Ridge con SHAP → memoria de trabajo → sistema experto (reglas MYCIN) →
lógica difusa Mamdani → planificador A* → explicación unificada. El dashboard es
un cliente ligero: no reimplementa ninguna regla de negocio.

**Modelo seleccionado.** Ridge, con MAE 2 298,48; RMSE 3 488,88; R² 0,7627;
MAPE 15,14 %. Mejora de 23,72 % de MAE frente a la línea base de semana
anterior. Fuente: [`INFORME_TECNICO.md`](INFORME_TECNICO.md).

**Búsqueda.** BFS, DFS, backtracking, costo uniforme, Greedy y A* comparten el
mismo espacio de estados. La heurística de A* es admisible y consistente. El
benchmark está en `docs/benchmark_busqueda.md`.

**Trazabilidad de la visualización.**
`search/resultado.py` registra cada nodo → `core/resultado.py` lo expone en el
plan → `api/esquemas.py` y `api/mapeado.py` lo entregan por REST →
`app/visualizacion.py` dibuja el grafo y la línea de tiempo → `app/dashboard.py`
los muestra dentro del apartado **«Cómo se exploraron las opciones»**.

**Trazabilidad de las reglas.**
`expert_system/reglas.json` y `config.py` declaran las reglas →
`MotorInferencia` registra cada disparo real con orden, premisa y certezas →
`core/resultado.py` guarda `reglas_aplicadas` → `api/mapeado.py` proyecta la
traza y el catálogo → `GET /reglas` expone las 60 reglas y el dashboard las
muestra en sus pestañas.

**Endpoints usados por el dashboard.**

| Método | Ruta | Para qué sirve |
| ------ | ---- | -------------- |
| POST | `/analisis-completo` | Predicción, causas, riesgo, plan, traza y reglas aplicadas |
| GET | `/explicar/{id}` | Explicación detallada y factores SHAP |
| GET | `/benchmark` | Comparación de algoritmos de búsqueda |
| GET | `/reglas` | Catálogo completo de reglas expertas y difusas (solo lectura) |

**Verificación de esta entrega.** 279 pruebas en verde; `black --check` y
`ruff check` sin hallazgos; arranque real de API y dashboard comprobado, con las
tres pestañas visibles, tablas accesibles y sin errores en consola.

**Archivos tocados.** `app/dashboard.py` (rediseño y pestañas),
`app/visualizacion.py` (traducción de reglas, certezas y causas en palabras),
`api/esquemas.py`, `api/mapeado.py`, `api/dependencias.py` y `api/main.py`
(catálogo `GET /reglas` y traza completa), `core/resultado.py`, `core/sistema.py`
y `expert_system/motor_inferencia.py` (propagación de la traza real), las
pruebas correspondientes, este informe y el renombrado de `docs/informe.md` a
`docs/INFORME_TECNICO.md` para liberar el nombre `docs/INFORME.md` sin perder el
informe académico. Las referencias en `README.md`, `docs/guion_demo.md`,
`docs/commonkads.md`, `prompt_maestro.md` y `setup_proyecto.py` se actualizaron
al nuevo nombre.

---

## 7. Límites a mencionar si preguntan

- Los datos son simulados; el prototipo no está conectado a inventario ni a
  ventas reales.
- El horizonte es semanal y la recomendación depende del escenario elegido.
- La confianza del modelo y los factores de certeza expresan duda, no
  probabilidades comerciales.
- El plan asume que los costos y efectos de cada acción están bien calibrados en
  `search/espacio_estados.py`.
- La traza es real para la búsqueda ejecutada, pero no sustituye una auditoría
  externa del modelo ni de los datos.
