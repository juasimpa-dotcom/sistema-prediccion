"""Contratos mínimos que la fachada exige a sus dependencias inyectadas.

La fachada depende de estos protocolos, no de las implementaciones concretas.
Así las pruebas unitarias pueden sustituir cualquier componente por un doble sin
arrancar el modelo, cargar reglas ni ejecutar A*.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

import pandas as pd

from core.planificador import SolicitudPlan
from core.resultado import PlanRecomendado
from expert_system.base_conocimientos import BaseConocimientos
from expert_system.explicacion import Explicacion
from expert_system.logica_difusa import HechoDifuso, ResultadoDifuso
from expert_system.memoria_trabajo import MemoriaTrabajo
from expert_system.motor_inferencia import TrazaInferencia
from ml.predictor import PrediccionVentas


class Predictor(Protocol):
    """Componente no simbólico que predice ventas y explica la predicción."""

    def predecir(self, entrada: Mapping[str, object] | pd.DataFrame) -> PrediccionVentas:
        """Predice una semana a partir del historial o de un DataFrame de características."""
        ...


class Motor(Protocol):
    """Motor experto con fuzzificación explícita y traza de inferencia."""

    memoria: MemoriaTrabajo
    ultimo_resultado_difuso: ResultadoDifuso | None

    def fuzzificar(self, memoria: MemoriaTrabajo | None = None) -> tuple[HechoDifuso, ...]:
        """Convierte hechos numéricos en hechos simbólicos."""
        ...

    def aplicar_difuso(self, memoria: MemoriaTrabajo | None = None) -> ResultadoDifuso | None:
        """Calcula y registra las salidas difusas."""
        ...

    def encadenar_adelante(self, memoria: MemoriaTrabajo | None = None) -> TrazaInferencia:
        """Deriva conclusiones y devuelve la traza."""
        ...


class Planificador(Protocol):
    """Componente que transforma el diagnóstico en un plan con costo."""

    def planificar(self, solicitud: SolicitudPlan) -> PlanRecomendado:
        """Devuelve el mejor plan para la solicitud dada."""
        ...


class Explicador(Protocol):
    """Constructor de explicaciones en español a partir de la traza."""

    def __call__(
        self,
        objetivo: str,
        valor: object,
        base: BaseConocimientos,
        traza: TrazaInferencia | None = None,
        memoria: MemoriaTrabajo | None = None,
    ) -> Explicacion:
        """Explica una conclusión del sistema experto."""
        ...
