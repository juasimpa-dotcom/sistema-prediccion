"""Generador del dataset simulado de ventas semanales del retail.

Construye dos años de observaciones semanales por sucursal y categoría con
estacionalidad, tendencia, promociones, quiebres de stock, merma, feriados,
diferencias entre sucursales y valores atípicos. El resultado se guarda en
``data/raw/ventas_semanales.csv``.

Uso:
    python -m data.generar_dataset
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from config import (
    AFLUENCIA_BASE_SUCURSAL,
    AJUSTE_ESTACIONAL_CATEGORIA,
    AJUSTE_TEMPERATURA_SUCURSAL,
    ARCHIVO_VENTAS_CRUDO,
    CATEGORIAS,
    COLUMNAS_CON_FALTANTES,
    COLUMNAS_DATASET,
    DIAS_POR_SEMANA,
    EFECTO_TERMICO_MERMA,
    ESTACIONALIDAD_MENSUAL,
    FACTOR_AFLUENCIA_FERIADO,
    FACTOR_META_SUCURSAL,
    FACTOR_PRECIO_SUCURSAL,
    FERIADOS_FIJOS,
    GRADOS_REFERENCIA_TERMICA,
    MERMA_BASE_CATEGORIA,
    MERMA_DESVIO_CATEGORIA,
    MERMA_MAXIMA_PCT,
    MERMA_MINIMA_PCT,
    MESES_POR_ANIO,
    META_MINIMA_BS,
    PARAMETROS_GENERACION,
    PENALIDAD_DEMANDA_MERMA,
    PERSONAL_BASE_CATEGORIA,
    PERSONAL_MAXIMO,
    PERSONAL_MINIMO,
    PRECIO_BASE_CATEGORIA,
    PRECIO_MINIMO_BS,
    SEMILLA,
    SENSIBILIDAD_TERMICA_CATEGORIA,
    SUCURSALES,
    TASA_CONVERSION_CATEGORIA,
    TEMPERATURA_MEDIA_MES,
    TEMPORADA_POR_MES,
    UNIDADES_MINIMAS,
    ParametrosGeneracion,
)

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Calendario y feriados
# ---------------------------------------------------------------------------
def domingo_de_pascua(anio: int) -> date:
    """Calcula la fecha del Domingo de Pascua con el algoritmo gregoriano.

    Args:
        anio: Año calendario a calcular.

    Returns:
        Fecha del Domingo de Pascua de ese año.
    """
    a = anio % 19
    b = anio // 100
    c = anio % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    desplazamiento = (32 + 2 * e + 2 * i - h - k) % 7
    correccion = (a + 11 * h + 22 * desplazamiento) // 451
    mes = (h + desplazamiento - 7 * correccion + 114) // 31
    dia = ((h + desplazamiento - 7 * correccion + 114) % 31) + 1
    return date(anio, mes, dia)


def feriados_de_bolivia(anio: int) -> dict[date, str]:
    """Devuelve los feriados bolivianos de un año, incluidos los móviles.

    Se incluye la Efeméride de La Paz porque todas las sucursales simuladas
    operan en el departamento de La Paz.

    Args:
        anio: Año calendario a calcular.

    Returns:
        Diccionario fecha -> nombre del feriado.
    """
    feriados = {date(anio, mes, dia): nombre for mes, dia, nombre in FERIADOS_FIJOS}
    pascua = domingo_de_pascua(anio)
    moviles = {
        pascua - timedelta(days=48): "Lunes de Carnaval",
        pascua - timedelta(days=47): "Martes de Carnaval",
        pascua - timedelta(days=3): "Jueves Santo",
        pascua - timedelta(days=2): "Viernes Santo",
        pascua + timedelta(days=60): "Corpus Christi",
    }
    feriados.update(moviles)
    return feriados


def construir_calendario(
    parametros: ParametrosGeneracion = PARAMETROS_GENERACION,
) -> pd.DataFrame:
    """Construye el calendario semanal con temporada y bandera de feriado.

    Args:
        parametros: Parámetros que definen el horizonte simulado.

    Returns:
        DataFrame con una fila por semana y columnas auxiliares de calendario.
    """
    fechas = pd.date_range(
        start=parametros.fecha_inicio,
        periods=parametros.numero_semanas,
        freq="W-MON",
    )
    feriados: set[date] = set()
    for anio in range(fechas.min().year, fechas.max().year + 2):
        feriados.update(feriados_de_bolivia(anio))

    registros = []
    for fecha in fechas:
        dias = pd.date_range(fecha, periods=DIAS_POR_SEMANA, freq="D")
        registros.append(
            {
                "fecha_semana": fecha,
                "mes": fecha.month,
                "temporada": TEMPORADA_POR_MES[fecha.month],
                "es_feriado_semana": any(dia.date() in feriados for dia in dias),
            }
        )
    return pd.DataFrame(registros)


def _producto_calendario(calendario: pd.DataFrame) -> pd.DataFrame:
    """Combina calendario, sucursales y categorías en todas sus combinaciones."""
    sucursales = pd.DataFrame({"sucursal": list(SUCURSALES)})
    categorias = pd.DataFrame({"categoria": list(CATEGORIAS)})
    return calendario.merge(sucursales, how="cross").merge(categorias, how="cross")


def tabla_estacional(categorias: tuple[str, ...] = CATEGORIAS) -> pd.DataFrame:
    """Construye la tabla de factores estacionales por categoría y mes.

    Args:
        categorias: Categorías a incluir en la tabla.

    Returns:
        DataFrame con columnas ``categoria``, ``mes`` y ``factor``.
    """
    registros = [
        {
            "categoria": categoria,
            "mes": mes,
            "factor": ESTACIONALIDAD_MENSUAL[mes]
            * AJUSTE_ESTACIONAL_CATEGORIA.get(categoria, {}).get(mes, 1.0),
        }
        for categoria in categorias
        for mes in range(1, MESES_POR_ANIO + 1)
    ]
    return pd.DataFrame(registros)


# ---------------------------------------------------------------------------
# Construcción de variables
# ---------------------------------------------------------------------------
def _factores_atipicos(
    rng: np.random.Generator,
    cantidad_filas: int,
    parametros: ParametrosGeneracion,
) -> np.ndarray:
    """Genera multiplicadores de afluencia para semanas anómalas."""
    factor = np.ones(cantidad_filas)
    cantidad = int(round(cantidad_filas * parametros.probabilidad_atipico))
    if cantidad == 0:
        return factor

    indices = rng.choice(cantidad_filas, size=cantidad, replace=False)
    es_caida = rng.random(cantidad) < parametros.probabilidad_atipico_negativo
    caidas = rng.uniform(*parametros.rango_atipico_bajo, size=cantidad)
    picos = rng.uniform(*parametros.rango_atipico_alto, size=cantidad)
    factor[indices] = np.where(es_caida, caidas, picos)
    return factor


def _agregar_temperatura(
    dataset: pd.DataFrame,
    rng: np.random.Generator,
    parametros: ParametrosGeneracion,
) -> pd.DataFrame:
    """Agrega la temperatura media semanal y su efecto sobre la demanda."""
    temperatura = (
        dataset["mes"].map(TEMPERATURA_MEDIA_MES).astype(float)
        + dataset["sucursal"].map(AJUSTE_TEMPERATURA_SUCURSAL)
        + rng.normal(0.0, parametros.ruido_temperatura, len(dataset))
    )
    dataset["temperatura_media"] = np.round(temperatura, 1)

    sensibilidad = dataset["categoria"].map(SENSIBILIDAD_TERMICA_CATEGORIA)
    exceso_termico = np.clip(temperatura - GRADOS_REFERENCIA_TERMICA, 0.0, None)
    dataset["_factor_termico"] = 1.0 + sensibilidad * exceso_termico
    return dataset


def _agregar_merma(
    dataset: pd.DataFrame,
    rng: np.random.Generator,
    parametros: ParametrosGeneracion,
) -> pd.DataFrame:
    """Simula la merma semanal, incluidos incidentes de cadena de frío."""
    exceso_termico = np.clip(
        dataset["temperatura_media"].to_numpy() - GRADOS_REFERENCIA_TERMICA, 0.0, None
    )
    merma = (
        rng.normal(
            dataset["categoria"].map(MERMA_BASE_CATEGORIA).to_numpy(),
            dataset["categoria"].map(MERMA_DESVIO_CATEGORIA).to_numpy(),
        )
        + EFECTO_TERMICO_MERMA * exceso_termico
    )

    incidente = rng.random(len(dataset)) < parametros.probabilidad_incidente_merma
    adicional = rng.uniform(
        parametros.rango_incidente_merma[0],
        parametros.rango_incidente_merma[1],
        len(dataset),
    )
    merma = np.where(incidente, merma + adicional, merma)
    dataset["merma_pct"] = np.round(np.clip(merma, MERMA_MINIMA_PCT, MERMA_MAXIMA_PCT), 2)
    return dataset


def _agregar_afluencia(
    dataset: pd.DataFrame,
    rng: np.random.Generator,
    parametros: ParametrosGeneracion,
) -> pd.DataFrame:
    """Calcula la afluencia semanal de clientes de cada sucursal."""
    factores = tabla_estacional().set_index(["categoria", "mes"])["factor"]
    estacional = pd.MultiIndex.from_frame(dataset[["categoria", "mes"]]).map(factores)

    factor_promocion = (
        1.0 + parametros.elasticidad_trafico_promocion * dataset["descuento_pct"] / 100.0
    )
    factor_feriado = np.where(dataset["es_feriado_semana"], FACTOR_AFLUENCIA_FERIADO, 1.0)
    factor_atipico = _factores_atipicos(rng, len(dataset), parametros)
    ruido = np.exp(rng.normal(0.0, parametros.ruido_afluencia, len(dataset)))

    dataset["afluencia_clientes"] = np.round(
        dataset["sucursal"].map(AFLUENCIA_BASE_SUCURSAL).to_numpy()
        * estacional.to_numpy()
        * factor_promocion.to_numpy()
        * factor_feriado
        * dataset["_factor_termico"].to_numpy()
        * factor_atipico
        * ruido
    )
    return dataset


def _agregar_demanda(
    dataset: pd.DataFrame,
    rng: np.random.Generator,
    parametros: ParametrosGeneracion,
) -> pd.DataFrame:
    """Deriva la demanda esperada y la demanda realizada en unidades."""
    indice_semana = (dataset["fecha_semana"] - dataset["fecha_semana"].min()).dt.days // 7
    tendencia = 1.0 + parametros.tendencia_semanal * indice_semana
    factor_promocion = 1.0 + parametros.elasticidad_promocion * dataset["descuento_pct"] / 100.0

    dataset["_demanda_esperada"] = (
        dataset["afluencia_clientes"].to_numpy()
        * dataset["categoria"].map(TASA_CONVERSION_CATEGORIA).to_numpy()
        * factor_promocion.to_numpy()
        * tendencia.to_numpy()
    )
    factor_calidad = 1.0 - PENALIDAD_DEMANDA_MERMA * dataset["merma_pct"].to_numpy() / 100.0
    ruido = np.exp(rng.normal(0.0, parametros.ruido_conversion, len(dataset)))
    dataset["_demanda_unidades"] = dataset["_demanda_esperada"] * factor_calidad * ruido
    return dataset


def _agregar_stock_y_unidades(
    dataset: pd.DataFrame,
    rng: np.random.Generator,
    parametros: ParametrosGeneracion,
) -> pd.DataFrame:
    """Simula el stock planificado y el efecto de quiebre sobre las unidades."""
    factor_stock = rng.uniform(
        parametros.rango_factor_stock[0],
        parametros.rango_factor_stock[1],
        len(dataset),
    )
    error_planificacion = np.exp(rng.normal(0.0, parametros.ruido_planificacion, len(dataset)))
    dataset["stock_inicial"] = np.round(
        dataset["_demanda_esperada"] * factor_stock * error_planificacion
    )

    disponibles = dataset["stock_inicial"] * (1.0 - dataset["merma_pct"] / 100.0)
    unidades = np.floor(np.minimum(dataset["_demanda_unidades"], disponibles))
    dataset["unidades_vendidas"] = np.maximum(unidades, UNIDADES_MINIMAS).astype(np.int64)
    return dataset


def _agregar_precio_y_ventas(
    dataset: pd.DataFrame,
    rng: np.random.Generator,
    parametros: ParametrosGeneracion,
) -> pd.DataFrame:
    """Calcula precio promedio realizado y ventas en bolivianos."""
    precio = (
        dataset["categoria"].map(PRECIO_BASE_CATEGORIA).to_numpy()
        * dataset["sucursal"].map(FACTOR_PRECIO_SUCURSAL).to_numpy()
        * (1.0 - dataset["descuento_pct"].to_numpy() / 100.0)
        * np.exp(rng.normal(0.0, parametros.ruido_precio, len(dataset)))
    )
    dataset["precio_promedio"] = np.round(np.maximum(precio, PRECIO_MINIMO_BS), 2)
    dataset["ventas_bs"] = np.round(dataset["unidades_vendidas"] * dataset["precio_promedio"], 2)
    return dataset


def _agregar_personal(
    dataset: pd.DataFrame,
    rng: np.random.Generator,
    parametros: ParametrosGeneracion,
) -> pd.DataFrame:
    """Asigna personal de venta según el volumen esperado de la categoría."""
    demanda_esperada = pd.Series(dataset["_demanda_esperada"], index=dataset.index)
    mediana_categoria = demanda_esperada.groupby(dataset["categoria"]).transform("median")
    personal = dataset["categoria"].map(PERSONAL_BASE_CATEGORIA).to_numpy() * (
        parametros.personal_piso_volumen
        + parametros.personal_escala_volumen * demanda_esperada / mediana_categoria
    ) + rng.normal(0.0, 0.5, len(dataset))
    dataset["personal_asignado"] = np.clip(np.round(personal), PERSONAL_MINIMO, PERSONAL_MAXIMO)
    return dataset


def _agregar_metas(
    dataset: pd.DataFrame,
    rng: np.random.Generator,
    parametros: ParametrosGeneracion,
) -> pd.DataFrame:
    """Estima la meta semanal a partir de la demanda esperada, no de la real."""
    meta = (
        dataset["afluencia_clientes"].to_numpy()
        * dataset["categoria"].map(TASA_CONVERSION_CATEGORIA).to_numpy()
        * dataset["categoria"].map(PRECIO_BASE_CATEGORIA).to_numpy()
        * dataset["sucursal"].map(FACTOR_META_SUCURSAL).to_numpy()
        * rng.uniform(
            parametros.rango_factor_meta[0],
            parametros.rango_factor_meta[1],
            len(dataset),
        )
    )
    dataset["meta_ventas_bs"] = np.round(np.maximum(meta, META_MINIMA_BS), 2)
    dataset["cumplimiento_meta_pct"] = np.round(
        dataset["ventas_bs"] / dataset["meta_ventas_bs"] * 100.0, 2
    )
    return dataset


def _inyectar_faltantes(
    dataset: pd.DataFrame,
    rng: np.random.Generator,
    parametros: ParametrosGeneracion,
) -> pd.DataFrame:
    """Reemplaza una pequeña proporción de valores por NaN."""
    for columna in COLUMNAS_CON_FALTANTES:
        mascara = rng.random(len(dataset)) < parametros.proporcion_faltantes
        dataset.loc[mascara, columna] = np.nan
    return dataset


def _ordenar_y_seleccionar(dataset: pd.DataFrame) -> pd.DataFrame:
    """Ordena por fecha, sucursal y categoría, y deja solo las columnas finales."""
    orden = dataset.assign(
        sucursal=pd.Categorical(dataset["sucursal"], categories=list(SUCURSALES)),
        categoria=pd.Categorical(dataset["categoria"], categories=list(CATEGORIAS)),
    ).sort_values(["fecha_semana", "sucursal", "categoria"])
    orden["sucursal"] = orden["sucursal"].astype(str)
    orden["categoria"] = orden["categoria"].astype(str)
    return orden.loc[:, list(COLUMNAS_DATASET)].reset_index(drop=True)


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------
def generar_dataset(
    semilla: int = SEMILLA,
    parametros: ParametrosGeneracion = PARAMETROS_GENERACION,
) -> pd.DataFrame:
    """Genera el dataset completo de ventas semanales.

    Args:
        semilla: Semilla del generador aleatorio. Garantiza reproducibilidad.
        parametros: Hiperparámetros del simulador.

    Returns:
        DataFrame con una fila por semana, sucursal y categoría.
    """
    rng = np.random.default_rng(semilla)
    dataset = _producto_calendario(construir_calendario(parametros))

    cantidad = len(dataset)
    en_promocion = rng.random(cantidad) < parametros.probabilidad_promocion
    dataset["en_promocion"] = en_promocion
    dataset["descuento_pct"] = np.round(
        np.where(
            en_promocion,
            rng.uniform(
                parametros.descuento_min_pct,
                parametros.descuento_max_pct,
                cantidad,
            ),
            0.0,
        ),
        1,
    )

    dataset = _agregar_temperatura(dataset, rng, parametros)
    dataset = _agregar_merma(dataset, rng, parametros)
    dataset = _agregar_afluencia(dataset, rng, parametros)
    dataset = _agregar_demanda(dataset, rng, parametros)
    dataset = _agregar_stock_y_unidades(dataset, rng, parametros)
    dataset = _agregar_precio_y_ventas(dataset, rng, parametros)
    dataset = _agregar_personal(dataset, rng, parametros)
    dataset = _agregar_metas(dataset, rng, parametros)
    dataset = _inyectar_faltantes(dataset, rng, parametros)

    columnas_internas = ["_factor_termico", "_demanda_esperada", "_demanda_unidades"]
    return _ordenar_y_seleccionar(dataset.drop(columns=columnas_internas))


def guardar_dataset(dataset: pd.DataFrame, ruta: Path | None = None) -> Path:
    """Guarda el dataset en formato CSV.

    Args:
        dataset: DataFrame a persistir.
        ruta: Destino del archivo. Por defecto, ``data/raw/ventas_semanales.csv``.

    Returns:
        Ruta del archivo escrito.
    """
    destino = ruta if ruta is not None else ARCHIVO_VENTAS_CRUDO
    destino.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(destino, index=False, date_format="%Y-%m-%d", encoding="utf-8")
    return destino


def resumen_estadistico(dataset: pd.DataFrame) -> pd.DataFrame:
    """Devuelve estadísticos descriptivos de las columnas numéricas.

    Args:
        dataset: Dataset de ventas.

    Returns:
        Tabla transpuesta con conteo, media, desviación, mínimo, cuartiles y máximo.
    """
    numericas = dataset.select_dtypes(include="number")
    return numericas.describe().T.round(2)


def _parsear_argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    """Define y procesa los argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(description="Genera el dataset simulado de ventas.")
    parser.add_argument("--semilla", type=int, default=SEMILLA, help="Semilla aleatoria.")
    parser.add_argument(
        "--salida",
        type=str,
        default=str(ARCHIVO_VENTAS_CRUDO),
        help="Ruta del CSV de salida.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Genera, guarda y resume el dataset de ventas."""
    argumentos = _parsear_argumentos(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    dataset = generar_dataset(semilla=argumentos.semilla)
    ruta = guardar_dataset(dataset, ruta=Path(argumentos.salida))

    LOGGER.info("Dataset generado en %s (%d filas)", ruta, len(dataset))
    print(dataset.head(5).to_string(index=False))
    print("\nResumen estadístico:")
    print(resumen_estadistico(dataset).to_string())


if __name__ == "__main__":
    main()
