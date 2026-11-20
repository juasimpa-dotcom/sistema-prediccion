"""Fachada ``SistemaInteligente``: un único punto de entrada para todo el flujo.

El constructor recibe todas las dependencias. ``ejecutar`` solo orquesta:
predice, inyecta hechos con CF derivado de la confianza, fuzzifica, infiere,
planifica con A* sobre el diagnóstico y compone la explicación final.
"""

from __future__ import annotations

import logging
from typing import cast

from config import (
    ATRIBUTO_CAUSA_VENTAS,
    ATRIBUTO_CONFIANZA_ML,
    ATRIBUTO_PREDICCION_BS,
    CAUSA_EXCESO_STOCK,
    CONFIANZA_MAXIMA,
    CONFIANZA_MINIMA,
    EPSILON,
    ORIGEN_CONTEXTO,
    ORIGEN_ML,
    UMBRAL_EXCESO_STOCK,
)
from core.contexto import ContextoNegocio
from core.explicacion import explicacion_unificada
from core.planificador import SolicitudPlan
from core.puertos import Explicador, Motor, Planificador, Predictor
from core.resultado import (
    ResultadoSistema,
    campos_difusos,
    causas_desde_memoria,
    comparativa_componentes,
    riesgo_desde_difuso,
)
from expert_system.base_conocimientos import BaseConocimientos
from expert_system.explicacion import explicar
from expert_system.memoria_trabajo import Hecho, MemoriaTrabajo
from ml.predictor import PrediccionVentas

LOGGER = logging.getLogger(__name__)


class SistemaInteligente:
    """Fachada que integra ML, experto, difuso, búsqueda y explicación.

    Attributes:
        predictor: Modelo calibrado que predice ventas y factores SHAP.
        base: Base de conocimientos utilizada por el motor y el explicador.
        memoria: Memoria de trabajo compartida por la inferencia.
        motor: Motor de inferencia con fuzzificador inyectado.
        planificador: Envoltorio de A* parametrizado por el diagnóstico.
        explicador: Función que construye explicaciones en español.
    """

    def __init__(
        self,
        predictor: Predictor,
        base: BaseConocimientos,
        memoria: MemoriaTrabajo,
        motor: Motor,
        planificador: Planificador,
        explicador: Explicador = explicar,
    ) -> None:
        """Conecta las dependencias ya construidas por la fábrica o por las pruebas.

        Raises:
            TypeError: Si una dependencia no tiene el tipo o la interfaz esperada.
        """
        if not hasattr(predictor, "predecir") or not callable(predictor.predecir):
            raise TypeError("El predictor debe exponer predecir()")
        if not isinstance(base, BaseConocimientos):
            raise TypeError("La base debe ser una BaseConocimientos")
        if not isinstance(memoria, MemoriaTrabajo):
            raise TypeError("La memoria debe ser una MemoriaTrabajo")
        if not callable(explicador):
            raise TypeError("explicador debe ser invocable")
        for nombre in ("fuzzificar", "aplicar_difuso", "encadenar_adelante"):
            if not callable(getattr(motor, nombre, None)):
                raise TypeError(f"El motor debe exponer {nombre}()")
        if not callable(getattr(planificador, "planificar", None)):
            raise TypeError("El planificador debe exponer planificar()")

        self.predictor = predictor
        self.base = base
        self.memoria = memoria
        self.motor = motor
        self.planificador = planificador
        self.explicador = explicador

    def ejecutar(self, contexto: ContextoNegocio) -> ResultadoSistema:
        """Ejecuta el flujo completo y devuelve el resultado integral.

        Args:
            contexto: Sucursal, categoría, historial y datos observados.

        Returns:
            Resultado tipado con predicción, diagnóstico, riesgo, plan,
            explicación y comparativa de componentes.
        """
        prediccion = self.predictor.predecir(contexto.entrada_prediccion())
        meta_bs = contexto.meta_efectiva()
        cumplimiento = round(prediccion.valor_predicho / max(meta_bs, EPSILON) * 100.0, 2)
        observado = contexto.datos_observados()

        for hecho in self._hechos(contexto, prediccion, observado, cumplimiento):
            self.memoria.registrar(hecho)

        self.motor.fuzzificar(self.memoria)
        resultado_difuso = self.motor.aplicar_difuso(self.memoria)
        if resultado_difuso is None:
            resultado_difuso = getattr(self.motor, "ultimo_resultado_difuso", None)
        traza = self.motor.encadenar_adelante(self.memoria)

        diagnostico = causas_desde_memoria(self.memoria, traza)
        riesgo = riesgo_desde_difuso(resultado_difuso, self.memoria)

        solicitud = SolicitudPlan(
            sucursal=contexto.sucursal,
            categoria=contexto.categoria,
            meta_bs=meta_bs,
            presupuesto_bs=contexto.presupuesto_bs,
            stock_inicial=float(cast(float, observado["stock_inicial"])),
            merma_inicial=float(cast(float, observado["merma_pct"])),
            personal_inicial=float(cast(float, observado["personal_asignado"])),
            afluencia=float(cast(float, observado["afluencia_clientes"])),
            causas=diagnostico,
        )
        plan = self.planificador.planificar(solicitud)
        comparativa = comparativa_componentes(prediccion, diagnostico, riesgo, traza)
        explicacion = explicacion_unificada(
            prediccion=prediccion,
            cumplimiento_pct=cumplimiento,
            diagnostico=diagnostico,
            riesgo=riesgo,
            plan=plan,
            comparativa=comparativa,
            base=self.base,
            traza=traza,
            memoria=self.memoria,
            explicador=self.explicador,
        )

        LOGGER.info(
            "Sistema ejecutado para %s/%s: %d causas, riesgo %s, plan %s",
            contexto.sucursal,
            contexto.categoria,
            len(diagnostico),
            riesgo.etiqueta,
            plan.descripcion,
        )
        return ResultadoSistema(
            sucursal=contexto.sucursal,
            categoria=contexto.categoria,
            prediccion=prediccion,
            cumplimiento_pct=cumplimiento,
            diagnostico=diagnostico,
            riesgo=riesgo,
            plan=plan,
            explicacion=explicacion,
            comparativa=comparativa,
            reglas_disparadas=tuple(paso.regla_id for paso in traza.pasos),
        )

    @staticmethod
    def _hechos(
        contexto: ContextoNegocio,
        prediccion: PrediccionVentas,
        observado: dict[str, object],
        cumplimiento: float,
    ) -> tuple[Hecho, ...]:
        """Traduce la predicción y el contexto a hechos de la memoria de trabajo."""
        cf = min(max(prediccion.confianza, CONFIANZA_MINIMA), CONFIANZA_MAXIMA)
        detalle_modelo = "; ".join(prediccion.principales_factores[:3])
        hechos = [
            Hecho(
                ATRIBUTO_PREDICCION_BS,
                prediccion.valor_predicho,
                cf,
                ORIGEN_ML,
                f"predicción calibrada; SHAP: {detalle_modelo}",
            ),
            Hecho(
                ATRIBUTO_CONFIANZA_ML,
                prediccion.confianza,
                cf,
                ORIGEN_ML,
                "confianza usada como factor de certeza de los hechos del modelo",
            ),
            Hecho(
                "cumplimiento_esperado_pct",
                cumplimiento,
                cf,
                ORIGEN_ML,
                f"predicción frente a meta efectiva de {contexto.meta_efectiva():,.2f} Bs",
            ),
            Hecho(
                "ventas_caida_pct",
                round(max(0.0, 100.0 - cumplimiento), 4),
                cf,
                ORIGEN_ML,
                "caída relativa respecto de la meta; 0 si la meta se supera",
            ),
        ]
        for atributo, valor in observado.items():
            hechos.append(
                Hecho(
                    atributo,
                    valor,  # type: ignore[arg-type]
                    1.0,
                    ORIGEN_CONTEXTO,
                    "dato observado de la semana cerrada",
                )
            )
        cobertura = campos_difusos(observado).get("stock_cobertura", 0.0)
        if cobertura >= UMBRAL_EXCESO_STOCK:
            hechos.append(
                Hecho(
                    ATRIBUTO_CAUSA_VENTAS,
                    CAUSA_EXCESO_STOCK,
                    cf,
                    ORIGEN_CONTEXTO,
                    f"cobertura de stock {cobertura:.2f} >= {UMBRAL_EXCESO_STOCK:.2f}",
                )
            )
        return tuple(hechos)
