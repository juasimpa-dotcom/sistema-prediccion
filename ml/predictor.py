"""Fachada tipada para consumir el modelo entrenado desde otras capas del sistema."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from config import ARCHIVO_MODELO, CARACTERISTICAS_CATEGORICAS, CARACTERISTICAS_NUMERICAS, EPSILON
from ml.entrenamiento import cargar_artefacto, dispersion_arboles, estimar_confianza
from ml.explicabilidad import explicar_local, resumir_factores
from ml.preprocesamiento import preparar_entrada

if TYPE_CHECKING:
    from sklearn.pipeline import Pipeline

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PrediccionVentas:
    """Resultado tipado de una predicción de ventas.

    Attributes:
        valor_predicho: Ventas estimadas para la semana siguiente, en bolivianos.
        cumplimiento_esperado_pct: Porcentaje esperado de la meta de ventas.
        confianza: Factor de certeza en el rango ``[0, 1]``.
        principales_factores: Descripciones legibles de las variables más influyentes.
    """

    valor_predicho: float
    cumplimiento_esperado_pct: float
    confianza: float
    principales_factores: tuple[str, ...]


class PredictorVentas:
    """Fachada que carga el artefacto y expone ``predecir(entrada)``.

    Attributes:
        pipeline: Pipeline ajustado con preprocesamiento y modelo.
        metadatos: Información de versión, métricas y calibración del artefacto.
        fondo: Muestra transformada de referencia para SHAP.
    """

    def __init__(
        self,
        ruta_modelo: Path | str = ARCHIVO_MODELO,
        incluir_explicacion: bool = True,
    ) -> None:
        """Carga el modelo y su calibración desde disco.

        Args:
            ruta_modelo: Ruta del archivo joblib generado por ``ml.entrenamiento``.
            incluir_explicacion: Si se calculan factores SHAP en cada predicción.
        """
        artefacto = cargar_artefacto(Path(ruta_modelo))
        self.pipeline: Pipeline = artefacto["pipeline"]
        self.metadatos: dict = artefacto["metadatos"]
        self.fondo = artefacto.get("fondo")
        self.incluir_explicacion = incluir_explicacion
        calibracion = self.metadatos.get("calibracion", {})
        self.desvio_residuos: float = float(calibracion.get("desvio_residuos_relativos", 0.2))
        self.mape: float = float(calibracion.get("mape_prueba", 20.0))
        self.meta_promedio: float = float(calibracion.get("meta_promedio", 1.0))
        LOGGER.info(
            "Predictor cargado: %s (versión %s)",
            self.metadatos.get("nombre_modelo", "desconocido"),
            self.metadatos.get("version", "desconocida"),
        )

    def _preparar_entrada(self, entrada: Mapping[str, object] | pd.DataFrame) -> pd.DataFrame:
        """Normaliza la entrada a un DataFrame con las columnas de características.

        Args:
            entrada: Diccionario de características, DataFrame de una fila, o
                diccionario con clave ``historial`` de semanas crudas.

        Returns:
            DataFrame de una sola fila con todas las columnas recibidas.

        Raises:
            ValueError: Si faltan columnas obligatorias o el historial es inválido.
        """
        if isinstance(entrada, Mapping) and "historial" in entrada:
            fila = preparar_entrada(
                pd.DataFrame(entrada["historial"]),
                fecha_objetivo=entrada.get("fecha_objetivo"),
            )
        elif isinstance(entrada, pd.DataFrame):
            fila = entrada.iloc[[0]].copy()
        else:
            fila = pd.DataFrame([entrada])

        columnas = [*CARACTERISTICAS_NUMERICAS, *CARACTERISTICAS_CATEGORICAS]
        faltantes = sorted(set(columnas) - set(fila.columns))
        if faltantes:
            raise ValueError(f"Faltan columnas en la entrada: {faltantes}")
        return fila

    def predecir(self, entrada: Mapping[str, object] | pd.DataFrame) -> PrediccionVentas:
        """Predice las ventas de la semana siguiente y sus metadatos asociados.

        Args:
            entrada: Características de la semana cerrada ``t``. Puede incluir
                un ``historial`` para calcular lags automáticamente.

        Returns:
            Dataclass con predicción, cumplimiento, confianza y factores SHAP.
        """
        fila = self._preparar_entrada(entrada)
        valor = float(self.pipeline.predict(fila)[0])

        meta = self.meta_promedio
        if "meta_objetivo" in fila.columns:
            meta = float(fila["meta_objetivo"].iloc[0])
        elif "meta_ventas_bs" in fila.columns:
            meta = float(fila["meta_ventas_bs"].iloc[0])
        cumplimiento = valor / max(meta, EPSILON) * 100.0

        dispersion = dispersion_arboles(self.pipeline, fila)
        referencia = float(fila["ventas_lag_1"].iloc[0])
        confianza = estimar_confianza(
            valor, referencia, self.desvio_residuos, self.mape, dispersion
        )

        if self.incluir_explicacion:
            factores = resumir_factores(explicar_local(self.pipeline, fila, fondo=self.fondo))
        else:
            factores = (f"ventas_lag_1={referencia:,.0f} Bs",)

        return PrediccionVentas(
            valor_predicho=round(valor, 2),
            cumplimiento_esperado_pct=round(cumplimiento, 2),
            confianza=round(confianza, 4),
            principales_factores=factores,
        )
