"""Pruebas del script de benchmark y sus artefactos."""

from __future__ import annotations

from pathlib import Path

import pytest

from search.benchmark import (
    COLORES,
    ESCENARIOS,
    ejecutar_benchmark,
    guardar_csv,
    guardar_figura,
    guardar_markdown,
)
from search.resultado import METRICAS_RESULTADO, Resultado


@pytest.fixture(scope="module")
def resultados() -> list[Resultado]:
    """Ejecuta el benchmark una sola vez para todas las pruebas del módulo."""
    return ejecutar_benchmark()


def test_benchmark_cubre_todos_los_escenarios_y_algoritmos(resultados: list[Resultado]) -> None:
    """Cada escenario se resuelve con los siete algoritmos configurados."""
    assert len(ESCENARIOS) == 4
    assert len(resultados) == len(ESCENARIOS) * len(COLORES)
    for escenario in ESCENARIOS:
        filas = [r for r in resultados if r.escenario == escenario.nombre]
        assert {r.algoritmo for r in filas} == set(COLORES)
    assert all(isinstance(r, Resultado) for r in resultados)


def test_optimos_coinciden_en_escenarios_con_solucion(resultados: list[Resultado]) -> None:
    """A* y costo uniforme alcanzan el mismo costo verificable."""
    for escenario in ESCENARIOS:
        astar = next(
            r for r in resultados if r.escenario == escenario.nombre and r.algoritmo == "A*"
        )
        uniforme = next(
            r
            for r in resultados
            if r.escenario == escenario.nombre and r.algoritmo == "Costo uniforme"
        )
        assert astar.encontrado == uniforme.encontrado
        if astar.encontrado:
            assert astar.costo == pytest.approx(uniforme.costo)


def test_escenario_sin_solucion_no_genera_plan(resultados: list[Resultado]) -> None:
    """El caso inviable termina sin plan en todos los algoritmos."""
    filas = [r for r in resultados if r.escenario == "sin_solucion"]
    assert filas
    assert all(not r.encontrado and r.plan == () for r in filas)


def test_artefactos_se_guardan_en_ruta_dada(resultados: list[Resultado], tmp_path: Path) -> None:
    """CSV, Markdown y PNG se escriben sin depender de ``docs/``."""
    csv_path = guardar_csv(resultados, tmp_path / "benchmark.csv")
    md_path = guardar_markdown(resultados, tmp_path / "benchmark.md")
    png_path = guardar_figura(resultados, tmp_path / "benchmark.png")

    csv_texto = Path(csv_path).read_text(encoding="utf-8")
    assert csv_texto.splitlines()[0] == ",".join(METRICAS_RESULTADO)
    assert len(csv_texto.splitlines()) == len(resultados) + 1

    md_texto = Path(md_path).read_text(encoding="utf-8")
    assert "# Benchmark de búsqueda y planificación" in md_texto
    assert all(f"## {escenario.nombre}" in md_texto for escenario in ESCENARIOS)

    png = Path(png_path).read_bytes()
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
