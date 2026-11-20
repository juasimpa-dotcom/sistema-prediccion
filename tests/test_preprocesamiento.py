"""Pruebas de ingeniería de características y ausencia de fuga de datos."""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import Ridge

from config import (
    CARACTERISTICAS_CATEGORICAS,
    CARACTERISTICAS_NUMERICAS,
    COLUMNA_META_OBJETIVO,
    COLUMNA_OBJETIVO,
    DIVISIONES_TIEMPO,
    LAGS_VENTAS,
    SEMILLA,
    VENTANAS_MEDIA_MOVIL,
)
from ml.preprocesamiento import (
    construir_dataset_supervisado,
    construir_pipeline,
    construir_preprocesador,
    dividir_temporal,
    divisor_tiempo,
    preparar_entrada,
)


def test_esquema_supervisado(supervisado: pd.DataFrame) -> None:
    """La tabla incluye identificadores, características, objetivo y meta."""
    esperadas = {
        "fecha_origen",
        "fecha_objetivo",
        "sucursal",
        "categoria",
        *CARACTERISTICAS_NUMERICAS,
        *CARACTERISTICAS_CATEGORICAS,
        COLUMNA_OBJETIVO,
        COLUMNA_META_OBJETIVO,
    }
    assert esperadas <= set(supervisado.columns)
    assert not supervisado[COLUMNA_OBJETIVO].isna().any()


def test_objetivo_es_venta_de_la_semana_siguiente(
    crudo: pd.DataFrame, supervisado: pd.DataFrame
) -> None:
    """El objetivo coincide con las ventas reales de t+1 de la misma serie."""
    ventas = crudo.set_index(["fecha_semana", "sucursal", "categoria"])["ventas_bs"]
    muestra = supervisado.sample(25, random_state=SEMILLA)
    for _, fila in muestra.iterrows():
        real = ventas.loc[(fila["fecha_objetivo"], fila["sucursal"], fila["categoria"])]
        assert fila[COLUMNA_OBJETIVO] == pytest.approx(real)

    fechas = supervisado["fecha_objetivo"] - supervisado["fecha_origen"]
    assert (fechas == timedelta(days=7)).all()


def test_lags_y_medias_usan_solo_pasado(crudo: pd.DataFrame, supervisado: pd.DataFrame) -> None:
    """Cada lag y media móvil coincide con ventas de semanas anteriores a t+1."""
    ventas = crudo.set_index(["fecha_semana", "sucursal", "categoria"])["ventas_bs"]
    muestra = supervisado.sample(20, random_state=SEMILLA)
    for _, fila in muestra.iterrows():
        clave = (fila["sucursal"], fila["categoria"])
        for lag in LAGS_VENTAS:
            fecha = fila["fecha_origen"] - timedelta(weeks=lag - 1)
            assert fila[f"ventas_lag_{lag}"] == pytest.approx(ventas.loc[(fecha, *clave)])
            assert fecha < fila["fecha_objetivo"]

        historial = [
            ventas.loc[(fila["fecha_origen"] - timedelta(weeks=i), *clave)]
            for i in range(max(VENTANAS_MEDIA_MOVIL))
        ]
        for ventana in VENTANAS_MEDIA_MOVIL:
            assert fila[f"ventas_media_{ventana}"] == pytest.approx(np.mean(historial[:ventana]))


def test_modificar_futuro_no_cambia_caracteristicas(
    crudo: pd.DataFrame, supervisado: pd.DataFrame
) -> None:
    """Alterar las ventas de t+1 cambia el objetivo, nunca las características de t."""
    fila = supervisado.iloc[50]
    alterado = crudo.copy()
    mascara = (
        (alterado["fecha_semana"] == fila["fecha_objetivo"])
        & (alterado["sucursal"] == fila["sucursal"])
        & (alterado["categoria"] == fila["categoria"])
    )
    assert mascara.any()
    alterado.loc[mascara, "ventas_bs"] = alterado.loc[mascara, "ventas_bs"] * 5

    nuevo = construir_dataset_supervisado(alterado)
    misma = nuevo[
        (nuevo["fecha_origen"] == fila["fecha_origen"])
        & (nuevo["sucursal"] == fila["sucursal"])
        & (nuevo["categoria"] == fila["categoria"])
    ].iloc[0]

    for columna in [*CARACTERISTICAS_NUMERICAS, *CARACTERISTICAS_CATEGORICAS]:
        original = fila[columna]
        if isinstance(original, str):
            assert misma[columna] == original, columna
        elif pd.isna(original):
            assert pd.isna(misma[columna]), columna
        else:
            assert misma[columna] == pytest.approx(original), columna
    assert misma[COLUMNA_OBJETIVO] != pytest.approx(fila[COLUMNA_OBJETIVO])


def test_calendario_corresponde_a_semana_objetivo(
    supervisado: pd.DataFrame,
) -> None:
    """Mes, temporada y feriado se derivan de la semana a predecir."""
    assert (supervisado["mes"] == supervisado["fecha_objetivo"].dt.month).all()
    cambios = supervisado[
        supervisado["fecha_origen"].dt.month != supervisado["fecha_objetivo"].dt.month
    ]
    assert not cambios.empty
    assert (cambios["mes"] == cambios["fecha_objetivo"].dt.month).all()
    assert supervisado["temporada_objetivo"].notna().all()
    assert set(supervisado["es_feriado_objetivo"]) <= {0, 1}


def test_preparar_entrada_reproduce_caracteristicas(
    crudo: pd.DataFrame, supervisado: pd.DataFrame, columnas: list[str]
) -> None:
    """El helper de inferencia genera las mismas variables que el entrenamiento."""
    fila = supervisado.iloc[100]
    historial = crudo[
        (crudo["sucursal"] == fila["sucursal"])
        & (crudo["categoria"] == fila["categoria"])
        & (crudo["fecha_semana"] <= fila["fecha_origen"])
    ]
    entrada = preparar_entrada(historial, fecha_objetivo=fila["fecha_objetivo"])
    for columna in columnas:
        if columna in entrada.columns and columna not in CARACTERISTICAS_CATEGORICAS:
            original = fila[columna]
            if pd.isna(original):
                assert pd.isna(entrada.iloc[0][columna]), columna
            else:
                assert entrada.iloc[0][columna] == pytest.approx(original), columna


def test_preparar_entrada_valida_historial(crudo: pd.DataFrame) -> None:
    """Se rechaza un historial corto o de varias series."""
    serie = crudo[(crudo["sucursal"] == "Sopocachi") & (crudo["categoria"] == "pollo")]
    with pytest.raises(ValueError, match="al menos"):
        preparar_entrada(serie.head(3))
    with pytest.raises(ValueError, match="una sola"):
        preparar_entrada(crudo.head(20))


def test_division_temporal_sin_solapamiento(supervisado: pd.DataFrame) -> None:
    """Entrenamiento y prueba son disjuntos y cronológicamente ordenados."""
    entrenamiento, prueba = dividir_temporal(supervisado)
    assert entrenamiento["fecha_objetivo"].max() < prueba["fecha_objetivo"].min()
    assert len(entrenamiento) + len(prueba) == len(supervisado)
    assert entrenamiento["fecha_objetivo"].is_monotonic_increasing


def test_divisor_tiempo_respeta_semanas(supervisado: pd.DataFrame) -> None:
    """Los pliegues de TimeSeriesSplit no mezclan semanas entre sí."""
    entrenamiento, _ = dividir_temporal(supervisado)
    divisiones = divisor_tiempo(entrenamiento)
    assert len(divisiones) == DIVISIONES_TIEMPO
    for train, valid in divisiones:
        fecha_train = entrenamiento.iloc[train]["fecha_objetivo"].max()
        fecha_valid = entrenamiento.iloc[valid]["fecha_objetivo"].min()
        assert fecha_train < fecha_valid
        assert not set(train) & set(valid)


def test_imputacion_elimina_nan(supervisado: pd.DataFrame, columnas: list[str]) -> None:
    """El pipeline imputa faltantes antes de entregar datos al modelo."""
    datos = supervisado.iloc[:300]
    caracteristicas = datos.loc[:, columnas].copy()
    caracteristicas.iloc[:10, caracteristicas.columns.get_loc("stock_inicial")] = np.nan
    caracteristicas.iloc[5:15, caracteristicas.columns.get_loc("sucursal")] = None

    pipeline = construir_pipeline(Ridge())
    pipeline.fit(caracteristicas, datos[COLUMNA_OBJETIVO])
    matriz = pipeline.named_steps["preprocesador"].transform(caracteristicas)
    assert not np.isnan(matriz).any()


def test_codificacion_de_categoricas(supervisado: pd.DataFrame, columnas: list[str]) -> None:
    """Las categóricas se transforman en columnas One-Hot con nombre propio."""
    preprocesador = construir_preprocesador()
    preprocesador.fit(supervisado.loc[:200, columnas])
    nombres = list(preprocesador.get_feature_names_out())
    assert any("sucursal" in nombre for nombre in nombres)
    assert any("categoria" in nombre for nombre in nombres)
    assert any("temporada_objetivo" in nombre for nombre in nombres)
    assert len(nombres) > len(CARACTERISTICAS_NUMERICAS)
