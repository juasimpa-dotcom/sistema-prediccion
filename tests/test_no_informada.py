"""Pruebas de BFS, DFS, backtracking y costo uniforme."""

from __future__ import annotations

from collections.abc import Hashable

import pytest

from search.espacio_estados import Problema
from search.no_informada import (
    backtracking,
    busqueda_amplitud,
    busqueda_profundidad,
    costo_uniforme,
)


class ProblemaNumerico(Problema[int, int]):
    """Problema juguete: avanzar de 0 al objetivo sumando 1 o 2 unidades."""

    descripcion = "juguete"

    def __init__(
        self,
        objetivo: int,
        tope: int,
        costos: dict[int, float] | None = None,
    ) -> None:
        self.objetivo = objetivo
        self.tope = tope
        self.costos = costos or {1: 1.0, 2: 1.0}

    def estado_inicial(self) -> int:
        return 0

    def es_meta(self, estado: int) -> bool:
        return estado >= self.objetivo

    def acciones(self, estado: int) -> tuple[int, ...]:
        return tuple(paso for paso in (1, 2) if estado + paso <= self.tope)

    def resultado(self, estado: int, accion: int) -> int:
        return estado + accion

    def costo_paso(self, estado: int, accion: int) -> float:
        del estado
        return self.costos[accion]


def replay(problema: Problema[int, int], plan: tuple[Hashable, ...]) -> int:
    """Aplica un plan y devuelve el estado final."""
    estado = problema.estado_inicial()
    for accion in plan:
        estado = problema.resultado(estado, accion)  # type: ignore[arg-type]
    return estado


def test_bfs_encuentra_el_plan_mas_corto() -> None:
    """BFS garantiza la menor cantidad de acciones en costos uniformes."""
    problema = ProblemaNumerico(objetivo=6, tope=6)
    resultado = busqueda_amplitud(problema)
    assert resultado.encontrado
    assert resultado.profundidad == 3
    assert replay(problema, resultado.plan) == 6
    assert resultado.costo == 3.0
    assert resultado.algoritmo == "BFS"
    assert resultado.escenario == "juguete"


def test_bfs_completo_en_problema_sin_solucion() -> None:
    """Si la meta es inalcanzable, BFS agota la frontera y lo informa."""
    problema = ProblemaNumerico(objetivo=10, tope=4)
    resultado = busqueda_amplitud(problema)
    assert not resultado.encontrado
    assert resultado.plan == ()
    assert resultado.costo == 0.0
    assert resultado.nodos_expandidos > 0


@pytest.mark.parametrize("algoritmo", [busqueda_amplitud, busqueda_profundidad, backtracking])
def test_limite_de_profundidad_evita_la_meta(algoritmo) -> None:
    """Con un límite insuficiente ningún algoritmo alcanza la meta."""
    problema = ProblemaNumerico(objetivo=6, tope=6)
    resultado = algoritmo(problema, limite_profundidad=2)
    assert not resultado.encontrado
    assert resultado.plan == ()
    assert resultado.profundidad <= 2


@pytest.mark.parametrize("algoritmo", [busqueda_amplitud, busqueda_profundidad, backtracking])
def test_limite_suficiente_si_encuentra_solucion(algoritmo) -> None:
    """Con profundidad suficiente los tres algoritmos encuentran la meta."""
    problema = ProblemaNumerico(objetivo=6, tope=6)
    resultado = algoritmo(problema, limite_profundidad=3)
    assert resultado.encontrado
    assert replay(problema, resultado.plan) == 6


def test_dfs_y_backtracking_devuelven_planes_validos() -> None:
    """El orden de exploración no afecta la validez del plan."""
    problema = ProblemaNumerico(objetivo=7, tope=7)
    for algoritmo, nombre in ((busqueda_profundidad, "DFS"), (backtracking, "Backtracking")):
        resultado = algoritmo(problema, limite_profundidad=7)
        assert resultado.encontrado
        assert resultado.algoritmo == nombre
        assert replay(problema, resultado.plan) >= 7


def test_costo_uniforme_ignora_el_numero_de_acciones() -> None:
    """Dijkstra prefiere menos pasos caros si el total es menor."""
    problema = ProblemaNumerico(objetivo=6, tope=6, costos={1: 5.0, 2: 6.0})
    resultado = costo_uniforme(problema)
    assert resultado.encontrado
    assert resultado.costo == 18.0
    assert resultado.profundidad == 3


def test_costo_uniforme_sin_solucion() -> None:
    """Costo uniforme también detecta la ausencia de solución."""
    problema = ProblemaNumerico(objetivo=10, tope=4)
    resultado = costo_uniforme(problema)
    assert not resultado.encontrado
    assert resultado.costo == 0.0


@pytest.mark.parametrize("algoritmo", [busqueda_profundidad, backtracking])
def test_limite_negativo_se_rechaza(algoritmo) -> None:
    """Un límite negativo no tiene sentido y se valida."""
    with pytest.raises(ValueError):
        algoritmo(ProblemaNumerico(objetivo=1, tope=1), limite_profundidad=-1)


def test_controla_estados_repetidos() -> None:
    """Los nodos generados superan a los expandidos pero el grafo es finito."""
    problema = ProblemaNumerico(objetivo=6, tope=6)
    resultado = busqueda_amplitud(problema)
    assert resultado.nodos_expandidos <= problema.tope + 1
    assert resultado.nodos_generados >= resultado.nodos_expandidos
