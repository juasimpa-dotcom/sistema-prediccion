"""Búsquedas informadas: voraz (Greedy) y A* con heurística admisible.

La heurística del dominio vive en
:meth:`~search.espacio_estados.ProblemaPlanComercial.heuristica` y está
justificada allí. Este módulo solo consume ``heuristica(estado)``; también
ofrece :func:`heuristica_cero` para medir cuánto aporta esa información.
"""

from __future__ import annotations

import heapq
import itertools
import math
import time
from collections.abc import Callable, Hashable
from typing import TypeVar

from search.espacio_estados import Problema
from search.resultado import Resultado

EstadoT = TypeVar("EstadoT", bound=Hashable)
AccionT = TypeVar("AccionT", bound=Hashable)
Heuristica = Callable[[Hashable], float]


def heuristica_cero(estado: Hashable) -> float:
    """Heurística trivial ``h = 0``: no informa pero es admisible y consistente.

    Con ella A* se degrada a :func:`~search.no_informada.costo_uniforme`. Se
    usa en las pruebas y en el benchmark para cuantificar la reducción de nodos
    que logra la heurística del dominio.

    Args:
        estado: Estado ignorado.

    Returns:
        Siempre 0.
    """
    del estado
    return 0.0


def _resolver_heuristica(
    problema: Problema[EstadoT, AccionT],
    heuristica: Heuristica | None,
) -> Heuristica:
    """Usa la heurística explícita, la del problema o la trivial, en ese orden."""
    if heuristica is not None:
        return heuristica
    propia = getattr(problema, "heuristica", None)
    return propia if callable(propia) else heuristica_cero


def _resultado(
    algoritmo: str,
    problema: Problema[EstadoT, AccionT],
    inicio: float,
    plan: tuple[Hashable, ...],
    costo: float,
    expandidos: int,
    generados: int,
    encontrado: bool,
) -> Resultado:
    """Construye el resultado común con el tiempo transcurrido."""
    return Resultado(
        plan=plan,
        costo=round(costo, 2),
        nodos_expandidos=expandidos,
        nodos_generados=generados,
        profundidad=len(plan),
        tiempo=time.perf_counter() - inicio,
        encontrado=encontrado,
        algoritmo=algoritmo,
        escenario=getattr(problema, "descripcion", type(problema).__name__),
    )


def busqueda_voraz(
    problema: Problema[EstadoT, AccionT],
    heuristica: Heuristica | None = None,
) -> Resultado:
    """Greedy: expande primero el estado más prometedor según ``h``.

    Ignora el costo acumulado, así que es rápido pero **no garantiza** el plan
    de menor costo. Sirve como contraste con A* en el benchmark.

    Args:
        problema: Problema a resolver.
        heuristica: Función de estimación; por defecto la del problema.

    Returns:
        Resultado con el primer plan encontrado, o ``encontrado=False``.
    """
    inicio = time.perf_counter()
    estimar = _resolver_heuristica(problema, heuristica)
    inicial = problema.estado_inicial()
    contador = itertools.count()
    frontera: list[tuple[float, int, EstadoT, tuple[Hashable, ...], float]] = [
        (estimar(inicial), next(contador), inicial, (), 0.0)
    ]
    visitados: set[EstadoT] = {inicial}
    expandidos = generados = 0

    while frontera:
        _, _, estado, plan, costo = heapq.heappop(frontera)
        expandidos += 1
        if problema.es_meta(estado):
            return _resultado("Greedy", problema, inicio, plan, costo, expandidos, generados, True)
        for accion in problema.acciones(estado):
            generados += 1
            sucesor = problema.resultado(estado, accion)
            if sucesor in visitados:
                continue
            visitados.add(sucesor)
            heapq.heappush(
                frontera,
                (
                    estimar(sucesor),
                    next(contador),
                    sucesor,
                    (*plan, accion),
                    round(costo + problema.costo_paso(estado, accion), 2),
                ),
            )

    return _resultado("Greedy", problema, inicio, (), 0.0, expandidos, generados, False)


def a_estrella(
    problema: Problema[EstadoT, AccionT],
    heuristica: Heuristica | None = None,
    peso: float = 1.0,
) -> Resultado:
    """A*: ordena por ``f = g + peso · h`` y es óptimo si ``peso == 1``.

    Con ``peso > 1`` se obtiene A* ponderado: expande menos nodos a costa de
    perder la garantía de optimalidad. Con ``peso == 0`` equivale a costo
    uniforme. Los empates se resuelven por menor ``h`` y después por orden de
    inserción, para que el resultado sea determinista.

    Args:
        problema: Problema a resolver.
        heuristica: Estimación por defecto ``h``; se usa la del problema si se omite.
        peso: Peso de ``h`` dentro de ``f``; 1 garantiza optimalidad con ``h``
            admisible y consistente.

    Returns:
        Resultado con el plan de costo mínimo, o ``encontrado=False``.

    Raises:
        ValueError: Si ``peso`` es negativo.
    """
    if peso < 0:
        raise ValueError("El peso de la heurística no puede ser negativo")
    inicio = time.perf_counter()
    estimar = _resolver_heuristica(problema, heuristica)
    inicial = problema.estado_inicial()
    contador = itertools.count()
    h_inicial = estimar(inicial)
    frontera: list[tuple[float, float, int, EstadoT, tuple[Hashable, ...], float]] = [
        (h_inicial, h_inicial, next(contador), inicial, (), 0.0)
    ]
    mejor: dict[EstadoT, float] = {inicial: 0.0}
    expandidos = generados = 0

    while frontera:
        _, _, _, estado, plan, costo = heapq.heappop(frontera)
        if costo > mejor.get(estado, math.inf) + 1e-9:
            continue
        expandidos += 1
        if problema.es_meta(estado):
            return _resultado("A*", problema, inicio, plan, costo, expandidos, generados, True)
        for accion in problema.acciones(estado):
            generados += 1
            sucesor = problema.resultado(estado, accion)
            nuevo_costo = round(costo + problema.costo_paso(estado, accion), 2)
            if nuevo_costo >= mejor.get(sucesor, math.inf):
                continue
            mejor[sucesor] = nuevo_costo
            h = estimar(sucesor)
            heapq.heappush(
                frontera,
                (
                    nuevo_costo + peso * h,
                    h,
                    next(contador),
                    sucesor,
                    (*plan, accion),
                    nuevo_costo,
                ),
            )

    return _resultado("A*", problema, inicio, (), 0.0, expandidos, generados, False)
