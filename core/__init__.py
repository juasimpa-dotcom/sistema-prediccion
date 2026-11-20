"""Fachada de integración de los componentes del sistema inteligente.

La fachada :class:`~core.sistema.SistemaInteligente` expone un único punto de
entrada ``ejecutar(contexto)``. La composición de dependencias vive en
:mod:`core.fabrica`; este paquete no crea instancias globales.
"""

from __future__ import annotations

from core.contexto import ContextoNegocio, contexto_desde_dataframe
from core.planificador import PlanificadorComercial, SolicitudPlan
from core.resultado import (
    CausaDiagnostico,
    ComparativaComponentes,
    PlanRecomendado,
    ResultadoSistema,
    RiesgoDifuso,
)
from core.sistema import SistemaInteligente

__all__ = [
    "CausaDiagnostico",
    "ComparativaComponentes",
    "ContextoNegocio",
    "PlanificadorComercial",
    "PlanRecomendado",
    "ResultadoSistema",
    "RiesgoDifuso",
    "SistemaInteligente",
    "SolicitudPlan",
    "contexto_desde_dataframe",
]
