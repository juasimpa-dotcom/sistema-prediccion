"""Pruebas del generador del dataset simulado de ventas."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from config import (
    CATEGORIAS,
    COLUMNAS_CON_FALTANTES,
    COLUMNAS_CRITICAS,
    COLUMNAS_DATASET,
    MERMA_MAXIMA_PCT,
    PARAMETROS_GENERACION,
    SEMILLA,
    SUCURSALES,
    TEMPORADAS,
)
from data.generar_dataset import (
    construir_calendario,
    domingo_de_pascua,
    feriados_de_bolivia,
    generar_dataset,
    guardar_dataset,
    resumen_estadistico,
)

PROPORCION_FALTANTES_ESPERADA = PARAMETROS_GENERACION.proporcion_faltantes
TOLERANCIA_FALTANTES = 0.012


@pytest.fixture(scope="module")
def dataset() -> pd.DataFrame:
    """Dataset generado con la semilla del proyecto."""
    return generar_dataset(semilla=SEMILLA)


def test_esquema_de_columnas(dataset: pd.DataFrame) -> None:
    """El dataset expone exactamente las columnas acordadas y en orden."""
    assert tuple(dataset.columns) == COLUMNAS_DATASET


def test_dimensiones_y_combinaciones(dataset: pd.DataFrame) -> None:
    """Cada semana combina todas las sucursales con todas las categorías."""
    filas_esperadas = PARAMETROS_GENERACION.numero_semanas * len(SUCURSALES) * len(CATEGORIAS)
    assert len(dataset) == filas_esperadas
    assert set(dataset["sucursal"]) == set(SUCURSALES)
    assert set(dataset["categoria"]) == set(CATEGORIAS)
    assert dataset["fecha_semana"].nunique() == PARAMETROS_GENERACION.numero_semanas

    combinaciones = dataset.groupby(["fecha_semana", "sucursal", "categoria"]).size()
    assert (combinaciones == 1).all()


def test_fechas_semanales(dataset: pd.DataFrame) -> None:
    """Las fechas son lunes consecutivos que empiezan en la fecha configurada."""
    fechas = dataset["fecha_semana"].drop_duplicates().sort_values().reset_index(drop=True)
    assert fechas.iloc[0].date() == PARAMETROS_GENERACION.fecha_inicio
    assert (fechas.dt.day_of_week == 0).all()
    assert (fechas.diff().dropna() == pd.Timedelta(days=7)).all()
    assert not dataset["fecha_semana"].isna().any()


def test_sin_duplicados_por_sucursal_categoria(dataset: pd.DataFrame) -> None:
    """No existe más de una observación por semana, sucursal y categoría."""
    duplicados = dataset.duplicated(subset=["fecha_semana", "sucursal", "categoria"])
    assert not duplicados.any()


def test_rangos_validos(dataset: pd.DataFrame) -> None:
    """Las variables numéricas se mantienen en rangos de negocio razonables."""
    assert (dataset["ventas_bs"] > 0).all()
    assert (dataset["unidades_vendidas"] >= 1).all()
    assert (dataset["precio_promedio"] > 0).all()
    assert (dataset["meta_ventas_bs"] > 0).all()
    assert (dataset["cumplimiento_meta_pct"] > 0).all()
    assert dataset["cumplimiento_meta_pct"].max() < 1_000

    descuento = dataset["descuento_pct"].dropna()
    assert descuento.between(0, PARAMETROS_GENERACION.descuento_max_pct).all()

    stock = dataset["stock_inicial"].dropna()
    assert (stock >= 0).all()

    merma = dataset["merma_pct"].dropna()
    assert merma.between(0, MERMA_MAXIMA_PCT).all()

    temperatura = dataset["temperatura_media"].dropna()
    assert temperatura.between(-5, 25).all()

    afluencia = dataset["afluencia_clientes"].dropna()
    assert (afluencia > 0).all()

    personal = dataset["personal_asignado"].dropna()
    assert personal.between(1, 15).all()


def test_variables_categoricas(dataset: pd.DataFrame) -> None:
    """Temporadas, feriados y promociones usan dominios cerrados."""
    assert set(dataset["temporada"]) <= set(TEMPORADAS)
    assert dataset["temporada"].notna().all()
    assert dataset["en_promocion"].dtype == bool
    assert dataset["es_feriado_semana"].dtype == bool
    assert dataset["es_feriado_semana"].any()


def test_cumplimiento_derivado(dataset: pd.DataFrame) -> None:
    """El cumplimiento se calcula como ventas sobre meta en porcentaje."""
    esperado = (dataset["ventas_bs"] / dataset["meta_ventas_bs"] * 100).round(2)
    pd.testing.assert_series_equal(
        dataset["cumplimiento_meta_pct"],
        esperado,
        check_names=False,
        rtol=1e-9,
        atol=0.01,
    )


def test_valores_faltantes_controlados(dataset: pd.DataFrame) -> None:
    """Solo las columnas no críticas presentan faltantes y en proporción baja."""
    for columna in COLUMNAS_CRITICAS:
        assert not dataset[columna].isna().any(), f"{columna} no debe tener faltantes"

    for columna in COLUMNAS_CON_FALTANTES:
        proporcion = dataset[columna].isna().mean()
        assert (
            abs(proporcion - PROPORCION_FALTANTES_ESPERADA) < TOLERANCIA_FALTANTES
        ), f"{columna} tiene {proporcion:.1%} de faltantes"


def test_promociones_coherentes(dataset: pd.DataFrame) -> None:
    """Solo hay descuento cuando la fila está marcada como promoción."""
    sin_descuento = dataset["descuento_pct"] == 0
    assert not dataset.loc[sin_descuento, "en_promocion"].any()

    con_promocion = dataset["en_promocion"]
    assert (dataset.loc[con_promocion, "descuento_pct"].dropna() > 0).all()


def test_efectos_de_negocio(dataset: pd.DataFrame) -> None:
    """Estacionalidad y promociones dejan huella en las unidades vendidas."""
    diciembre = dataset[dataset["fecha_semana"].dt.month == 12]["unidades_vendidas"].mean()
    abril = dataset[dataset["fecha_semana"].dt.month == 4]["unidades_vendidas"].mean()
    assert diciembre > abril

    con_promocion = dataset.loc[dataset["en_promocion"], "unidades_vendidas"].mean()
    sin_promocion = dataset.loc[~dataset["en_promocion"], "unidades_vendidas"].mean()
    assert con_promocion > sin_promocion


def test_reproducibilidad(dataset: pd.DataFrame) -> None:
    """La misma semilla produce exactamente el mismo dataset."""
    repetido = generar_dataset(semilla=SEMILLA)
    pd.testing.assert_frame_equal(dataset, repetido)


def test_semilla_distinta_cambia_datos(dataset: pd.DataFrame) -> None:
    """Otra semilla produce valores distintos."""
    otro = generar_dataset(semilla=SEMILLA + 1)
    assert not dataset.equals(otro)
    assert tuple(otro.columns) == COLUMNAS_DATASET


def test_guardar_dataset(tmp_path) -> None:
    """El CSV escrito conserva filas, columnas y tipos de fecha."""
    dataset = generar_dataset(semilla=SEMILLA)
    ruta = guardar_dataset(dataset, ruta=tmp_path / "ventas.csv")

    assert ruta.exists()
    recuperado = pd.read_csv(ruta, parse_dates=["fecha_semana"])
    assert recuperado.shape == dataset.shape
    assert tuple(recuperado.columns) == COLUMNAS_DATASET
    assert recuperado["fecha_semana"].iloc[0].date() == PARAMETROS_GENERACION.fecha_inicio


def test_resumen_estadistico(dataset: pd.DataFrame) -> None:
    """El resumen estadístico cubre todas las columnas numéricas."""
    resumen = resumen_estadistico(dataset)
    assert {"count", "mean", "std", "min", "max"} <= set(resumen.columns)
    assert "ventas_bs" in resumen.index


def test_domingo_de_pascua() -> None:
    """El cálculo de Pascua coincide con fechas conocidas."""
    assert domingo_de_pascua(2024) == date(2024, 3, 31)
    assert domingo_de_pascua(2025) == date(2025, 4, 20)


def test_feriados_incluyen_moviles_y_locales() -> None:
    """Los feriados contemplan Carnaval, Semana Santa y la Efeméride de La Paz."""
    feriados_2024 = feriados_de_bolivia(2024)
    assert date(2024, 2, 12) in feriados_2024  # Lunes de Carnaval
    assert date(2024, 3, 29) in feriados_2024  # Viernes Santo
    assert date(2024, 7, 16) in feriados_2024  # Efeméride de La Paz
    assert date(2024, 8, 6) in feriados_2024


def test_calendario_coherente() -> None:
    """El calendario tiene una fila por semana con metadatos válidos."""
    calendario = construir_calendario()
    assert len(calendario) == PARAMETROS_GENERACION.numero_semanas
    assert (calendario["fecha_semana"].dt.day_of_week == 0).all()
    assert calendario["temporada"].isin(TEMPORADAS).all()
    assert calendario["es_feriado_semana"].dtype == bool
    assert calendario["es_feriado_semana"].any()
