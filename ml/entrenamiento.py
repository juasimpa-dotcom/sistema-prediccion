"""Entrenamiento, comparación y guardado de modelos de ventas semanales.

Uso:
    python -m ml.entrenamiento
    python -m ml.entrenamiento --sin-mlp
"""

from __future__ import annotations

import argparse
import logging
import random
import warnings
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import Ridge
from sklearn.model_selection import GridSearchCV, ParameterGrid
from sklearn.neural_network import MLPRegressor

from config import (
    ARCHIVO_MODELO,
    ARCHIVO_VENTAS_CRUDO,
    CARACTERISTICAS_CATEGORICAS,
    CARACTERISTICAS_NUMERICAS,
    COLUMNA_OBJETIVO,
    CONFIANZA_MAXIMA,
    CONFIANZA_MINIMA,
    EPSILON,
    SEMILLA,
    VERSION_MODELO,
)
from ml.evaluacion import (
    NOMBRE_BASELINE,
    calcular_metricas,
    construir_tabla,
    guardar_metricas,
    guardar_reporte,
)
from ml.explicabilidad import (
    explicar_global,
    explicar_local,
    guardar_importancias,
    resumir_factores,
    transformar_entrada,
)
from ml.preprocesamiento import (
    construir_dataset_supervisado,
    construir_pipeline,
    dividir_temporal,
    divisor_tiempo,
    obtener_nombres_caracteristicas,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from sklearn.pipeline import Pipeline

    from ml.evaluacion import Metricas

LOGGER = logging.getLogger(__name__)


def cargar_datos(ruta: Path = ARCHIVO_VENTAS_CRUDO) -> pd.DataFrame:
    """Lee el dataset crudo y valida que exista.

    Args:
        ruta: Ubicación del CSV generado en la Fase 1.

    Returns:
        Dataset con la columna de fecha interpretada.

    Raises:
        FileNotFoundError: Si el archivo no existe.
    """
    if not ruta.exists():
        raise FileNotFoundError(
            f"No se encontró {ruta}. Ejecuta primero 'python -m data.generar_dataset'."
        )
    return pd.read_csv(ruta, parse_dates=["fecha_semana"])


def modelos_candidatos(incluir_mlp: bool = True) -> dict[str, tuple[Pipeline, dict]]:
    """Declara los modelos y sus grids de hiperparámetros moderados.

    Args:
        incluir_mlp: Si se incluye el perceptrón multicapa.

    Returns:
        Mapa nombre -> ``(pipeline, grilla)``.
    """
    candidatos: dict[str, tuple[Pipeline, dict]] = {
        "Ridge": (
            construir_pipeline(Ridge(random_state=SEMILLA)),
            {"modelo__alpha": [1.0, 10.0, 100.0]},
        ),
        "Random Forest": (
            construir_pipeline(
                RandomForestRegressor(random_state=SEMILLA, n_jobs=1), escalar=False
            ),
            {
                "modelo__n_estimators": [200, 300],
                "modelo__max_depth": [None, 12],
                "modelo__min_samples_leaf": [1, 3],
            },
        ),
        "Gradient Boosting": (
            construir_pipeline(GradientBoostingRegressor(random_state=SEMILLA), escalar=False),
            {
                "modelo__n_estimators": [200, 300],
                "modelo__learning_rate": [0.05, 0.1],
                "modelo__max_depth": [2, 3],
            },
        ),
    }
    if incluir_mlp:
        candidatos["MLPRegressor"] = (
            construir_pipeline(
                MLPRegressor(
                    hidden_layer_sizes=(64,),
                    max_iter=400,
                    early_stopping=True,
                    n_iter_no_change=20,
                    random_state=SEMILLA,
                )
            ),
            {
                "modelo__hidden_layer_sizes": [(64,), (32, 32)],
                "modelo__alpha": [1e-3, 1e-2],
            },
        )
    return candidatos


def entrenar_modelos(
    x_entrenamiento: pd.DataFrame,
    y_entrenamiento: pd.Series,
    divisiones: list[tuple[np.ndarray, np.ndarray]],
    incluir_mlp: bool = True,
) -> dict[str, GridSearchCV]:
    """Ajusta cada candidato con GridSearchCV y validación temporal.

    Args:
        x_entrenamiento: Características del conjunto de entrenamiento.
        y_entrenamiento: Ventas objetivo del entrenamiento.
        divisiones: Pliegues de ``TimeSeriesSplit`` por semana completa.
        incluir_mlp: Si se incluye el perceptrón multicapa.

    Returns:
        Mapa nombre -> buscador ya ajustado.
    """
    ajustados: dict[str, GridSearchCV] = {}
    for nombre, (pipeline, grilla) in modelos_candidatos(incluir_mlp).items():
        LOGGER.info(
            "Entrenando %s (%d combinaciones)",
            nombre,
            len(list(ParameterGrid(grilla))),
        )
        busqueda = GridSearchCV(
            estimator=pipeline,
            param_grid=grilla,
            scoring="neg_mean_absolute_error",
            cv=divisiones,
            n_jobs=1,
            refit=True,
        )
        busqueda.fit(x_entrenamiento, y_entrenamiento)
        ajustados[nombre] = busqueda
        LOGGER.info(
            "%s: MAE validación %.2f | mejores parámetros %s",
            nombre,
            -busqueda.best_score_,
            busqueda.best_params_,
        )
    return ajustados


def evaluar_modelos(
    ajustados: Mapping[str, GridSearchCV],
    x_prueba: pd.DataFrame,
    y_prueba: pd.Series,
) -> tuple[dict[str, Metricas], dict[str, np.ndarray], dict[str, Pipeline]]:
    """Evalúa todos los modelos y el baseline en el conjunto de prueba.

    Args:
        ajustados: Modelos ya entrenados.
        x_prueba: Características de prueba.
        y_prueba: Ventas reales de prueba.

    Returns:
        Tupla ``(métricas, predicciones, pipelines)``.
    """
    predicciones: dict[str, np.ndarray] = {
        NOMBRE_BASELINE: x_prueba["ventas_lag_1"].to_numpy(dtype=float)
    }
    pipelines: dict[str, Pipeline] = {}
    for nombre, busqueda in ajustados.items():
        predicciones[nombre] = np.asarray(busqueda.predict(x_prueba), dtype=float)
        pipelines[nombre] = busqueda.best_estimator_

    metricas = {
        nombre: calcular_metricas(y_prueba.tolist(), valores.tolist())
        for nombre, valores in predicciones.items()
    }
    return metricas, predicciones, pipelines


def seleccionar_mejor(metricas: Mapping[str, Metricas]) -> str:
    """Elige el modelo con menor MAE entre los ajustados, excluyendo el baseline.

    Args:
        metricas: Métricas por modelo.

    Returns:
        Nombre del modelo seleccionado.

    Raises:
        ValueError: Si no hay modelos ajustados.
    """
    candidatos = [
        (nombre, item.mae) for nombre, item in metricas.items() if nombre != NOMBRE_BASELINE
    ]
    if not candidatos:
        raise ValueError("No hay modelos ajustados para seleccionar")
    mejor = min(candidatos, key=lambda par: par[1])[0]
    if NOMBRE_BASELINE in metricas and metricas[mejor].mae >= metricas[NOMBRE_BASELINE].mae:
        LOGGER.warning("Ningún modelo superó al baseline en MAE")
    return mejor


def estimar_desvio_residuos(y_real: pd.Series, y_predicho: np.ndarray) -> float:
    """Calcula la desviación estándar de los errores relativos en prueba.

    Args:
        y_real: Ventas observadas.
        y_predicho: Ventas estimadas.

    Returns:
        Desviación estándar de ``(real - predicho) / real``.
    """
    errores = (np.asarray(y_real, dtype=float) - y_predicho) / np.maximum(
        np.asarray(y_real, dtype=float), EPSILON
    )
    return float(np.std(errores))


def dispersion_arboles(pipeline: Pipeline, entrada: pd.DataFrame) -> float | None:
    """Mide la dispersión de predicciones entre árboles o etapas de boosting.

    Args:
        pipeline: Pipeline ajustado.
        entrada: Fila o filas con características originales.

    Returns:
        Desviación de las predicciones, o ``None`` si el modelo no es de árboles.
    """
    modelo = pipeline.named_steps["modelo"]
    matriz = transformar_entrada(pipeline, entrada)
    if isinstance(modelo, RandomForestRegressor):
        predicciones = np.array([arbol.predict(matriz) for arbol in modelo.estimators_])
    elif isinstance(modelo, GradientBoostingRegressor):
        predicciones = np.array(list(modelo.staged_predict(matriz)))
    else:
        return None
    return float(np.std(predicciones, axis=0)[0])


def estimar_confianza(
    valor_predicho: float,
    referencia: float,
    desvio_residuos: float,
    mape: float,
    dispersion: float | None = None,
) -> float:
    """Convierte la incertidumbre estimada en un factor de certeza entre 0 y 1.

    Args:
        valor_predicho: Ventas estimadas para la semana objetivo.
        referencia: Ventas de la semana anterior (lag 1).
        desvio_residuos: Desviación de errores relativos observada en prueba.
        mape: Error porcentual medio del modelo en prueba.
        dispersion: Dispersión entre árboles, si el modelo la permite.

    Returns:
        Confianza acotada entre ``CONFIANZA_MINIMA`` y ``CONFIANZA_MAXIMA``.
    """
    calidad = float(np.clip(1.0 - mape / 100.0, 0.0, 1.0))
    escala = max(desvio_residuos, EPSILON)
    if dispersion is not None:
        incertidumbre = dispersion / max(abs(valor_predicho), EPSILON)
    else:
        incertidumbre = abs(valor_predicho - referencia) / max(abs(referencia), EPSILON)
    razon = min(incertidumbre / escala, 1.0)
    return float(np.clip(calidad * (1.0 - razon), CONFIANZA_MINIMA, CONFIANZA_MAXIMA))


def guardar_artefacto(
    pipeline: Pipeline,
    metadatos: Mapping[str, object],
    ruta: Path = ARCHIVO_MODELO,
    fondo: np.ndarray | None = None,
) -> Path:
    """Guarda el pipeline y sus metadatos en un único archivo joblib.

    Args:
        pipeline: Modelo seleccionado ya ajustado.
        metadatos: Información de versión, métricas, columnas y calibración.
        ruta: Archivo de destino.
        fondo: Muestra transformada de referencia para explicaciones SHAP lineales.

    Returns:
        Ruta escrita.
    """
    ruta.parent.mkdir(parents=True, exist_ok=True)
    contenido = {"pipeline": pipeline, "metadatos": dict(metadatos), "fondo": fondo}
    joblib.dump(contenido, ruta, compress=3)
    LOGGER.info("Modelo guardado en %s", ruta)
    return ruta


def cargar_artefacto(ruta: Path = ARCHIVO_MODELO) -> dict:
    """Carga el pipeline y los metadatos guardados con :func:`guardar_artefacto`.

    Args:
        ruta: Archivo joblib.

    Returns:
        Diccionario con claves ``pipeline`` y ``metadatos``.

    Raises:
        FileNotFoundError: Si el archivo no existe.
        ValueError: Si el contenido no corresponde a un artefacto de la Fase 2.
    """
    if not ruta.exists():
        raise FileNotFoundError(
            f"No se encontró el modelo en {ruta}. Ejecuta 'python -m ml.entrenamiento'."
        )
    artefacto = joblib.load(ruta)
    if not isinstance(artefacto, dict) or "pipeline" not in artefacto:
        raise ValueError(f"El archivo {ruta} no es un artefacto válido")
    return artefacto


def _parsear_argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    """Procesa los argumentos de línea de comandos.

    Args:
        argv: Argumentos a analizar.

    Returns:
        Espacio de nombres con las opciones.
    """
    parser = argparse.ArgumentParser(description="Entrena y compara modelos de ventas.")
    parser.add_argument("--semilla", type=int, default=SEMILLA, help="Semilla aleatoria.")
    parser.add_argument("--sin-mlp", action="store_true", help="Omite el MLPRegressor.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Ejecuta el pipeline completo de entrenamiento, evaluación y guardado."""
    argumentos = _parsear_argumentos(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    warnings.filterwarnings("ignore", category=ConvergenceWarning)
    random.seed(argumentos.semilla)
    np.random.seed(argumentos.semilla)

    crudo = cargar_datos()
    supervisado = construir_dataset_supervisado(crudo)
    entrenamiento, prueba = dividir_temporal(supervisado)
    divisiones = divisor_tiempo(entrenamiento)
    columnas = [*CARACTERISTICAS_NUMERICAS, *CARACTERISTICAS_CATEGORICAS]
    x_train = entrenamiento.loc[:, columnas]
    y_train = entrenamiento[COLUMNA_OBJETIVO]
    x_test = prueba.loc[:, columnas]
    y_test = prueba[COLUMNA_OBJETIVO]
    LOGGER.info(
        "Entrenamiento: %d filas | Prueba: %d filas | Pliegues: %d",
        len(x_train),
        len(x_test),
        len(divisiones),
    )

    ajustados = entrenar_modelos(x_train, y_train, divisiones, incluir_mlp=not argumentos.sin_mlp)
    metricas, predicciones, pipelines = evaluar_modelos(ajustados, x_test, y_test)
    tabla = construir_tabla(metricas)
    mejor = seleccionar_mejor(metricas)
    mejor_pipeline = pipelines[mejor]
    mejor_prediccion = predicciones[mejor]

    rutas = guardar_reporte(
        prueba["fecha_objetivo"], y_test.tolist(), mejor_prediccion.tolist(), tabla
    )
    LOGGER.info("Mejor modelo: %s", mejor)

    columnas_transformadas = obtener_nombres_caracteristicas(mejor_pipeline)
    global_shap = explicar_global(mejor_pipeline, x_test)
    ruta_importancias = guardar_importancias(global_shap)

    ejemplo = x_test.iloc[[0]]
    fondo_shap = transformar_entrada(mejor_pipeline, x_test.iloc[: min(100, len(x_test))])
    local_shap = explicar_local(mejor_pipeline, ejemplo, fondo=fondo_shap)
    dispersion = dispersion_arboles(mejor_pipeline, ejemplo)
    desvio = estimar_desvio_residuos(y_test, mejor_prediccion)
    metrica_mejor = metricas[mejor]
    confianza = estimar_confianza(
        float(mejor_prediccion[0]),
        float(ejemplo["ventas_lag_1"].iloc[0]),
        desvio,
        metrica_mejor.mape,
        dispersion,
    )

    metadatos: dict[str, object] = {
        "version": VERSION_MODELO,
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "semilla": argumentos.semilla,
        "nombre_modelo": mejor,
        "mejores_parametros": {
            clave: str(valor) for clave, valor in ajustados[mejor].best_params_.items()
        },
        "metricas": metrica_mejor.como_dict(),
        "metricas_por_modelo": {nombre: item.como_dict() for nombre, item in metricas.items()},
        "columnas": {
            "numericas": list(CARACTERISTICAS_NUMERICAS),
            "categoricas": list(CARACTERISTICAS_CATEGORICAS),
            "transformadas": columnas_transformadas,
            "objetivo": COLUMNA_OBJETIVO,
        },
        "calibracion": {
            "desvio_residuos_relativos": desvio,
            "mape_prueba": metrica_mejor.mape,
            "confianza_ejemplo": confianza,
            "meta_promedio": float(x_test["meta_ventas_bs"].mean()),
        },
        "fecha_corte_entrenamiento": str(entrenamiento["fecha_objetivo"].max().date()),
        "reporte": rutas,
        "importancias": str(ruta_importancias),
    }
    guardar_artefacto(mejor_pipeline, metadatos, fondo=fondo_shap)
    guardar_metricas(metadatos)

    print("\n" + "=" * 78)
    print("COMPARACIÓN DE MODELOS (conjunto de prueba)")
    print("=" * 78)
    print(tabla.to_string())
    mejora = tabla.loc[mejor, "mejora_vs_baseline_pct"] if NOMBRE_BASELINE in tabla.index else None
    if mejora is not None:
        print(f"\nMejora del mejor modelo frente al baseline: {mejora:.2f}% en MAE")
    print(f"Modelo guardado: {ARCHIVO_MODELO}")
    print(f"Confianza de ejemplo: {confianza:.3f}")
    print("Factores principales (SHAP):")
    for factor in resumir_factores(local_shap):
        print(f"  - {factor}")
    print("Variables más influyentes (SHAP global):")
    for item in global_shap.importancias[:5]:
        print(f"  - {item.variable}: {item.importancia:,.0f} Bs")


if __name__ == "__main__":
    main()
