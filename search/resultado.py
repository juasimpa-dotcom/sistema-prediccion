"""Estructura de resultado compartida por todos los algoritmos de búsqueda."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

METRICAS_RESULTADO: tuple[str, ...] = (
    "algoritmo",
    "escenario",
    "encontrado",
    "costo",
    "nodos_expandidos",
    "nodos_generados",
    "profundidad",
    "tiempo",
)


@dataclass(frozen=True, slots=True)
class Resultado:
    """Trazabilidad y métricas de una búsqueda, sea informada o no.

    Attributes:
        plan: Secuencia de operadores desde el estado inicial hasta la meta.
        costo: Suma de ``costo_paso`` a lo largo del plan (0 si no hay solución).
        nodos_expandidos: Estados retirados de la frontera y evaluados.
        nodos_generados: Sucesores creados durante la búsqueda.
        profundidad: Longitud del plan; si falla, profundidad máxima explorada.
        tiempo: Segundos transcurridos, medidos con ``time.perf_counter``.
        encontrado: ``False`` cuando se agotó la frontera o el límite de profundidad.
        algoritmo: Nombre del algoritmo, para las tablas comparativas.
        escenario: Nombre del escenario, para las tablas comparativas.
    """

    plan: tuple[Any, ...]
    costo: float
    nodos_expandidos: int
    nodos_generados: int
    profundidad: int
    tiempo: float
    encontrado: bool = True
    algoritmo: str = ""
    escenario: str = ""

    @property
    def descripcion_plan(self) -> str:
        """Devuelve el plan en texto legible, o ``sin solución`` si no hay plan."""
        if not self.encontrado:
            return "sin solución"
        if not self.plan:
            return "sin acciones (meta inicial)"
        return " => ".join(str(accion) for accion in self.plan)

    def a_fila(self) -> dict[str, object]:
        """Convierte el resultado en una fila plana para el benchmark."""
        return {
            "algoritmo": self.algoritmo,
            "escenario": self.escenario,
            "encontrado": self.encontrado,
            "costo": round(self.costo, 2),
            "nodos_expandidos": self.nodos_expandidos,
            "nodos_generados": self.nodos_generados,
            "profundidad": self.profundidad,
            "tiempo": round(self.tiempo, 6),
        }
