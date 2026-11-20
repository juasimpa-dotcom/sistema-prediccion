"""Búsquedas no informadas: amplitud, profundidad, backtracking y costo uniforme.

Todas comparten la interfaz :class:`~search.espacio_estados.Problema` y devuelven
el mismo :class:`~search.resultado.Resultado`. El control de estados repetidos
evita reexpandir un mismo estado y garantiza la terminación en espacios finitos.
"""

from __future__ import annotations

import heapq
import itertools
import math
import time
from collections import deque
from collections.abc import Hashable
from typing import TypeVar

from search.espacio_estados import Problema
from search.resultado import Resultado

EstadoT = TypeVar("EstadoT", bound=Hashable)
AccionT = TypeVar("AccionT", bound=Hashable)


def _resultado(
    algoritmo: str,
    problema: Problema[EstadoT, AccionT],
    inicio: float,
    plan: tuple[Hashable, ...],
    costo: float,
    expandidos: int,
    generados: int,
    profundidad: int,
    encontrado: bool,
) -> Resultado:
    """Construye el resultado común con el tiempo transcurrido."""
    return Resultado(
        plan=plan,
        costo=round(costo, 2),
        nodos_expandidos=expandidos,
        nodos_generados=generados,
        profundidad=profundidad,
        tiempo=time.perf_counter() - inicio,
        encontrado=encontrado,
        algoritmo=algoritmo,
        escenario=getattr(problema, "descripcion", type(problema).__name__),
    )


def busqueda_amplitud(
    problema: Problema[EstadoT, AccionT],
    limite_profundidad: int | None = None,
) -> Resultado:
    """BFS: explora por niveles y garantiza el plan con menos acciones.

    No minimiza el costo cuando los operadores tienen precios distintos; para
    eso se usa :func:`costo_uniforme` o A*. El límite de profundidad, si se da,
    acota los niveles expandidos sin afectar la optimalidad en visitas.

    Args:
        problema: Problema a resolver.
        limite_profundidad: Nivel máximo a expandir; ``None`` para sin límite.

    Returns:
        Resultado con el plan más corto encontrado, o ``encontrado=False``.
    """
    inicio = time.perf_counter()
    inicial = problema.estado_inicial()
    frontera: deque[tuple[EstadoT, tuple[Hashable, ...], float, int]] = deque(
        [(inicial, (), 0.0, 0)]
    )
    visitados: set[EstadoT] = {inicial}
    expandidos = generados = maxima = 0

    while frontera:
        estado, plan, costo, profundidad = frontera.popleft()
        expandidos += 1
        maxima = max(maxima, profundidad)
        if problema.es_meta(estado):
            return _resultado(
                "BFS", problema, inicio, plan, costo, expandidos, generados, len(plan), True
            )
        if limite_profundidad is not None and profundidad >= limite_profundidad:
            continue
        for accion in problema.acciones(estado):
            generados += 1
            sucesor = problema.resultado(estado, accion)
            if sucesor in visitados:
                continue
            visitados.add(sucesor)
            nuevo_costo = round(costo + problema.costo_paso(estado, accion), 2)
            frontera.append((sucesor, (*plan, accion), nuevo_costo, profundidad + 1))

    return _resultado("BFS", problema, inicio, (), 0.0, expandidos, generados, maxima, False)


def busqueda_profundidad(
    problema: Problema[EstadoT, AccionT],
    limite_profundidad: int | None = None,
) -> Resultado:
    """DFS: baja por una rama hasta el límite y luego retrocede.

    Args:
        problema: Problema a resolver.
        limite_profundidad: Profundidad máxima; ``None`` usa ``LIMITE_PROFUNDIDAD_DFS``
            del módulo :mod:`config` para evitar recorridos infinitos.

    Returns:
        Resultado con el primer plan encontrado, que no es óptimo en general.
    """
    from config import LIMITE_PROFUNDIDAD_DFS

    limite = LIMITE_PROFUNDIDAD_DFS if limite_profundidad is None else limite_profundidad
    if limite < 0:
        raise ValueError("El límite de profundidad no puede ser negativo")

    inicio = time.perf_counter()
    inicial = problema.estado_inicial()
    frontera: list[tuple[EstadoT, tuple[Hashable, ...], float, int]] = [(inicial, (), 0.0, 0)]
    # Se guarda la menor profundidad con la que se alcanzó cada estado: una visita
    # posterior con menos pasos restantes sí puede conducir a la meta dentro del
    # límite, así que no debe descartarse.
    mejor_profundidad: dict[EstadoT, int] = {inicial: 0}
    expandidos = generados = maxima = 0

    while frontera:
        estado, plan, costo, profundidad = frontera.pop()
        expandidos += 1
        maxima = max(maxima, profundidad)
        if problema.es_meta(estado):
            return _resultado(
                "DFS", problema, inicio, plan, costo, expandidos, generados, len(plan), True
            )
        if profundidad >= limite:
            continue
        sucesores: list[tuple[EstadoT, Hashable, float]] = []
        for accion in problema.acciones(estado):
            generados += 1
            sucesor = problema.resultado(estado, accion)
            nueva_profundidad = profundidad + 1
            if mejor_profundidad.get(sucesor, math.inf) <= nueva_profundidad:
                continue
            mejor_profundidad[sucesor] = nueva_profundidad
            sucesores.append((sucesor, accion, problema.costo_paso(estado, accion)))
        # Se apilan en orden inverso para respetar el orden declarado de acciones.
        for sucesor, accion, costo_paso in reversed(sucesores):
            frontera.append(
                (
                    sucesor,
                    (*plan, accion),
                    round(costo + costo_paso, 2),
                    profundidad + 1,
                )
            )

    return _resultado("DFS", problema, inicio, (), 0.0, expandidos, generados, maxima, False)


def backtracking(
    problema: Problema[EstadoT, AccionT],
    limite_profundidad: int | None = None,
) -> Resultado:
    """Backtracking recursivo con control global de estados repetidos.

    Explora en profundidad probando acciones en orden y retrocede cuando una
    rama no prospera. Para cada estado se recuerda la menor profundidad con la
    que se alcanzó: solo se descarta una visita posterior si llega igual o más
    tarde. Así se preserva la completitud dentro del límite de profundidad.
    No garantiza el menor costo.

    Args:
        problema: Problema a resolver.
        limite_profundidad: Profundidad máxima de la recursión.

    Returns:
        Resultado con el primer plan encontrado en orden de acciones.
    """
    from config import LIMITE_PROFUNDIDAD_DFS

    limite = LIMITE_PROFUNDIDAD_DFS if limite_profundidad is None else limite_profundidad
    if limite < 0:
        raise ValueError("El límite de profundidad no puede ser negativo")

    inicio = time.perf_counter()
    expandidos = generados = maxima = 0
    profundidades: dict[EstadoT, int] = {}

    def visitar(
        estado: EstadoT, plan: tuple[Hashable, ...], costo: float, profundidad: int
    ) -> bool:
        """Explora una rama y devuelve si encontró la meta."""
        nonlocal expandidos, generados, maxima, mejor_plan, mejor_costo, mejor_profundidad
        expandidos += 1
        maxima = max(maxima, profundidad)
        if problema.es_meta(estado):
            mejor_plan, mejor_costo, mejor_profundidad = plan, costo, len(plan)
            return True
        if profundidad >= limite:
            return False
        profundidades[estado] = profundidad
        for accion in problema.acciones(estado):
            generados += 1
            sucesor = problema.resultado(estado, accion)
            nueva_profundidad = profundidad + 1
            if profundidades.get(sucesor, math.inf) <= nueva_profundidad:
                continue
            if visitar(
                sucesor,
                (*plan, accion),
                round(costo + problema.costo_paso(estado, accion), 2),
                nueva_profundidad,
            ):
                return True
        return False

    mejor_plan: tuple[Hashable, ...] = ()
    mejor_costo = 0.0
    mejor_profundidad = maxima
    inicial = problema.estado_inicial()
    profundidades[inicial] = 0
    encontrado = visitar(inicial, (), 0.0, 0)
    return _resultado(
        "Backtracking",
        problema,
        inicio,
        mejor_plan,
        mejor_costo,
        expandidos,
        generados,
        mejor_profundidad if encontrado else maxima,
        encontrado,
    )


def costo_uniforme(problema: Problema[EstadoT, AccionT]) -> Resultado:
    """Dijkstra sobre el espacio de estados: óptimo cuando los costos varían.

    Es la referencia independiente para verificar la optimalidad de A*. Mantiene
    la mejor certeza conocida por estado y descarta entradas obsoletas de la
    cola de prioridad.

    Args:
        problema: Problema a resolver con costos no negativos.

    Returns:
        Resultado con el plan de costo mínimo, o ``encontrado=False``.
    """
    inicio = time.perf_counter()
    inicial = problema.estado_inicial()
    contador = itertools.count()
    frontera: list[tuple[float, int, EstadoT, tuple[Hashable, ...], int]] = [
        (0.0, next(contador), inicial, (), 0)
    ]
    mejor: dict[EstadoT, float] = {inicial: 0.0}
    expandidos = generados = 0

    while frontera:
        costo, _, estado, plan, profundidad = heapq.heappop(frontera)
        if costo > mejor.get(estado, math.inf):
            continue
        expandidos += 1
        if problema.es_meta(estado):
            return _resultado(
                "Costo uniforme",
                problema,
                inicio,
                plan,
                costo,
                expandidos,
                generados,
                len(plan),
                True,
            )
        for accion in problema.acciones(estado):
            generados += 1
            sucesor = problema.resultado(estado, accion)
            nuevo_costo = round(costo + problema.costo_paso(estado, accion), 2)
            if nuevo_costo >= mejor.get(sucesor, math.inf):
                continue
            mejor[sucesor] = nuevo_costo
            heapq.heappush(
                frontera,
                (nuevo_costo, next(contador), sucesor, (*plan, accion), profundidad + 1),
            )

    return _resultado("Costo uniforme", problema, inicio, (), 0.0, expandidos, generados, 0, False)
