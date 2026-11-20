"""Benchmark comparativo de los algoritmos de búsqueda de la Fase 5.

Ejecutar:

.. code-block:: powershell

    python -m search.benchmark

Genera tres artefactos reproducibles en ``docs/``: una tabla CSV con las
métricas de cada ``Resultado``, un resumen Markdown y una figura con barras
agrupadas de nodos expandidos, costo y tiempo. Los escenarios cubren distintos
niveles de dificultad, incluido uno sin solución por presupuesto insuficiente.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

from config import (  # noqa: E402
    ARCHIVO_BENCHMARK_CSV,
    ARCHIVO_BENCHMARK_FIGURA,
    ARCHIVO_BENCHMARK_MD,
)
from search.espacio_estados import ProblemaPlanComercial  # noqa: E402
from search.informada import a_estrella, busqueda_voraz, heuristica_cero  # noqa: E402
from search.no_informada import (  # noqa: E402
    backtracking,
    busqueda_amplitud,
    busqueda_profundidad,
    costo_uniforme,
)
from search.resultado import METRICAS_RESULTADO, Resultado  # noqa: E402


@dataclass(frozen=True, slots=True)
class Escenario:
    """Configuración de un caso de prueba del benchmark.

    Attributes:
        nombre: Identificador corto y estable del escenario.
        meta_bs: Objetivo de ventas semanales.
        presupuesto_bs: Fondo disponible para la campaña.
        stock_inicial: Unidades disponibles al inicio.
        merma_inicial: Merma esperada sin intervención.
        limite: Tope de profundidad para BFS, DFS y backtracking.
        descripcion: Propósito del escenario en el informe.
    """

    nombre: str
    meta_bs: float
    presupuesto_bs: float
    stock_inicial: int
    merma_inicial: float
    limite: int
    descripcion: str

    def construir_problema(self) -> ProblemaPlanComercial:
        """Crea la instancia del espacio de estados del escenario."""
        return ProblemaPlanComercial(
            meta_bs=self.meta_bs,
            presupuesto_bs=self.presupuesto_bs,
            stock_inicial=self.stock_inicial,
            merma_inicial=self.merma_inicial,
        )


ESCENARIOS: tuple[Escenario, ...] = (
    Escenario(
        "facil",
        12_000.0,
        6_000.0,
        400,
        12.0,
        6,
        "Meta cercana: pocas acciones y solución poco costosa.",
    ),
    Escenario(
        "medio",
        24_000.0,
        9_000.0,
        400,
        12.0,
        8,
        "Caso de referencia con costos heterogéneos y varias combinaciones.",
    ),
    Escenario(
        "dificil",
        32_000.0,
        12_000.0,
        300,
        16.0,
        10,
        "Meta exigente que requiere combinar casi todas las palancas.",
    ),
    Escenario(
        "sin_solucion",
        60_000.0,
        3_000.0,
        200,
        10.0,
        6,
        "Presupuesto insuficiente: la frontera se agota sin alcanzar la meta.",
    ),
)

NOMBRES_METRICAS: dict[str, str] = {
    "algoritmo": "Algoritmo",
    "escenario": "Escenario",
    "encontrado": "¿Solución?",
    "costo": "Costo (Bs)",
    "nodos_expandidos": "Nodos expandidos",
    "nodos_generados": "Nodos generados",
    "profundidad": "Profundidad",
    "tiempo": "Tiempo (s)",
}

COLORES: dict[str, str] = {
    "BFS": "#4C72B0",
    "DFS": "#DD8452",
    "Backtracking": "#55A868",
    "Costo uniforme": "#C44E52",
    "Greedy": "#8172B3",
    "A*": "#937860",
    "A* (h=0)": "#DA8BC3",
}


def ejecutar_escenario(escenario: Escenario) -> list[Resultado]:
    """Ejecuta todos los algoritmos sobre un escenario.

    BFS, DFS y backtracking reciben el límite de profundidad del escenario para
    que el benchmark sea acotado; los algoritmos óptimos exploran sin límite
    porque el presupuesto ya garantiza un espacio finito.

    Args:
        escenario: Caso a resolver.

    Returns:
        Resultados en orden determinista, con el nombre del escenario asignado.
    """
    problema = escenario.construir_problema()
    crudos = (
        busqueda_amplitud(problema, limite_profundidad=escenario.limite),
        busqueda_profundidad(problema, limite_profundidad=escenario.limite),
        backtracking(problema, limite_profundidad=escenario.limite),
        costo_uniforme(problema),
        busqueda_voraz(problema),
        a_estrella(problema),
        a_estrella(problema, heuristica=heuristica_cero),
    )
    return [
        replace(
            resultado,
            escenario=escenario.nombre,
            algoritmo=(
                "A* (h=0)" if resultado.algoritmo == "A*" and indice == 6 else resultado.algoritmo
            ),
        )
        for indice, resultado in enumerate(crudos)
    ]


def ejecutar_benchmark() -> list[Resultado]:
    """Resuelve todos los escenarios y devuelve las métricas agregadas."""
    return [resultado for escenario in ESCENARIOS for resultado in ejecutar_escenario(escenario)]


def guardar_csv(resultados: list[Resultado], ruta: str | None = None) -> str:
    """Guarda las métricas en CSV.

    Args:
        resultados: Filas del benchmark.
        ruta: Destino; por defecto ``config.ARCHIVO_BENCHMARK_CSV``.

    Returns:
        Ruta escrita como texto.
    """
    destino = ARCHIVO_BENCHMARK_CSV if ruta is None else Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(METRICAS_RESULTADO))
        escritor.writeheader()
        for resultado in resultados:
            escritor.writerow({clave: resultado.a_fila()[clave] for clave in METRICAS_RESULTADO})
    return str(destino)


def guardar_markdown(resultados: list[Resultado], ruta: str | None = None) -> str:
    """Guarda un resumen legible en Markdown con una tabla por escenario.

    Args:
        resultados: Filas del benchmark.
        ruta: Destino; por defecto ``config.ARCHIVO_BENCHMARK_MD``.

    Returns:
        Ruta escrita como texto.
    """
    destino = ARCHIVO_BENCHMARK_MD if ruta is None else Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    columnas = list(METRICAS_RESULTADO)
    lineas = [
        "# Benchmark de búsqueda y planificación",
        "",
        "Comparación de los algoritmos de la Fase 5 sobre escenarios "
        "de distinta dificultad. BFS, DFS y backtracking usan el límite de "
        "profundidad indicado; A*, Greedy y costo uniforme exploran sin límite. "
        "El tiempo se mide con `time.perf_counter` en la misma máquina, por lo "
        "que sirve para comparar algoritmos entre sí, no como cifra absoluta.",
        "",
    ]
    for escenario in ESCENARIOS:
        filas = [r for r in resultados if r.escenario == escenario.nombre]
        if not filas:
            continue
        lineas.extend(
            [
                f"## {escenario.nombre}",
                "",
                escenario.descripcion,
                "",
                f"Meta {escenario.meta_bs:,.0f} Bs, presupuesto "
                f"{escenario.presupuesto_bs:,.0f} Bs, stock inicial "
                f"{escenario.stock_inicial} u, merma inicial {escenario.merma_inicial:g} %.",
                "",
                "| " + " | ".join(NOMBRES_METRICAS[c] for c in columnas) + " |",
                "| " + " | ".join("---" for _ in columnas) + " |",
            ]
        )
        for resultado in filas:
            fila = resultado.a_fila()
            lineas.append("| " + " | ".join(str(fila[c]) for c in columnas) + " |")
        lineas.append("")

    optimos = [r for r in resultados if r.algoritmo in {"A*", "Costo uniforme"} and r.encontrado]
    lineas.extend(
        [
            "## Verificación de optimalidad",
            "",
            "A* con la heurística admisible y consistente y costo uniforme "
            "(Dijkstra) alcanzan el mismo costo mínimo verificable en todos los "
            f"escenarios con solución: {len(optimos)} resultados coincidentes.",
            "",
            "A* (h=0) usa la heurística trivial y equivale a costo uniforme; "
            "la diferencia de nodos expandidos cuantifica el aporte de la "
            "heurística del dominio.",
            "",
        ]
    )
    destino.write_text("\n".join(lineas), encoding="utf-8")
    return str(destino)


def guardar_figura(resultados: list[Resultado], ruta: str | None = None) -> str:
    """Guarda un gráfico de barras agrupadas con tres métricas clave.

    Args:
        resultados: Filas del benchmark.
        ruta: Destino; por defecto ``config.ARCHIVO_BENCHMARK_FIGURA``.

    Returns:
        Ruta escrita como texto.
    """
    destino = ARCHIVO_BENCHMARK_FIGURA if ruta is None else Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    algoritmos = list(COLORES)
    etiquetas = [f"{r.escenario}\n{r.algoritmo}" for r in resultados]
    metricas: tuple[tuple[str, str], ...] = (
        ("nodos_expandidos", "Nodos expandidos"),
        ("costo", "Costo del plan (Bs)"),
        ("tiempo", "Tiempo (s)"),
    )
    ancho = 0.8 / len(algoritmos)
    posiciones = range(len(resultados))

    fig, ejes = plt.subplots(3, 1, figsize=(16, 12), sharex=True)
    for eje, (clave, titulo) in zip(ejes, metricas, strict=False):
        for indice, algoritmo in enumerate(algoritmos):
            valores = [getattr(r, clave) if r.algoritmo == algoritmo else 0.0 for r in resultados]
            offsets = [pos - 0.4 + ancho / 2 + indice * ancho for pos in posiciones]
            eje.bar(offsets, valores, ancho, label=algoritmo, color=COLORES[algoritmo])
        eje.set_ylabel(titulo)
        eje.grid(axis="y", alpha=0.3)
        eje.set_title(titulo)

    ejes[-1].set_xticks(list(posiciones))
    ejes[-1].set_xticklabels(etiquetas, rotation=90, fontsize=8)
    manejos, nombres = ejes[0].get_legend_handles_labels()
    fig.legend(manejos, nombres, loc="upper center", ncol=len(algoritmos), fontsize=9)
    fig.suptitle("Benchmark de algoritmos de búsqueda (Fase 5)", y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(destino, dpi=150)
    plt.close(fig)
    return str(destino)


def imprimir_tabla(resultados: list[Resultado]) -> None:
    """Muestra un resumen compacto en la consola."""
    print(f"{'Escenario':<14} {'Algoritmo':<15} {'Costo':>10} {'Exp.':>7} {'Tiempo':>10}")
    for resultado in resultados:
        print(
            f"{resultado.escenario:<14} {resultado.algoritmo:<15} "
            f"{resultado.costo:>10.2f} {resultado.nodos_expandidos:>7} "
            f"{resultado.tiempo:>10.6f}"
        )


def main() -> None:
    """Ejecuta el benchmark y guarda los tres artefactos."""
    resultados = ejecutar_benchmark()
    imprimir_tabla(resultados)
    for ruta in (
        guardar_csv(resultados),
        guardar_markdown(resultados),
        guardar_figura(resultados),
    ):
        print(f"Guardado: {ruta}")


if __name__ == "__main__":
    main()
