"""Explicación unificada, en español, de las cinco etapas del flujo.

Compone la explicación del modelo (SHAP), la traza del sistema experto, el
riesgo difuso, la justificación del plan y la comparativa Tema 1 en un solo
texto. El constructor de explicaciones del experto se inyecta, no se importa
como instancia global.
"""

from __future__ import annotations

from config import ATRIBUTO_ACCION_EXPERTA, ATRIBUTO_CAUSA_VENTAS, ATRIBUTO_NIVEL_RIESGO
from core.puertos import Explicador
from core.resultado import (
    CausaDiagnostico,
    ComparativaComponentes,
    PlanRecomendado,
    RiesgoDifuso,
)
from expert_system.base_conocimientos import BaseConocimientos
from expert_system.memoria_trabajo import MemoriaTrabajo
from expert_system.motor_inferencia import TrazaInferencia
from ml.predictor import PrediccionVentas


def _texto_explicacion(resultado: object) -> str:
    """Acepta tanto ``Explicacion`` como cualquier doble con ``a_texto``."""
    if hasattr(resultado, "a_texto") and callable(resultado.a_texto):
        return str(resultado.a_texto())
    return str(resultado)


def _traza_en_texto(traza: TrazaInferencia | None) -> str:
    """Resume en español los reglas disparadas por el motor."""
    if traza is None or not traza.pasos:
        return "No se disparó ninguna regla: los hechos no alcanzaron el umbral."
    return "\n".join(
        f"  {paso.orden}. [{paso.categoria}] {paso.regla_id}: {paso.descripcion} "
        f"=> {paso.conclusion} (CF {paso.cf_conclusion:+.3f})"
        for paso in traza.pasos
    )


def explicacion_unificada(
    prediccion: PrediccionVentas,
    cumplimiento_pct: float,
    diagnostico: tuple[CausaDiagnostico, ...],
    riesgo: RiesgoDifuso,
    plan: PlanRecomendado,
    comparativa: ComparativaComponentes,
    base: BaseConocimientos,
    traza: TrazaInferencia,
    memoria: MemoriaTrabajo,
    explicador: Explicador,
) -> str:
    """Devuelve la explicación completa de una ejecución.

    Args:
        prediccion: Predicción del componente no simbólico.
        cumplimiento_pct: Cumplimiento sobre la meta efectiva.
        diagnostico: Causas del sistema experto.
        riesgo: Resultado de la etapa difusa.
        plan: Plan devuelto por A*.
        comparativa: Comparativa de componentes.
        base: Base de conocimientos usada por el explicador.
        traza: Traza de inferencia crisp.
        memoria: Memoria con todos los hechos.
        explicador: Constructor de explicaciones inyectado.

    Returns:
        Texto en español con las cinco secciones.
    """
    factores = "\n".join(f"  - {factor}" for factor in prediccion.principales_factores)
    ml = (
        "=== 1. POR QUÉ PREDIJO ESA CIFRA (componente no simbólico) ===\n"
        f"El modelo estimó {prediccion.valor_predicho:,.2f} Bs para la semana siguiente, "
        f"un {cumplimiento_pct:.1f}% de la meta, con confianza calibrada de "
        f"{prediccion.confianza:.3f}. Esa confianza se reutilizó como factor de certeza "
        "inicial de los hechos inyectados en la memoria de trabajo.\n"
        "Variables que más pesaron en la predicción (SHAP):\n"
        f"{factores or '  - sin factores informativos'}"
    )

    objetivo = ATRIBUTO_CAUSA_VENTAS if diagnostico else ATRIBUTO_ACCION_EXPERTA
    valor: object = diagnostico[0].causa if diagnostico else None
    if valor is None:
        hecho = memoria.consultar(ATRIBUTO_ACCION_EXPERTA)
        if hecho is not None:
            objetivo, valor = ATRIBUTO_ACCION_EXPERTA, hecho.valor
        else:
            hecho = memoria.consultar(ATRIBUTO_NIVEL_RIESGO)
            if hecho is not None:
                objetivo, valor = ATRIBUTO_NIVEL_RIESGO, hecho.valor
            else:
                objetivo, valor = ATRIBUTO_NIVEL_RIESGO, "sin conclusión"

    detalle = _texto_explicacion(explicador(objetivo, valor, base, traza, memoria))
    simbolico = (
        "\n\n=== 2. QUÉ REGLAS DISPARARON Y POR QUÉ (componente simbólico) ===\n"
        "Diagnóstico: "
        + (
            "; ".join(causa.a_texto() for causa in diagnostico)
            if diagnostico
            else "ninguna causa superó el umbral de certeza."
        )
        + "\n\nReglas disparadas en orden:\n"
        + _traza_en_texto(traza)
        + "\n\nExplicación del motor:\n"
        + detalle
    )

    difuso = (
        "\n\n=== 3. CÓMO SE GRADUÓ EL RIESGO (lógica difusa) ===\n"
        + riesgo.a_texto()
        + "\nLa defuzzificación por centroide convierte grados de pertenencia parciales "
        "en una etiqueta auditable por el motor crisp, que después dispara las reglas F01-F08."
    )

    plan_texto = (
        "\n\n=== 4. POR QUÉ RECOMIENDA ESE PLAN (A* sobre el diagnóstico) ===\n" + plan.a_texto()
    )

    comparativa_texto = "\n\n=== 5. COMPARATIVA SIMBÓLICO vs. NO SIMBÓLICO (Tema 1) ===\n"
    comparativa_texto += comparativa.a_texto()

    return ml + simbolico + difuso + plan_texto + comparativa_texto
