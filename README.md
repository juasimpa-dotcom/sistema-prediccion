# Sistema inteligente de predicción del rendimiento de ventas

Sistema híbrido neuro-simbólico que predice el rendimiento de ventas y el
cumplimiento de metas de una cadena de retail de alimentos en Bolivia
(pollo, cerdo, embutidos y congelados), y que además razona, recomienda
acciones y explica sus decisiones.

## Estado del proyecto

| Fase | Alcance | Estado |
| ---- | ------- | ------ |
| 1 | Configuración base y generación del dataset | Completada |
| 2 | Preprocesamiento y modelo de Machine Learning | Pendiente |
| 3 | Sistema experto (reglas, factores de certeza, lógica difusa) | Pendiente |
| 4 | Búsqueda de planes de acción | Pendiente |
| 5 | Explicabilidad, API y dashboard | Pendiente |

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
  search/                    # Espacio de estados, búsquedas no informadas e informadas
  api/                       # API FastAPI
  app/                       # Dashboard Streamlit
  notebooks/
    eda_ventas.py            # Análisis exploratorio y figuras
    figuras/                 # Gráficos generados
  tests/                     # Pruebas con pytest
  docs/                      # CommonKADS e informe
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

Calidad y pruebas:

```powershell
black --check .
ruff check .
pytest
```

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
