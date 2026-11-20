"""Planificador comercial: convierte el diagnóstico en un problema para A*.

La clase no Instancia el problema directamente: recibe por constructor la
fábrica del problema y el algoritmo de búsqueda. Así la fachada no crea
dependencias y las pruebas pueden inyectar dobles en cualquier nivel.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TypeVar

from config import (
    REPOSICION_UNIDADES,
    RESTRICCIONES_CAUSA_OPERADOR,
    STOCK_MAXIMO_UNIDADES,
)
from core.resultado import CausaDiagnostico, PlanRecomendado
from search.espacio_estados import Accion, EstadoPlan, Problema
from search.informada import a_estrella
from search.resultado import Resultado

ProblemaT = TypeVar("ProblemaT", bound=Problema[EstadoPlan, Accion])
OPERADORES_RESTRINGIBLES: tuple[str, ...] = (
    "permitir_reasignacion",
    "permitir_reducir_merma",
)


@dataclass(frozen=True, slots=True)
class SolicitudPlan:
    """Datos necesarios para plantear la búsqueda de acciones.

    Attributes:
        sucursal: Sucursal del escenario.
        categoria: Categoría del escenario.
        meta_bs: Meta de ventas a alcanzar.
        presupuesto_bs: Presupuesto máximo de la campaña.
        stock_inicial: Unidades disponibles antes de intervenir.
        merma_inicial: Merma porcentual esperada.
        personal_inicial: Dotación inicial.
        afluencia: Clientes esperados.
        causas: Diagnóstico del sistema experto, ordenado por certeza.
    """

    sucursal: str
    categoria: str
    meta_bs: float
    presupuesto_bs: float
    stock_inicial: float
    merma_inicial: float
    personal_inicial: float
    afluencia: float
    causas: tuple[CausaDiagnostico, ...] = ()


def restricciones_por_causas(
    causas: tuple[CausaDiagnostico, ...],
) -> tuple[str, ...]:
    """Devuelve los operadores desactivados por el diagnóstico.

    Varias causas pueden opinar sobre el mismo operador; se conserva el
    permiso solo si todas lo permiten. El orden es determinista.
    """
    permisos: dict[str, bool] = dict.fromkeys(OPERADORES_RESTRINGIBLES, True)
    for causa in causas:
        reglas: Mapping[str, bool] = RESTRICCIONES_CAUSA_OPERADOR.get(causa.causa, {})
        for nombre, permitido in reglas.items():
            permisos[nombre] = permisos[nombre] and bool(permitido)
    return tuple(nombre for nombre in OPERADORES_RESTRINGIBLES if not permisos[nombre])


def _justificacion(
    causas: tuple[CausaDiagnostico, ...],
    restricciones: tuple[str, ...],
    resultado: Resultado,
) -> str:
    """Explica por qué el diagnóstico conduce al plan encontrado."""
    lineas: list[str] = []
    if causas:
        lineas.append(
            "El diagnóstico priorizó "
            + ", ".join(f"{causa.causa} (FC {causa.cf:+.2f})" for causa in causas)
            + "."
        )
    else:
        lineas.append("El diagnóstico no encontró causas con certeza positiva.")

    if restricciones:
        legibles = {
            "permitir_reasignacion": "reasignar inventario",
            "permitir_reducir_merma": "reducir merma",
        }
        lineas.append(
            "Se excluyeron por el diagnóstico: "
            + ", ".join(legibles.get(nombre, nombre) for nombre in restricciones)
            + "."
        )
    else:
        lineas.append("Todos los operadores comerciales seguían disponibles.")

    if resultado.encontrado:
        lineas.append(
            f"A* eligió el plan de menor costo ({resultado.costo:,.2f} Bs) "
            f"entre {resultado.nodos_expandidos} estados expandidos; se ejecuta "
            "primero la palanca que cierra el déficit con mejor relación costo/ganancia."
        )
    else:
        lineas.append("A* agotó los estados alcanzables sin llegar a la meta con ese presupuesto.")
    return "\n".join(lineas)


class PlanificadorComercial:
    """Envuelve A* y parametriza el problema según el diagnóstico recibido."""

    def __init__(
        self,
        crear_problema: Callable[..., ProblemaT],
        buscar: Callable[[ProblemaT], Resultado] = a_estrella,
    ) -> None:
        """Inicializa el planificador con dependencias inyectadas.

        Args:
            crear_problema: Fábrica de :class:`ProblemaPlanComercial`.
            buscar: Algoritmo de búsqueda; A* por defecto.

        Raises:
            TypeError: Si alguna dependencia no es invocable.
        """
        if not callable(crear_problema) or not callable(buscar):
            raise TypeError("crear_problema y buscar deben ser invocables")
        self.crear_problema = crear_problema
        self.buscar = buscar

    def planificar(self, solicitud: SolicitudPlan) -> PlanRecomendado:
        """Resuelve el plan e incrusta su justificación en el resultado."""
        restricciones = restricciones_por_causas(solicitud.causas)
        permitidos = {nombre: nombre not in restricciones for nombre in OPERADORES_RESTRINGIBLES}
        stock = int(round(solicitud.stock_inicial))
        problema = self.crear_problema(
            sucursal=solicitud.sucursal,
            categoria=solicitud.categoria,
            meta_bs=solicitud.meta_bs,
            presupuesto_bs=solicitud.presupuesto_bs,
            stock_inicial=stock,
            stock_maximo=max(STOCK_MAXIMO_UNIDADES, stock + REPOSICION_UNIDADES),
            merma_inicial=solicitud.merma_inicial,
            personal_inicial=int(round(solicitud.personal_inicial)),
            afluencia=solicitud.afluencia,
            **permitidos,
        )
        resultado = self.buscar(problema)
        return PlanRecomendado(
            acciones=tuple(str(accion) for accion in resultado.plan),
            costo_bs=resultado.costo,
            encontrado=resultado.encontrado,
            nodos_expandidos=resultado.nodos_expandidos,
            restricciones=restricciones,
            justificacion=_justificacion(solicitud.causas, restricciones, resultado),
        )
