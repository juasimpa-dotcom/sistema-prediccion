"""Explicaciones locales y globales con SHAP como estructuras de datos limpias."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge

from config import (
    ARCHIVO_IMPORTANCIAS,
    CARACTERISTICAS_CATEGORICAS,
    CARACTERISTICAS_NUMERICAS,
    MAX_MUESTRAS_SHAP,
    NUMERO_FACTORES_LOCALES,
)

if TYPE_CHECKING:
    from sklearn.base import BaseEstimator
    from sklearn.pipeline import Pipeline

LOGGER = logging.getLogger(__name__)

MODELOS_ARBOL = (RandomForestRegressor, GradientBoostingRegressor)
MODELOS_LINEALES = (Ridge, LinearRegression)


@dataclass(frozen=True, slots=True)
class FactorInfluencia:
    """Aporte de una variable a una predicción individual.

    Attributes:
        variable: Nombre de la característica transformada.
        valor_shap: Contribución en bolivianos sobre la predicción.
        direccion: ``"aumenta"`` o ``"reduce"`` según el signo del aporte.
        detalle: Valor legible de la variable en la observación explicada.
    """

    variable: str
    valor_shap: float
    direccion: str
    detalle: str


@dataclass(frozen=True, slots=True)
class ExplicacionLocal:
    """Explicación de una única predicción.

    Attributes:
        valor_base: Valor esperado de referencia devuelto por SHAP.
        valor_predicho: Predicción final del pipeline.
        factores: Variables ordenadas por influencia absoluta.
    """

    valor_base: float
    valor_predicho: float
    factores: tuple[FactorInfluencia, ...]


@dataclass(frozen=True, slots=True)
class ImportanciaVariable:
    """Importancia global de una variable.

    Attributes:
        variable: Nombre de la característica transformada.
        importancia: Media del valor absoluto de SHAP.
        impacto_medio: Media del valor de SHAP, con signo.
    """

    variable: str
    importancia: float
    impacto_medio: float


@dataclass(frozen=True, slots=True)
class ExplicacionGlobal:
    """Explicación agregada de múltiples predicciones.

    Attributes:
        metodo: Nombre del explicador SHAP utilizado.
        numero_observaciones: Cantidad de filas explicadas.
        importancias: Variables ordenadas por importancia descendente.
    """

    metodo: str
    numero_observaciones: int
    importancias: tuple[ImportanciaVariable, ...]


def _columnas(pipeline: Pipeline) -> list[str]:
    """Devuelve las columnas de entrada que espera el pipeline.

    Args:
        pipeline: Pipeline ajustado.

    Returns:
        Lista de nombres de características crudas.
    """
    return [*CARACTERISTICAS_NUMERICAS, *CARACTERISTICAS_CATEGORICAS]


def transformar_entrada(pipeline: Pipeline, entrada: pd.DataFrame) -> np.ndarray:
    """Aplica preprocesamiento y escalado hasta la entrada del modelo.

    Args:
        pipeline: Pipeline ajustado.
        entrada: Filas con las columnas originales.

    Returns:
        Matriz numérica lista para el modelo.
    """
    datos = entrada.loc[:, _columnas(pipeline)]
    matriz = pipeline.named_steps["preprocesador"].transform(datos)
    if "escalador" in pipeline.named_steps:
        matriz = pipeline.named_steps["escalador"].transform(matriz)
    return np.asarray(matriz, dtype=float)


def nombres_transformados(pipeline: Pipeline) -> list[str]:
    """Lista los nombres de las columnas después de codificar.

    Args:
        pipeline: Pipeline ajustado.

    Returns:
        Nombres de las características que recibe el modelo.
    """
    return list(pipeline.named_steps["preprocesador"].get_feature_names_out())


def crear_explicador(
    modelo: BaseEstimator,
    fondo: np.ndarray,
) -> tuple[object, str]:
    """Selecciona el explicador SHAP más adecuado para el tipo de modelo.

    Args:
        modelo: Estimador final ya ajustado.
        fondo: Muestra de referencia para explicadores dependientes del fondo.

    Returns:
        Par ``(explicador, nombre_del_metodo)``.
    """
    if isinstance(modelo, MODELOS_ARBOL):
        return shap.TreeExplainer(modelo), "TreeExplainer"
    if isinstance(modelo, MODELOS_LINEALES):
        return shap.LinearExplainer(modelo, fondo), "LinearExplainer"
    return shap.KernelExplainer(modelo.predict, fondo), "KernelExplainer"


def _valores_shap(explicador: Any, matriz: np.ndarray) -> tuple[np.ndarray, float]:
    """Calcula valores SHAP y normaliza sus dimensiones para regresión.

    Args:
        explicador: Explicador SHAP ya construido.
        matriz: Matriz transformada de observaciones.

    Returns:
        Par ``(valores, valor_base)``.
    """
    valores = np.asarray(explicador.shap_values(matriz), dtype=float)
    if valores.ndim == 3:
        valores = valores[:, :, 0]
    base = np.asarray(explicador.expected_value, dtype=float).reshape(-1)[0]
    return valores, float(base)


def detalle_variable(nombre: str, entrada: pd.DataFrame) -> str:
    """Convierte un nombre transformado en una descripción legible.

    Args:
        nombre: Nombre producido por ``ColumnTransformer``.
        entrada: Filas originales con los valores de la observación.

    Returns:
        Cadena del tipo ``"sucursal=El Alto"`` o ``"ventas_lag_1=14000.0"``.
    """
    limpio = nombre.split("__", 1)[-1]
    for columna in CARACTERISTICAS_CATEGORICAS:
        if limpio.startswith(f"{columna}_"):
            return f"{columna}={limpio[len(columna) + 1 :]}"
    if limpio in entrada.columns and not entrada.empty:
        return f"{limpio}={entrada.iloc[0][limpio]}"
    return limpio


def explicar_local(
    pipeline: Pipeline,
    entrada: pd.DataFrame,
    numero_factores: int = NUMERO_FACTORES_LOCALES,
    fondo: np.ndarray | None = None,
) -> ExplicacionLocal:
    """Explica una predicción individual devolviendo sus factores más influyentes.

    Args:
        pipeline: Pipeline ajustado.
        entrada: DataFrame de una sola fila con las columnas originales.
        numero_factores: Cantidad máxima de factores devueltos.
        fondo: Muestra de referencia ya transformada. Para modelos lineales es
            imprescindible usar un fondo distinto de la fila explicada.

    Returns:
        Explicación local con valores SHAP en bolivianos.
    """
    matriz = transformar_entrada(pipeline, entrada)
    modelo = pipeline.named_steps["modelo"]
    referencia = matriz if fondo is None else fondo
    explicador, _ = crear_explicador(modelo, referencia)
    valores, base = _valores_shap(explicador, matriz)

    nombres = nombres_transformados(pipeline)
    aportes = valores[0]
    orden = np.argsort(np.abs(aportes))[::-1][:numero_factores]
    factores = tuple(
        FactorInfluencia(
            variable=nombres[indice],
            valor_shap=float(aportes[indice]),
            direccion="aumenta" if aportes[indice] >= 0 else "reduce",
            detalle=detalle_variable(nombres[indice], entrada),
        )
        for indice in orden
    )
    prediccion = float(pipeline.predict(entrada)[0])
    return ExplicacionLocal(valor_base=base, valor_predicho=prediccion, factores=factores)


def explicar_global(
    pipeline: Pipeline,
    datos: pd.DataFrame,
    numero_factores: int = 10,
    max_muestras: int = MAX_MUESTRAS_SHAP,
) -> ExplicacionGlobal:
    """Calcula la importancia global promediando valores SHAP absolutos.

    Args:
        pipeline: Pipeline ajustado.
        datos: Conjunto de observaciones a explicar.
        numero_factores: Cantidad de variables devueltas.
        max_muestras: Límite de filas para mantener el cálculo acotado.

    Returns:
        Explicación global ordenada por importancia.
    """
    muestra = datos.loc[:, _columnas(pipeline)].iloc[:max_muestras]
    matriz = transformar_entrada(pipeline, muestra)
    modelo = pipeline.named_steps["modelo"]
    explicador, metodo = crear_explicador(modelo, matriz)
    valores, _ = _valores_shap(explicador, matriz)

    importancia = np.mean(np.abs(valores), axis=0)
    impacto = np.mean(valores, axis=0)
    orden = np.argsort(importancia)[::-1][:numero_factores]
    nombres = nombres_transformados(pipeline)
    importancias = tuple(
        ImportanciaVariable(
            variable=nombres[indice],
            importancia=float(importancia[indice]),
            impacto_medio=float(impacto[indice]),
        )
        for indice in orden
    )
    return ExplicacionGlobal(
        metodo=metodo,
        numero_observaciones=len(muestra),
        importancias=importancias,
    )


def guardar_importancias(
    explicacion: ExplicacionGlobal,
    ruta: Path = ARCHIVO_IMPORTANCIAS,
) -> Path:
    """Guarda la explicación global como CSV en ``docs/``.

    Args:
        explicacion: Resultado de :func:`explicar_global`.
        ruta: Archivo de destino.

    Returns:
        Ruta escrita.
    """
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tabla = pd.DataFrame(
        [
            {
                "variable": item.variable,
                "importancia": round(item.importancia, 2),
                "impacto_medio": round(item.impacto_medio, 2),
            }
            for item in explicacion.importancias
        ]
    )
    tabla.to_csv(ruta, index=False, encoding="utf-8")
    LOGGER.info("Importancias guardadas en %s", ruta)
    return ruta


def resumir_factores(
    explicacion: ExplicacionLocal,
    numero_factores: int = NUMERO_FACTORES_LOCALES,
) -> tuple[str, ...]:
    """Convierte los factores SHAP en cadenas breves para la fachada.

    Args:
        explicacion: Explicación local calculada con SHAP.
        numero_factores: Cantidad máxima de cadenas devueltas.

    Returns:
        Tupla de textos del tipo ``"ventas_lag_1: +1 200 Bs (...)"``.
    """
    textos: list[str] = []
    for factor in explicacion.factores[:numero_factores]:
        signo = "+" if factor.valor_shap >= 0 else "-"
        magnitud = abs(factor.valor_shap)
        texto = f"{factor.variable}: {signo}{magnitud:,.0f} Bs ({factor.detalle})"
        textos.append(texto)
    return tuple(textos)
