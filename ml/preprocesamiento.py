"""Limpieza e ingeniería de características sin fuga de información.

La convención temporal es explícita: la fila ``t`` usa datos **cerrados** de la
semana ``t`` y el calendario ya conocido de la semana ``t + 1``, que es el
objetivo. Nunca se consulta una realización futura (ventas, promociones,
afluencia, etc.) para construir las características de una predicción.

Uso:
    python -m ml.preprocesamiento  # imprime un resumen del dataset supervisado
"""

from __future__ import annotations

import logging
from datetime import date
from functools import cache
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from config import (
    CARACTERISTICAS_CATEGORICAS,
    CARACTERISTICAS_NUMERICAS,
    CLAVE_SERIE,
    COLUMNA_META_OBJETIVO,
    COLUMNA_OBJETIVO,
    COLUMNAS_IDENTIFICADOR,
    DIVISIONES_TIEMPO,
    FECHA_CORTE_ENTRENAMIENTO,
    LAGS_VENTAS,
    TEMPORADA_POR_MES,
    VENTANAS_MEDIA_MOVIL,
)
from data.generar_dataset import feriados_de_bolivia

if TYPE_CHECKING:
    from sklearn.base import BaseEstimator

LOGGER = logging.getLogger(__name__)

DIAS_POR_SEMANA: int = 7


@cache
def _feriados(anio: int) -> frozenset[date]:
    """Devuelve los feriados de un año en una estructura inmutable y cacheada.

    Args:
        anio: Año a consultar.

    Returns:
        Conjunto de fechas feriadas.
    """
    return frozenset(feriados_de_bolivia(anio))


def es_feriado(fecha: pd.Timestamp | date) -> int:
    """Indica si la semana que empieza en ``fecha`` contiene algún feriado.

    Args:
        fecha: Lunes que inicia la semana.

    Returns:
        1 si hay feriado en la semana, 0 en caso contrario.
    """
    fecha = pd.Timestamp(fecha)
    dias = pd.date_range(fecha, periods=DIAS_POR_SEMANA, freq="D")
    return int(any(dia.date() in _feriados(dia.year) for dia in dias))


def _caracteristicas_calendario(fecha_objetivo: pd.Series) -> pd.DataFrame:
    """Deriva las variables de calendario conocidas antes de la semana objetivo.

    Args:
        fecha_objetivo: Fechas de la semana a predecir.

    Returns:
        DataFrame con semana ISO, mes, temporada y bandera de feriado.
    """
    return pd.DataFrame(
        {
            "semana_anio": fecha_objetivo.dt.isocalendar().week.astype(int),
            "mes": fecha_objetivo.dt.month.astype(int),
            "temporada_objetivo": fecha_objetivo.dt.month.map(TEMPORADA_POR_MES),
            "es_feriado_objetivo": fecha_objetivo.map(es_feriado).astype(int),
        },
        index=fecha_objetivo.index,
    )


def construir_dataset_supervisado(dataset: pd.DataFrame) -> pd.DataFrame:
    """Genera la tabla supervisada: cada fila predice las ventas de la semana siguiente.

    Args:
        dataset: Dataset crudo con una fila por semana, sucursal y categoría.

    Returns:
        DataFrame con identificadores, características, objetivo y meta objetivo.
        Las semanas sin historial suficiente se descartan.
    """
    datos = dataset.copy()
    datos["fecha_semana"] = pd.to_datetime(datos["fecha_semana"])
    datos = datos.sort_values([*CLAVE_SERIE, "fecha_semana"]).reset_index(drop=True)

    ventas = datos.groupby(list(CLAVE_SERIE), sort=False)["ventas_bs"]
    datos[COLUMNA_OBJETIVO] = ventas.shift(-1)
    datos[COLUMNA_META_OBJETIVO] = datos.groupby(list(CLAVE_SERIE), sort=False)[
        "meta_ventas_bs"
    ].shift(-1)

    # Respecto al objetivo: lag_1 es la semana t (ya cerrada), lag_2 la t-1, etc.
    datos["ventas_lag_1"] = datos["ventas_bs"]
    datos["ventas_lag_2"] = ventas.shift(1)
    datos["ventas_lag_4"] = ventas.shift(3)
    for ventana in VENTANAS_MEDIA_MOVIL:
        datos[f"ventas_media_{ventana}"] = ventas.transform(
            lambda serie, v=ventana: serie.rolling(v, min_periods=v).mean()
        )

    datos["fecha_origen"] = datos["fecha_semana"]
    datos["fecha_objetivo"] = datos["fecha_semana"] + pd.Timedelta(days=DIAS_POR_SEMANA)
    calendario = _caracteristicas_calendario(datos["fecha_objetivo"])
    datos = pd.concat([datos, calendario], axis=1)

    datos["en_promocion"] = pd.to_numeric(datos["en_promocion"], errors="coerce")
    for columna in CARACTERISTICAS_NUMERICAS:
        datos[columna] = pd.to_numeric(datos[columna], errors="coerce")

    columnas_historia = [f"ventas_lag_{lag}" for lag in LAGS_VENTAS] + [
        f"ventas_media_{v}" for v in VENTANAS_MEDIA_MOVIL
    ]
    datos = datos.dropna(subset=[COLUMNA_OBJETIVO, *columnas_historia])

    columnas = list(
        dict.fromkeys(
            [
                *COLUMNAS_IDENTIFICADOR,
                *CARACTERISTICAS_NUMERICAS,
                *CARACTERISTICAS_CATEGORICAS,
                COLUMNA_OBJETIVO,
                COLUMNA_META_OBJETIVO,
            ]
        )
    )
    return (
        datos.loc[:, columnas].sort_values(["fecha_objetivo", *CLAVE_SERIE]).reset_index(drop=True)
    )


def preparar_entrada(
    historial: pd.DataFrame,
    fecha_objetivo: date | str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Construye una fila de características a partir del historial de una serie.

    El historial debe pertenecer a una sola combinación sucursal-categoría y
    contener al menos ``HISTORIA_MINIMA_SEMANAS`` semanas consecutivas.

    Args:
        historial: Filas crudas ordenadas por fecha, con la semana ``t`` al final.
        fecha_objetivo: Fecha de la semana a predecir. Por defecto, ``t + 7`` días.

    Returns:
        DataFrame de una sola fila con las columnas de características.

    Raises:
        ValueError: Si el historial es demasiado corto o no es de una sola serie.
    """
    datos = historial.copy()
    datos["fecha_semana"] = pd.to_datetime(datos["fecha_semana"])
    datos = datos.sort_values("fecha_semana").reset_index(drop=True)

    minimo = max(LAGS_VENTAS + VENTANAS_MEDIA_MOVIL)
    if len(datos) < minimo:
        raise ValueError(f"Se requieren al menos {minimo} semanas de historial")
    for columna in CLAVE_SERIE:
        if columna in datos and datos[columna].nunique() != 1:
            raise ValueError(f"El historial debe corresponder a una sola {columna}")

    ventas = datos["ventas_bs"].astype(float)
    ultima = datos.iloc[-1]
    fecha_origen = pd.Timestamp(ultima["fecha_semana"])
    objetivo = (
        fecha_origen + pd.Timedelta(days=DIAS_POR_SEMANA)
        if fecha_objetivo is None
        else pd.Timestamp(fecha_objetivo)
    )

    fila: dict[str, object] = {
        "fecha_origen": fecha_origen,
        "fecha_objetivo": objetivo,
        "sucursal": ultima["sucursal"],
        "categoria": ultima["categoria"],
    }
    for lag in LAGS_VENTAS:
        fila[f"ventas_lag_{lag}"] = float(ventas.iloc[-lag])
    for ventana in VENTANAS_MEDIA_MOVIL:
        fila[f"ventas_media_{ventana}"] = float(ventas.iloc[-ventana:].mean())

    for columna in CARACTERISTICAS_NUMERICAS:
        if columna not in fila and columna in datos:
            fila[columna] = ultima[columna]

    calendario = _caracteristicas_calendario(pd.Series([objetivo]))
    for columna in calendario.columns:
        fila[columna] = calendario.iloc[0][columna]

    columnas = [*COLUMNAS_IDENTIFICADOR, *CARACTERISTICAS_NUMERICAS, *CARACTERISTICAS_CATEGORICAS]
    columnas = list(dict.fromkeys(columnas))
    return pd.DataFrame([fila])[columnas]


def dividir_temporal(
    dataset: pd.DataFrame,
    fecha_corte: date = FECHA_CORTE_ENTRENAMIENTO,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separa la tabla supervisada en entrenamiento y prueba por fecha objetivo.

    Args:
        dataset: Tabla supervisada ordenada cronológicamente.
        fecha_corte: Última fecha incluida en entrenamiento.

    Returns:
        Par ``(entrenamiento, prueba)`` sin solapamiento temporal.
    """
    corte = pd.Timestamp(fecha_corte)
    entrenamiento = dataset.loc[dataset["fecha_objetivo"] <= corte]
    prueba = dataset.loc[dataset["fecha_objetivo"] > corte]
    if entrenamiento.empty or prueba.empty:
        raise ValueError("La fecha de corte deja alguno de los conjuntos vacío")
    return entrenamiento.reset_index(drop=True), prueba.reset_index(drop=True)


def divisor_tiempo(
    dataset: pd.DataFrame,
    numero_divisiones: int = DIVISIONES_TIEMPO,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Crea pliegues de ``TimeSeriesSplit`` respetando semanas completas.

    Args:
        dataset: Conjunto de entrenamiento con columna ``fecha_objetivo``.
        numero_divisiones: Cantidad de pliegues.

    Returns:
        Lista de pares de índices ``(entrenamiento, validación)``.
    """
    semanas = np.sort(dataset["fecha_objetivo"].unique())
    if numero_divisiones >= len(semanas):
        raise ValueError("Hay menos semanas que divisiones solicitadas")

    posicion = {semana: indice for indice, semana in enumerate(semanas)}
    codigos = dataset["fecha_objetivo"].map(posicion).to_numpy()
    divisiones: list[tuple[np.ndarray, np.ndarray]] = []
    for semanas_train, semanas_valid in TimeSeriesSplit(n_splits=numero_divisiones).split(semanas):
        train = np.flatnonzero(np.isin(codigos, semanas_train))
        valid = np.flatnonzero(np.isin(codigos, semanas_valid))
        divisiones.append((train, valid))
    return divisiones


def construir_preprocesador() -> ColumnTransformer:
    """Compone imputación y codificación dentro de un ``ColumnTransformer``.

    Returns:
        Transformador ajustable, sin estado, para variables numéricas y categóricas.
    """
    numerico = Pipeline([("imputador", SimpleImputer(strategy="median"))])
    categorico = Pipeline(
        [
            ("imputador", SimpleImputer(strategy="most_frequent")),
            ("codificador", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )
    return ColumnTransformer(
        [
            ("num", numerico, list(CARACTERISTICAS_NUMERICAS)),
            ("cat", categorico, list(CARACTERISTICAS_CATEGORICAS)),
        ],
        remainder="drop",
        verbose_feature_names_out=True,
    )


def construir_pipeline(estimador: BaseEstimator, escalar: bool = True) -> Pipeline:
    """Envuelve un estimador con el preprocesador y, opcionalmente, escalado.

    Args:
        estimador: Modelo de regresión sin ajustar.
        escalar: Si se agrega ``StandardScaler`` antes del modelo.

    Returns:
        Pipeline completo y reproducible.
    """
    pasos: list[tuple[str, object]] = [("preprocesador", construir_preprocesador())]
    if escalar:
        pasos.append(("escalador", StandardScaler()))
    pasos.append(("modelo", estimador))
    return Pipeline(pasos)


def obtener_nombres_caracteristicas(pipeline: Pipeline) -> list[str]:
    """Recupera los nombres de las columnas después del preprocesamiento.

    Args:
        pipeline: Pipeline ya ajustado.

    Returns:
        Lista de nombres de características transformadas.
    """
    return list(pipeline.named_steps["preprocesador"].get_feature_names_out())


def main() -> None:
    """Imprime un resumen del dataset supervisado y de la división temporal."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    from config import ARCHIVO_VENTAS_CRUDO  # importación local: solo para el script

    dataset = pd.read_csv(ARCHIVO_VENTAS_CRUDO, parse_dates=["fecha_semana"])
    supervisado = construir_dataset_supervisado(dataset)
    entrenamiento, prueba = dividir_temporal(supervisado)
    columnas = [*CARACTERISTICAS_NUMERICAS, *CARACTERISTICAS_CATEGORICAS]
    preprocesador = construir_preprocesador().fit(supervisado[columnas])
    print(f"Filas supervisadas: {len(supervisado):,}")
    print(f"Entrenamiento: {len(entrenamiento):,} filas | Prueba: {len(prueba):,} filas")
    print(f"Características después de codificar: {len(preprocesador.get_feature_names_out())}")
    print(supervisado.head(3).to_string(index=False))


if __name__ == "__main__":
    main()
