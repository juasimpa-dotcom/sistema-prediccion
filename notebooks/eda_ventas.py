"""Análisis exploratorio del dataset de ventas semanales.

Genera las figuras de tendencia, estacionalidad, efecto de promociones,
distribución del cumplimiento y correlaciones en ``notebooks/figuras``.

Uso:
    python -m notebooks.eda_ventas
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from config import (
    ARCHIVO_VENTAS_CRUDO,
    CATEGORIAS,
    COLUMNAS_DATASET,
    DIR_FIGURAS,
    SUCURSALES,
)

LOGGER = logging.getLogger(__name__)

MESES = {
    1: "Ene",
    2: "Feb",
    3: "Mar",
    4: "Abr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dic",
}

COLOR_PRINCIPAL = "#1f4e79"
COLOR_ACENTO = "#d97706"
COLOR_PROMOCION = "#0f766e"


def cargar_dataset(ruta: Path = ARCHIVO_VENTAS_CRUDO) -> pd.DataFrame:
    """Lee el CSV de ventas y valida que tenga el esquema esperado.

    Args:
        ruta: Ubicación del dataset crudo.

    Returns:
        Dataset con la fecha ya interpretada.

    Raises:
        FileNotFoundError: Si el CSV no existe todavía.
        ValueError: Si faltan columnas obligatorias.
    """
    if not ruta.exists():
        raise FileNotFoundError(f"No se encontró {ruta}. Ejecuta 'python -m data.generar_dataset'.")

    dataset = pd.read_csv(ruta, parse_dates=["fecha_semana"])
    faltantes = set(COLUMNAS_DATASET) - set(dataset.columns)
    if faltantes:
        raise ValueError(f"Faltan columnas en el dataset: {sorted(faltantes)}")
    return dataset


def _guardar(figura: plt.Figure, nombre: str) -> Path:
    """Guarda una figura en la carpeta configurada y libera la memoria."""
    DIR_FIGURAS.mkdir(parents=True, exist_ok=True)
    destino = DIR_FIGURAS / nombre
    figura.tight_layout()
    figura.savefig(destino, dpi=130, bbox_inches="tight")
    plt.close(figura)
    LOGGER.info("Figura guardada: %s", destino)
    return destino


def figura_tendencia(dataset: pd.DataFrame) -> Path:
    """Grafica la evolución semanal de ventas totales y por categoría."""
    total = dataset.groupby("fecha_semana")["ventas_bs"].sum()
    por_categoria = dataset.pivot_table(
        index="fecha_semana", columns="categoria", values="ventas_bs", aggfunc="sum"
    )

    figura, (arriba, abajo) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    arriba.plot(total.index, total / 1_000, color=COLOR_PRINCIPAL, label="Ventas semanales")
    arriba.plot(
        total.index,
        total.rolling(4).mean() / 1_000,
        color=COLOR_ACENTO,
        linewidth=2,
        label="Media móvil (4 semanas)",
    )
    arriba.set_title("Tendencia de ventas semanales de la cadena")
    arriba.set_ylabel("Miles de Bs")
    arriba.legend(loc="upper left")

    for categoria in CATEGORIAS:
        if categoria in por_categoria:
            abajo.plot(
                por_categoria.index,
                por_categoria[categoria] / 1_000,
                label=categoria.capitalize(),
                linewidth=1.4,
            )
    abajo.set_title("Ventas semanales por categoría")
    abajo.set_ylabel("Miles de Bs")
    abajo.set_xlabel("Semana")
    abajo.legend(ncol=len(CATEGORIAS), loc="upper left")

    return _guardar(figura, "01_tendencia.png")


def figura_estacionalidad(dataset: pd.DataFrame) -> Path:
    """Muestra el patrón estacional por mes y categoría."""
    copia = dataset.copy()
    copia["mes"] = copia["fecha_semana"].dt.month
    copia["mes_nombre"] = copia["mes"].map(MESES)

    promedio = copia.groupby(["mes_nombre", "categoria"])["unidades_vendidas"].mean()
    tabla = promedio.unstack("categoria").reindex([MESES[mes] for mes in range(1, 13)])

    figura, (izquierda, derecha) = plt.subplots(1, 2, figsize=(14, 5))
    sns.heatmap(
        tabla,
        annot=True,
        fmt=".0f",
        cmap="YlGnBu",
        ax=izquierda,
        cbar_kws={"label": "Unidades promedio"},
    )
    izquierda.set_title("Unidades promedio por mes y categoría")
    izquierda.set_xlabel("Categoría")
    izquierda.set_ylabel("Mes")

    por_mes = copia.groupby("mes_nombre")["unidades_vendidas"].sum()
    por_mes = por_mes.reindex([MESES[mes] for mes in range(1, 13)])
    derecha.bar(por_mes.index, por_mes.values / 1_000, color=COLOR_PRINCIPAL)
    derecha.set_title("Unidades totales por mes")
    derecha.set_ylabel("Miles de unidades")
    derecha.set_xlabel("Mes")

    return _guardar(figura, "02_estacionalidad.png")


def figura_promociones(dataset: pd.DataFrame) -> Path:
    """Compara unidades vendidas con y sin promoción por categoría."""
    copia = dataset.assign(
        promocion=dataset["en_promocion"].map({True: "Con promoción", False: "Sin promoción"})
    )
    figura, (izquierda, derecha) = plt.subplots(1, 2, figsize=(14, 5))

    sns.boxplot(
        data=copia,
        x="categoria",
        y="unidades_vendidas",
        hue="promocion",
        hue_order=["Sin promoción", "Con promoción"],
        palette={"Sin promoción": "#94a3b8", "Con promoción": COLOR_PROMOCION},
        ax=izquierda,
    )
    izquierda.set_title("Unidades vendidas según promoción")
    izquierda.set_xlabel("Categoría")
    izquierda.set_ylabel("Unidades por semana")

    promedios = copia.groupby(["categoria", "promocion"])["unidades_vendidas"].mean().unstack()
    incremento = (promedios["Con promoción"] / promedios["Sin promoción"] - 1) * 100
    incremento = incremento.reindex(list(CATEGORIAS))

    derecha.bar(incremento.index, incremento.values, color=COLOR_PROMOCION)
    for posicion, valor in enumerate(incremento.values):
        derecha.text(posicion, valor + 1, f"+{valor:.1f}%", ha="center")
    derecha.set_title("Incremento medio de unidades en promoción")
    derecha.set_ylabel("Incremento (%)")
    derecha.set_xlabel("Categoría")

    return _guardar(figura, "03_promociones.png")


def figura_cumplimiento(dataset: pd.DataFrame) -> Path:
    """Analiza la distribución del cumplimiento de metas."""
    figura, (izquierda, derecha) = plt.subplots(1, 2, figsize=(14, 5))

    sns.histplot(
        dataset["cumplimiento_meta_pct"],
        bins=30,
        kde=True,
        color=COLOR_PRINCIPAL,
        ax=izquierda,
    )
    izquierda.axvline(100, color=COLOR_ACENTO, linestyle="--", label="Meta (100 %)")
    izquierda.set_title("Distribución del cumplimiento de meta")
    izquierda.set_xlabel("Cumplimiento (%)")
    izquierda.set_ylabel("Frecuencia")
    izquierda.legend()

    sns.boxplot(
        data=dataset,
        x="sucursal",
        y="cumplimiento_meta_pct",
        order=list(SUCURSALES),
        color="#a5b4fc",
        ax=derecha,
    )
    derecha.axhline(100, color=COLOR_ACENTO, linestyle="--")
    derecha.set_title("Cumplimiento por sucursal")
    derecha.set_xlabel("Sucursal")
    derecha.set_ylabel("Cumplimiento (%)")
    derecha.tick_params(axis="x", rotation=20)

    return _guardar(figura, "04_cumplimiento.png")


def figura_correlaciones(dataset: pd.DataFrame) -> Path:
    """Grafica la matriz de correlación de las variables numéricas."""
    numericas = dataset.select_dtypes("number")
    correlacion = numericas.corr(numeric_only=True)

    figura, eje = plt.subplots(figsize=(11, 8))
    sns.heatmap(
        correlacion,
        annot=True,
        fmt=".2f",
        cmap="coolwarm",
        center=0,
        vmin=-1,
        vmax=1,
        ax=eje,
        cbar_kws={"label": "Correlación de Pearson"},
    )
    eje.set_title("Correlación entre variables numéricas")
    return _guardar(figura, "05_correlaciones.png")


def imprimir_resumen(dataset: pd.DataFrame) -> None:
    """Imprime un resumen textual del dataset."""
    print("=" * 78)
    print("RESUMEN DEL DATASET DE VENTAS")
    print("=" * 78)
    print(f"Filas: {len(dataset):,} | Columnas: {dataset.shape[1]}")
    print(
        f"Periodo: {dataset['fecha_semana'].min():%Y-%m-%d} "
        f"a {dataset['fecha_semana'].max():%Y-%m-%d}"
    )
    print(f"Semanas: {dataset['fecha_semana'].nunique()}")
    print(
        f"Sucursales: {dataset['sucursal'].nunique()} | "
        f"Categorías: {dataset['categoria'].nunique()}"
    )

    print("\nValores faltantes por columna:")
    faltantes = dataset.isna().sum()
    print(faltantes[faltantes > 0].to_string() or "Sin valores faltantes")

    print("\nEstadísticos de variables clave:")
    claves = [
        "ventas_bs",
        "unidades_vendidas",
        "precio_promedio",
        "merma_pct",
        "cumplimiento_meta_pct",
    ]
    print(dataset[claves].describe().T.round(2).to_string())

    print("\nCumplimiento medio por sucursal (%):")
    print(
        dataset.groupby("sucursal")["cumplimiento_meta_pct"]
        .mean()
        .round(2)
        .sort_values(ascending=False)
        .to_string()
    )

    print("\nCumplimiento medio por categoría (%):")
    print(dataset.groupby("categoria")["cumplimiento_meta_pct"].mean().round(2).to_string())


def main() -> None:
    """Ejecuta el análisis exploratorio completo."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    plt.switch_backend("Agg")
    sns.set_theme(style="whitegrid", palette="deep")

    dataset = cargar_dataset()
    imprimir_resumen(dataset)

    figura_tendencia(dataset)
    figura_estacionalidad(dataset)
    figura_promociones(dataset)
    figura_cumplimiento(dataset)
    figura_correlaciones(dataset)

    LOGGER.info("Análisis exploratorio finalizado. Figuras en %s", DIR_FIGURAS)


if __name__ == "__main__":
    main()
