"""Composition root de la Fase 6.

Aquí —y solo aquí— se instancian el modelo, la base de reglas, la memoria, el
motor difuso, A* y la fachada. :class:`~core.sistema.SistemaInteligente` recibe
todos esos objetos ya construidos por constructor.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from config import ARCHIVO_MODELO, ARCHIVO_REGLAS_EXPERTO, ARCHIVO_VENTAS_CRUDO
from core.contexto import ContextoNegocio, contexto_desde_dataframe
from core.planificador import PlanificadorComercial
from core.sistema import SistemaInteligente
from expert_system.base_conocimientos import BaseConocimientos
from expert_system.explicacion import explicar
from expert_system.logica_difusa import SistemaDifuso
from expert_system.memoria_trabajo import MemoriaTrabajo
from expert_system.motor_inferencia import MotorInferencia
from ml.predictor import PredictorVentas
from search.espacio_estados import ProblemaPlanComercial
from search.informada import a_estrella


def construir_sistema(
    ruta_modelo: Path | str = ARCHIVO_MODELO,
    ruta_reglas: Path | str = ARCHIVO_REGLAS_EXPERTO,
    incluir_explicacion: bool = True,
) -> SistemaInteligente:
    """Construye e inyecta todas las dependencias del sistema inteligente.

    Args:
        ruta_modelo: Artefacto joblib entrenado en la Fase 2.
        ruta_reglas: Base declarativa de reglas de la Fase 3.
        incluir_explicacion: Si se calculan factores SHAP en cada predicción.

    Returns:
        Fachada lista para recibir ``ejecutar(contexto)``.
    """
    predictor = PredictorVentas(ruta_modelo, incluir_explicacion=incluir_explicacion)
    base = BaseConocimientos.desde_json(ruta_reglas)
    memoria = MemoriaTrabajo()
    motor = MotorInferencia(base, memoria, fuzzificador=SistemaDifuso())
    planificador = PlanificadorComercial(
        crear_problema=ProblemaPlanComercial,
        buscar=a_estrella,
    )
    return SistemaInteligente(
        predictor=predictor,
        base=base,
        memoria=memoria,
        motor=motor,
        planificador=planificador,
        explicador=explicar,
    )


def construir_contexto_desde_csv(
    sucursal: str,
    categoria: str,
    ruta_csv: Path | str = ARCHIVO_VENTAS_CRUDO,
    fecha_corte: str | None = None,
    **sobrescribir: object,
) -> ContextoNegocio:
    """Lee el dataset y devuelve un contexto de 8 semanas para la fachada."""
    crudo = pd.read_csv(ruta_csv, parse_dates=["fecha_semana"])
    return contexto_desde_dataframe(
        crudo,
        sucursal,
        categoria,
        fecha_corte=fecha_corte,
        **sobrescribir,
    )
