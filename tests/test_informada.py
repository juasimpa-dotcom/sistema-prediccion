"""Pruebas de Greedy, A* y comparación de heurísticas."""

from __future__ import annotations

import pytest

from search.espacio_estados import ProblemaPlanComercial
from search.informada import a_estrella, busqueda_voraz, heuristica_cero
from search.no_informada import busqueda_amplitud, costo_uniforme


def hacer_problema(meta: float, presupuesto: float, stock: int = 400, merma: float = 12.0):
    """Construye un escenario comercial pequeño."""
    return ProblemaPlanComercial(
        meta_bs=meta,
        presupuesto_bs=presupuesto,
        stock_inicial=stock,
        merma_inicial=merma,
    )


def verificar_plan(problema: ProblemaPlanComercial, resultado) -> None:
    """Comprueba que el plan alcance la meta y que su costo sea coherente."""
    estado = problema.estado_inicial()
    acumulado = 0.0
    for accion in resultado.plan:
        acumulado += problema.costo_paso(estado, accion)
        estado = problema.resultado(estado, accion)
    assert problema.es_meta(estado)
    assert acumulado == pytest.approx(resultado.costo)
    assert resultado.profundidad == len(resultado.plan)


@pytest.mark.parametrize(
    ("meta", "presupuesto", "stock", "merma", "costo_esperado"),
    [
        (12_000.0, 6_000.0, 400, 12.0, 1_400.0),
        (24_000.0, 9_000.0, 400, 12.0, 5_900.0),
        (32_000.0, 12_000.0, 300, 16.0, 10_920.0),
    ],
)
def test_a_estrella_casos_conocidos(
    meta: float, presupuesto: float, stock: int, merma: float, costo_esperado: float
) -> None:
    """A* reproduce costos mínimos verificados con costo uniforme."""
    problema = hacer_problema(meta, presupuesto, stock, merma)
    resultado = a_estrella(problema)
    assert resultado.encontrado
    assert resultado.costo == pytest.approx(costo_esperado)
    assert resultado.algoritmo == "A*"
    verificar_plan(problema, resultado)


@pytest.mark.parametrize(
    ("meta", "presupuesto", "stock", "merma"),
    [
        (12_000.0, 6_000.0, 400, 12.0),
        (24_000.0, 9_000.0, 400, 12.0),
        (32_000.0, 12_000.0, 300, 16.0),
    ],
)
def test_a_estrella_coesiste_con_costo_uniforme(
    meta: float, presupuesto: float, stock: int, merma: float
) -> None:
    """La heurística admisible no altera la optimalidad de A*."""
    problema = hacer_problema(meta, presupuesto, stock, merma)
    optimo = costo_uniforme(problema)
    resultado = a_estrella(problema)
    assert optimo.encontrado and resultado.encontrado
    assert resultado.costo == pytest.approx(optimo.costo)


def test_a_estrella_es_optimo_en_caso_facil_verificado_por_bfs() -> None:
    """En el caso fácil, BFS y A* coinciden porque hay una sola acción óptima."""
    problema = hacer_problema(12_000.0, 6_000.0)
    bfs = busqueda_amplitud(problema)
    astar = a_estrella(problema)
    assert bfs.encontrado and astar.encontrado
    assert bfs.costo == astar.costo == 1_400.0
    assert astar.profundidad == 1
    verificar_plan(problema, astar)


def test_heuristica_cero_es_trivial_y_optima() -> None:
    """``h = 0`` devuelve 0 y degrada A* a costo uniforme."""
    assert heuristica_cero(object()) == 0.0
    problema = hacer_problema(24_000.0, 9_000.0)
    con_cero = a_estrella(problema, heuristica=heuristica_cero)
    referencia = costo_uniforme(problema)
    assert con_cero.costo == pytest.approx(referencia.costo)
    assert con_cero.nodos_expandidos == referencia.nodos_expandidos


def test_heuristica_del_dominio_reduce_nodos_expandidos() -> None:
    """La heurística informada expande menos nodos que la trivial."""
    problema = hacer_problema(24_000.0, 9_000.0)
    informada = a_estrella(problema)
    trivial = a_estrella(problema, heuristica=heuristica_cero)
    assert informada.costo == trivial.costo
    assert informada.nodos_expandidos < trivial.nodos_expandidos


def test_greedy_no_garantiza_optimo_pero_encuentra_plan() -> None:
    """Greedy es más rápido en nodos pero puede pagar más que A*."""
    problema = hacer_problema(24_000.0, 9_000.0)
    voraz = busqueda_voraz(problema)
    optimo = a_estrella(problema)
    assert voraz.encontrado
    verificar_plan(problema, voraz)
    assert voraz.costo >= optimo.costo
    assert voraz.nodos_expandidos < optimo.nodos_expandidos


def test_a_estrella_sin_solucion() -> None:
    """Sin presupuesto suficiente A* agota la frontera y lo reporta."""
    problema = hacer_problema(60_000.0, 3_000.0, stock=200, merma=10.0)
    resultado = a_estrella(problema)
    assert not resultado.encontrado
    assert resultado.plan == ()
    assert resultado.costo == 0.0


def test_peso_invalido_se_rechaza() -> None:
    """El peso de A* ponderado no puede ser negativo."""
    problema = hacer_problema(12_000.0, 6_000.0)
    with pytest.raises(ValueError):
        a_estrella(problema, peso=-0.1)
