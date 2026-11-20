"""Métricas, tabla comparativa y figuras de diagnóstico de los modelos."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import (
    ARCHIVO_COMPARACION,
    ARCHIVO_COMPARACION_MD,
    ARCHIVO_METRICAS,
    DIR_FIGURAS_MODELOS,
    EPSILON,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

LOGGER = logging.getLogger(__name__)

NOMBRE_BASELINE: str = "Baseline (semana anterior)"
COLOR_REAL: str = "#1f4e79"
COLOR_PREDICHO: str = "#d97706"
COLOR_RESIDUO: str = "#b91c1c"


@dataclass(frozen=True, slots=True)
class Metricas:
    """Conjunto de métricas de regresión calculadas sobre un conjunto de prueba.

    Attributes:
        mae: Error absoluto medio, en bolivianos.
        rmse: Raíz del error cuadrático medio, en bolivianos.
        r2: Coeficiente de determinación.
        mape: Error porcentual absoluto medio, en porcentaje.
    """

    mae: float
    rmse: float
    r2: float
    mape: float

    def como_dict(self) -> dict[str, float]:
        """Devuelve las métricas como diccionario serializable.

        Returns:
            Diccionario con claves ``mae``, ``rmse``, ``r2`` y ``mape``.
        """
        return {
            "mae": round(self.mae, 4),
            "rmse": round(self.rmse, 4),
            "r2": round(self.r2, 6),
            "mape": round(self.mape, 4),
        }


def calcular_metricas(y_real: Sequence[float], y_predicho: Sequence[float]) -> Metricas:
    """Calcula MAE, RMSE, R2 y MAPE entre valores reales y predichos.

    Args:
        y_real: Valores observados.
        y_predicho: Valores estimados por el modelo.

    Returns:
        Objeto :class:`Metricas` con las cuatro medidas.

    Raises:
        ValueError: Si ambas secuencias tienen longitudes distintas o están vacías.
    """
    real = np.asarray(y_real, dtype=float)
    predicho = np.asarray(y_predicho, dtype=float)
    if real.shape != predicho.shape or real.size == 0:
        raise ValueError("Las secuencias real y predicha deben tener la misma longitud")

    error = real - predicho
    mae = float(np.mean(np.abs(error)))
    rmse = float(np.sqrt(np.mean(error**2)))
    varianza = float(np.sum((real - real.mean()) ** 2))
    r2 = 1.0 - float(np.sum(error**2)) / varianza if varianza > EPSILON else 0.0
    mape = float(np.mean(np.abs(error) / np.maximum(np.abs(real), EPSILON)) * 100)
    return Metricas(mae=mae, rmse=rmse, r2=r2, mape=mape)


def construir_tabla(resultados: Mapping[str, Metricas]) -> pd.DataFrame:
    """Arma la tabla comparativa ordenada por MAE.

    Args:
        resultados: Mapa nombre de modelo -> métricas en prueba.

    Returns:
        DataFrame indexado por modelo con las métricas y la mejora sobre el baseline.
    """
    filas = {nombre: metricas.como_dict() for nombre, metricas in resultados.items()}
    tabla = pd.DataFrame.from_dict(filas, orient="index")
    tabla.index.name = "modelo"
    tabla = tabla.sort_values("mae")

    if NOMBRE_BASELINE in tabla.index:
        mae_base = tabla.loc[NOMBRE_BASELINE, "mae"]
        tabla["mejora_vs_baseline_pct"] = (
            (mae_base - tabla["mae"]) / max(mae_base, EPSILON) * 100
        ).round(2)
    return tabla


def _a_markdown(tabla: pd.DataFrame) -> str:
    """Convierte una tabla a Markdown sin dependencias opcionales.

    Args:
        tabla: Tabla a convertir.

    Returns:
        Cadena con la tabla en formato Markdown.
    """
    cabeceras = ["modelo", *[str(columna) for columna in tabla.columns]]
    filas = [
        [str(indice), *[f"{valor:.2f}" for valor in fila]] for indice, fila in tabla.iterrows()
    ]
    ancho = [
        max(len(str(item)) for item in [cabecera, *[fila[i] for fila in filas]])
        for i, cabecera in enumerate(cabeceras)
    ]
    separador = "| " + " | ".join("-" * largo for largo in ancho) + " |"

    def formatear(fila: list[str]) -> str:
        celdas = [item.ljust(ancho[i]) for i, item in enumerate(fila)]
        return "| " + " | ".join(celdas) + " |"

    return "\n".join([formatear(cabeceras), separador, *(formatear(fila) for fila in filas)])


def guardar_tabla(
    tabla: pd.DataFrame,
    ruta_csv: Path = ARCHIVO_COMPARACION,
    ruta_markdown: Path = ARCHIVO_COMPARACION_MD,
) -> tuple[Path, Path]:
    """Guarda la tabla comparativa en CSV y Markdown dentro de ``docs/``.

    Args:
        tabla: Tabla devuelta por :func:`construir_tabla`.
        ruta_csv: Archivo CSV de destino.
        ruta_markdown: Archivo Markdown de destino.

    Returns:
        Par de rutas escritas.
    """
    for ruta in (ruta_csv, ruta_markdown):
        ruta.parent.mkdir(parents=True, exist_ok=True)

    tabla.to_csv(ruta_csv, encoding="utf-8")
    ruta_markdown.write_text(
        "# Comparación de modelos\n\n"
        "Ordenado por MAE sobre el conjunto de prueba (menor es mejor).\n\n"
        f"{_a_markdown(tabla)}\n",
        encoding="utf-8",
    )
    return ruta_csv, ruta_markdown


def guardar_metricas(
    datos: Mapping[str, object],
    ruta: Path = ARCHIVO_METRICAS,
) -> Path:
    """Serializa métricas y metadatos a un archivo JSON legible.

    Args:
        datos: Contenido a guardar.
        ruta: Ruta del archivo JSON.

    Returns:
        Ruta escrita.
    """
    ruta.parent.mkdir(parents=True, exist_ok=True)
    contenido = json.dumps(datos, default=str, ensure_ascii=False, indent=2)
    ruta.write_text(contenido, encoding="utf-8")
    return ruta


def _preparar_eje() -> None:
    """Fija un backend no interactivo y un estilo consistente para las figuras."""
    plt.switch_backend("Agg")
    plt.style.use("seaborn-v0_8-whitegrid")


def _guardar_figura(figura: plt.Figure, ruta: Path) -> Path:
    """Guarda una figura en disco y libera la memoria.

    Args:
        figura: Figura de matplotlib.
        ruta: Ruta de destino.

    Returns:
        Ruta escrita.
    """
    ruta.parent.mkdir(parents=True, exist_ok=True)
    figura.tight_layout()
    figura.savefig(ruta, dpi=130, bbox_inches="tight")
    plt.close(figura)
    LOGGER.info("Figura guardada en %s", ruta)
    return ruta


def grafica_real_vs_predicho(
    fechas: Sequence[object],
    y_real: Sequence[float],
    y_predicho: Sequence[float],
    ruta: Path | None = None,
) -> Path:
    """Grafica la serie real frente a la predicha y la correspondencia punto a punto.

    Args:
        fechas: Etiquetas temporales de las observaciones.
        y_real: Ventas observadas.
        y_predicho: Ventas estimadas.
        ruta: Ruta de la imagen. Por defecto, ``docs/figuras/real_vs_predicho.png``.

    Returns:
        Ruta de la imagen escrita.
    """
    _preparar_eje()
    destino = ruta if ruta is not None else DIR_FIGURAS_MODELOS / "real_vs_predicho.png"
    real = np.asarray(y_real, dtype=float)
    predicho = np.asarray(y_predicho, dtype=float)

    figura, (temporal, dispersion) = plt.subplots(1, 2, figsize=(14, 5))
    temporal.plot(fechas, real, color=COLOR_REAL, linewidth=1, label="Real")
    temporal.plot(
        fechas, predicho, color=COLOR_PREDICHO, linewidth=1.2, alpha=0.85, label="Predicho"
    )
    temporal.set_title("Ventas semanales: real vs predicho")
    temporal.set_ylabel("Ventas (Bs)")
    temporal.legend(loc="upper right")
    temporal.tick_params(axis="x", rotation=45)

    limite = [min(real.min(), predicho.min()), max(real.max(), predicho.max())]
    dispersion.scatter(real, predicho, alpha=0.35, s=18, color=COLOR_REAL)
    dispersion.plot(limite, limite, color=COLOR_PREDICHO, linestyle="--", label="Ideal")
    dispersion.set_title("Correspondencia real vs predicho")
    dispersion.set_xlabel("Ventas reales (Bs)")
    dispersion.set_ylabel("Ventas predichas (Bs)")
    dispersion.legend(loc="upper left")

    return _guardar_figura(figura, destino)


def grafica_residuos(
    fechas: Sequence[object],
    y_real: Sequence[float],
    y_predicho: Sequence[float],
    ruta: Path | None = None,
) -> Path:
    """Grafica la evolución y la distribución de los residuos.

    Args:
        fechas: Etiquetas temporales de las observaciones.
        y_real: Ventas observadas.
        y_predicho: Ventas estimadas.
        ruta: Ruta de la imagen. Por defecto, ``docs/figuras/residuos.png``.

    Returns:
        Ruta de la imagen escrita.
    """
    _preparar_eje()
    destino = ruta if ruta is not None else DIR_FIGURAS_MODELOS / "residuos.png"
    residuos = np.asarray(y_real, dtype=float) - np.asarray(y_predicho, dtype=float)

    figura, (temporal, histograma) = plt.subplots(1, 2, figsize=(14, 5))
    temporal.plot(fechas, residuos, color=COLOR_RESIDUO, linewidth=0.9, alpha=0.8)
    temporal.axhline(0.0, color="black", linestyle="--", linewidth=1)
    temporal.set_title("Residuos en el tiempo")
    temporal.set_ylabel("Real - predicho (Bs)")
    temporal.tick_params(axis="x", rotation=45)

    histograma.hist(residuos, bins=40, color=COLOR_RESIDUO, alpha=0.75)
    histograma.axvline(0.0, color="black", linestyle="--", linewidth=1)
    histograma.set_title("Distribución de residuos")
    histograma.set_xlabel("Real - predicho (Bs)")
    histograma.set_ylabel("Frecuencia")

    return _guardar_figura(figura, destino)


def guardar_reporte(
    fechas: Sequence[object],
    y_real: Sequence[float],
    y_predicho: Sequence[float],
    tabla: pd.DataFrame,
) -> dict[str, str]:
    """Guarda la tabla y las dos figuras de diagnóstico del mejor modelo.

    Args:
        fechas: Etiquetas temporales de la prueba.
        y_real: Ventas observadas.
        y_predicho: Ventas estimadas por el modelo seleccionado.
        tabla: Tabla comparativa de todos los modelos.

    Returns:
        Diccionario con las rutas relativas de los archivos generados.
    """
    rutas_csv, rutas_md = guardar_tabla(tabla)
    figura_real = grafica_real_vs_predicho(fechas, y_real, y_predicho)
    figura_residuos = grafica_residuos(fechas, y_real, y_predicho)
    return {
        "tabla_csv": str(rutas_csv),
        "tabla_markdown": str(rutas_md),
        "real_vs_predicho": str(figura_real),
        "residuos": str(figura_residuos),
        "generado": datetime.now().isoformat(timespec="seconds"),
    }
