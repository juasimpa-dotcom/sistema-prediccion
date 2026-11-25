"""Tipos de salida de la fachada y constructores puros a partir de la memoria.

Toda la información que produce el flujo queda concentrada en
:class:`ResultadoSistema`: predicción, diagnóstico con factores de certeza,
riesgo difuso, plan con costo y explicación en español. No hay efectos laterales
ni dependencias externas en este módulo.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from config import (
    ATRIBUTO_CAUSA_VENTAS,
    ATRIBUTO_RIESGO_DIFUSO,
    SALIDAS_DIFUSAS,
)
from expert_system.logica_difusa import ResultadoDifuso
from expert_system.memoria_trabajo import MemoriaTrabajo
from expert_system.motor_inferencia import PasoInferencia, TrazaInferencia
from ml.predictor import PrediccionVentas
from search.resultado import NodoBusqueda


@dataclass(frozen=True, slots=True)
class CausaDiagnostico:
    """Causa derivada por el sistema experto, con su certeza combinada.

    Attributes:
        causa: Valor del atributo ``causa_ventas_bajas``.
        cf: Factor de certeza final tras combinar todas las evidencias.
        descripcion: Intuición de negocio de la regla que la respalda.
        reglas: Identificadores de las reglas que concluyeron esta causa.
    """

    causa: str
    cf: float
    descripcion: str
    reglas: tuple[str, ...] = ()

    def a_texto(self) -> str:
        """Devuelve la causa en una línea legible."""
        origen = ", ".join(self.reglas) if self.reglas else "hecho del contexto"
        return f"- {self.causa}: FC {self.cf:+.3f} ({origen}). {self.descripcion}"


@dataclass(frozen=True, slots=True)
class RiesgoDifuso:
    """Riesgo defuzzificado y traducido a una etiqueta lingüística.

    Attributes:
        etiqueta: Etiqueta dominante del centroide de riesgo.
        valor: Centroide numérico en la escala configurada.
        grado: Grado de pertenencia de la etiqueta dominante.
        urgencia: Etiqueta dominante de la urgencia de acción.
        reglas_activadas: Reglas difusas con fuerza positiva.
        descripcion: Resumen del resultado difuso.
        fuerzas_reglas: Fuerza de activación real de cada regla difusa.
    """

    etiqueta: str
    valor: float
    grado: float
    urgencia: str
    reglas_activadas: tuple[str, ...]
    descripcion: str
    fuerzas_reglas: dict[str, float] = field(default_factory=dict)

    @property
    def magnitud(self) -> str:
        """Devuelve riesgo y urgencia en una sola frase corta."""
        return f"{self.etiqueta} (centroide {self.valor:.1f}, urgencia {self.urgencia})"

    def a_texto(self) -> str:
        """Devuelve el riesgo difuso en texto legible."""
        reglas = ", ".join(self.reglas_activadas) if self.reglas_activadas else "ninguna"
        return (
            f"Riesgo difuso {self.magnitud}; pertenencia {self.grado:.3f}. "
            f"Reglas activadas: {reglas}."
        )


@dataclass(frozen=True, slots=True)
class PlanRecomendado:
    """Plan de acciones devuelto por A* sobre el diagnóstico.

    Attributes:
        acciones: Operadores en el orden en que deben ejecutarse.
        costo_bs: Costo total estimado del plan.
        encontrado: Si A* alcanzó la meta dentro del presupuesto.
        nodos_expandidos: Estados evaluados por la búsqueda.
        restricciones: Operadores excluidos por el diagnóstico.
        justificacion: Por qué el diagnóstico conduce a este plan.
        nodos_generados: Estados creados durante la búsqueda.
        profundidad: Cantidad de acciones del plan encontrado.
        nodos: Estados visitados, con su relación padre-hijo y sus métricas.
    """

    acciones: tuple[str, ...]
    costo_bs: float
    encontrado: bool
    nodos_expandidos: int
    restricciones: tuple[str, ...]
    justificacion: str
    nodos_generados: int = 0
    profundidad: int = 0
    nodos: tuple[NodoBusqueda, ...] = ()

    @property
    def descripcion(self) -> str:
        """Devuelve el plan en texto legible."""
        if not self.encontrado:
            return "sin solución dentro del presupuesto"
        if not self.acciones:
            return "sin acciones (la meta ya se alcanza)"
        return " => ".join(self.acciones)

    def a_texto(self) -> str:
        """Devuelve el plan y su justificación."""
        return (
            f"Plan: {self.descripcion}. Costo: {self.costo_bs:,.2f} Bs "
            f"({self.nodos_expandidos} nodos expandidos).\n{self.justificacion}"
        )


@dataclass(frozen=True, slots=True)
class ComparativaComponentes:
    """Comparativa documentada entre el componente simbólico y el no simbólico.

    Attributes:
        no_simbólico: Qué aporta el modelo de Machine Learning.
        simbolico: Qué aportan las reglas, los CF y la lógica difusa.
        complementariedad: Por qué la unión supera a cada parte por separado.
        evidencia: Huella dejada por ambos componentes en esta ejecución.
    """

    no_simbólico: str
    simbolico: str
    complementariedad: str
    evidencia: str

    def a_texto(self) -> str:
        """Devuelve la comparativa completa en español."""
        return "\n".join(
            [
                f"No simbólico (ML): {self.no_simbólico}",
                f"Simbólico (experto + difuso): {self.simbolico}",
                f"Complementariedad: {self.complementariedad}",
                f"Evidencia de esta ejecución: {self.evidencia}",
            ]
        )


@dataclass(frozen=True, slots=True)
class ResultadoSistema:
    """Resultado completo y tipado de una ejecución de la fachada.

    Attributes:
        sucursal: Sucursal analizada.
        categoria: Categoría analizada.
        prediccion: Predicción y factores SHAP del modelo.
        cumplimiento_pct: Cumplimiento respecto de la meta efectiva.
        diagnostico: Causas rankeadas por factor de certeza.
        riesgo: Riesgo difuso resultante.
        plan: Plan de acciones con costo y justificación.
        explicacion: Explicación unificada en español.
        comparativa: Comparativa simbólico vs. no simbólico (Tema 1).
        reglas_disparadas: Reglas crisp disparadas, en orden de ejecución.
        reglas_aplicadas: Pasos completos de inferencia, con condición, certeza y prioridad.
    """

    sucursal: str
    categoria: str
    prediccion: PrediccionVentas
    cumplimiento_pct: float
    diagnostico: tuple[CausaDiagnostico, ...]
    riesgo: RiesgoDifuso
    plan: PlanRecomendado
    explicacion: str
    comparativa: ComparativaComponentes
    reglas_disparadas: tuple[str, ...]
    reglas_aplicadas: tuple[PasoInferencia, ...] = ()

    @property
    def confianza(self) -> float:
        """Devuelve la confianza del modelo, la misma usada como CF inicial."""
        return self.prediccion.confianza

    def resumen(self) -> str:
        """Devuelve una línea de resumen para la demostración."""
        causas = ", ".join(causa.causa for causa in self.diagnostico) or "sin causas"
        return (
            f"{self.sucursal}/{self.categoria}: {self.prediccion.valor_predicho:,.2f} Bs "
            f"({self.cumplimiento_pct:.1f}% de meta, confianza {self.confianza:.2f}); "
            f"causas [{causas}]; riesgo {self.riesgo.etiqueta}; plan {self.plan.descripcion}"
        )


def causas_desde_memoria(
    memoria: MemoriaTrabajo,
    traza: TrazaInferencia | None = None,
) -> tuple[CausaDiagnostico, ...]:
    """Extrae las causas de la memoria con su CF final y sus reglas de respaldo."""
    valores = dict.fromkeys(hecho.valor for hecho in memoria.evidencias(ATRIBUTO_CAUSA_VENTAS))
    causas: list[CausaDiagnostico] = []
    for valor in valores:
        consolidado = memoria.consultar(ATRIBUTO_CAUSA_VENTAS, valor)
        if consolidado is None or consolidado.fc <= 0:
            continue
        pasos = (
            paso
            for paso in (traza.pasos if traza is not None else ())
            if paso.conclusion_atributo == ATRIBUTO_CAUSA_VENTAS and paso.conclusion_valor == valor
        )
        respaldos = tuple(pasos)
        causas.append(
            CausaDiagnostico(
                causa=str(valor),
                cf=round(consolidado.fc, 4),
                descripcion=respaldos[0].descripcion if respaldos else consolidado.detalle,
                reglas=tuple(paso.regla_id for paso in respaldos),
            )
        )
    return tuple(sorted(causas, key=lambda causa: -abs(causa.cf)))


def riesgo_desde_difuso(
    resultado: ResultadoDifuso | None,
    memoria: MemoriaTrabajo,
) -> RiesgoDifuso:
    """Convierte el resultado difuso en el tipo de salida de la fachada."""
    variable_riesgo = SALIDAS_DIFUSAS[0]
    variable_urgencia = SALIDAS_DIFUSAS[1]
    if resultado is None:
        hecho = memoria.consultar(ATRIBUTO_RIESGO_DIFUSO)
        return RiesgoDifuso(
            etiqueta=str(hecho.valor) if hecho is not None else "desconocido",
            valor=0.0,
            grado=round(hecho.fc, 4) if hecho is not None else 0.0,
            urgencia="desconocida",
            reglas_activadas=(),
            descripcion="No se ejecutó lógica difusa; solo hay evidencia crisp.",
            fuerzas_reglas={},
        )
    etiqueta = resultado.etiquetas.get(variable_riesgo, "desconocida")
    return RiesgoDifuso(
        etiqueta=etiqueta,
        valor=round(resultado.valores.get(variable_riesgo, 0.0), 2),
        grado=round(resultado.grados.get(variable_riesgo, {}).get(etiqueta, 0.0), 4),
        urgencia=resultado.etiquetas.get(variable_urgencia, "desconocida"),
        reglas_activadas=resultado.reglas_activadas,
        descripcion=resultado.descripcion(),
        fuerzas_reglas={
            identificador: round(fuerza, 4)
            for identificador, fuerza in resultado.fuerzas.items()
            if fuerza > 0.0
        },
    )


def comparativa_componentes(
    prediccion: PrediccionVentas,
    diagnostico: tuple[CausaDiagnostico, ...],
    riesgo: RiesgoDifuso,
    traza: TrazaInferencia | None = None,
) -> ComparativaComponentes:
    """Documenta la colaboración entre ML y razonamiento simbólico (Tema 1)."""
    factores = ", ".join(prediccion.principales_factores) or "sin factores informativos"
    causas = ", ".join(causa.causa for causa in diagnostico) or "ninguna"
    reglas = ", ".join(paso.regla_id for paso in traza.pasos) if traza is not None else "ninguna"
    return ComparativaComponentes(
        no_simbólico=(
            "Aprende de los datos con un pipeline calibrado: entrega un número "
            "predicho, una confianza y factores SHAP. No conoce reglas de negocio "
            "ni puede justificar por sí solo qué acción conviene."
        ),
        simbolico=(
            "Opera sobre hechos y significado: factores de certeza estilo MYCIN "
            "para la duda, lógica difusa para la vaguedad de conceptos como "
            "'stock crítico', y reglas auditables con traza de disparo. No aprende "
            "de los datos, pero sí explica y restringe decisiones."
        ),
        complementariedad=(
            "El ML propone la magnitud y su evidencia estadística; el componente "
            "simbólico convierte esa magnitud en hechos con CF, diagnostica causas, "
            "gradúa el riesgo y poda el espacio de búsqueda antes de aplicar A*."
        ),
        evidencia=factores + f"; SHAP explica la predicción. Causas: {causas}. "
        f"Reglas crisp: {reglas}. Riesgo difuso: {riesgo.magnitud}.",
    )


def campos_difusos(datos: Mapping[str, object]) -> dict[str, float]:
    """Filtra los hechos numéricos necesarios para la fuzzificación."""
    return {
        str(clave): float(valor)
        for clave, valor in datos.items()
        if isinstance(valor, (int, float)) and not isinstance(valor, bool)
    }
