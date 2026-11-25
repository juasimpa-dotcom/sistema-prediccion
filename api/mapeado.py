"""Funciones puras que proyectan el resultado del núcleo a esquemas Pydantic.

La API no reimplementa ninguna regla de negocio: todas las cifras provienen de
:class:`core.resultado.ResultadoSistema` o de :class:`core.contexto.ContextoNegocio`.
Este módulo solo las ordena, redondea y nombra para el contrato REST.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pandas as pd

from api.esquemas import (
    CausaDTO,
    ComparativaDTO,
    NodoBusquedaDTO,
    PlanDTO,
    PrediccionDTO,
    Proyeccion,
    PuntoHistorico,
    ReglaAplicadaDTO,
    ReglaSistemaDTO,
    RespuestaReglas,
    RiesgoDTO,
)
from config import REGLAS_DIFUSAS, RIESGO_SEMAFORO, ReglaDifusa
from core.contexto import ContextoNegocio
from core.resultado import ResultadoSistema, RiesgoDifuso
from expert_system.base_conocimientos import BaseConocimientos, Condicion, GrupoCondiciones, Regla

DIAS_POR_SEMANA = 7
"""Días que separa la semana cerrada ``t`` de la semana objetivo ``t + 1``."""


def _numero(valor: object, defecto: float = 0.0) -> float:
    """Convierte un valor de dataset a float sin propagar NaN."""
    try:
        resultado = float(valor)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return defecto
    return resultado if pd.notna(resultado) else defecto


def _fecha_texto(valor: object) -> str:
    """Normaliza una fecha de dataset o de contexto a ``AAAA-MM-DD``."""
    return pd.Timestamp(valor).strftime("%Y-%m-%d")


def fecha_objetivo_de(contexto: ContextoNegocio) -> str:
    """Devuelve la semana a predecir en formato ISO."""
    if contexto.fecha_objetivo is not None:
        return _fecha_texto(contexto.fecha_objetivo)
    ultima = pd.Timestamp(contexto.ultima_fila.get("fecha_semana"))
    return _fecha_texto(ultima + pd.Timedelta(days=DIAS_POR_SEMANA))


def historial_de_contexto(contexto: ContextoNegocio) -> list[PuntoHistorico]:
    """Proyecta las semanas cerradas para el gráfico histórico del dashboard."""
    puntos: list[PuntoHistorico] = []
    for fila in contexto.historial:
        puntos.append(
            PuntoHistorico(
                fecha=_fecha_texto(fila.get("fecha_semana")),
                ventas_bs=round(_numero(fila.get("ventas_bs")), 2),
                meta_bs=round(_numero(fila.get("meta_ventas_bs")), 2),
            )
        )
    return puntos


def proyeccion_de(contexto: ContextoNegocio, resultado: ResultadoSistema) -> Proyeccion:
    """Proyecta la semana objetivo junto a la meta efectiva del escenario."""
    return Proyeccion(
        fecha=fecha_objetivo_de(contexto),
        valor_predicho_bs=round(resultado.prediccion.valor_predicho, 2),
        meta_bs=round(contexto.meta_efectiva(), 2),
        cumplimiento_pct=resultado.cumplimiento_pct,
    )


def prediccion_de(resultado: ResultadoSistema) -> PrediccionDTO:
    """Proyecta predicción, confianza y factores SHAP."""
    return PrediccionDTO(
        valor_predicho_bs=round(resultado.prediccion.valor_predicho, 2),
        cumplimiento_esperado_pct=round(resultado.prediccion.cumplimiento_esperado_pct, 2),
        confianza=round(resultado.confianza, 4),
        principales_factores=list(resultado.prediccion.principales_factores),
    )


def causas_de(resultado: ResultadoSistema) -> list[CausaDTO]:
    """Proyecta el diagnóstico rankeado por factor de certeza."""
    return [
        CausaDTO(
            causa=causa.causa,
            cf=causa.cf,
            descripcion=causa.descripcion,
            reglas=list(causa.reglas),
        )
        for causa in resultado.diagnostico
    ]


def semaforo_de(riesgo: RiesgoDifuso) -> str:
    """Traduce la etiqueta difusa a un color de semáforo para el dashboard."""
    etiqueta = riesgo.etiqueta.strip().lower()
    if etiqueta in RIESGO_SEMAFORO:
        return RIESGO_SEMAFORO[etiqueta]
    if riesgo.valor < 40:
        return "verde"
    if riesgo.valor < 70:
        return "amarillo"
    if riesgo.valor < 85:
        return "naranja"
    return "rojo"


def riesgo_de(resultado: ResultadoSistema) -> RiesgoDTO:
    """Proyecta el riesgo difuso y añade su semáforo."""
    riesgo = resultado.riesgo
    return RiesgoDTO(
        etiqueta=riesgo.etiqueta,
        valor=riesgo.valor,
        grado=riesgo.grado,
        urgencia=riesgo.urgencia,
        reglas_activadas=list(riesgo.reglas_activadas),
        descripcion=riesgo.descripcion,
        semaforo=semaforo_de(riesgo),
    )


def plan_de(resultado: ResultadoSistema) -> PlanDTO:
    """Proyecta el plan de acciones, su costo y sus restricciones."""
    plan = resultado.plan
    return PlanDTO(
        acciones=list(plan.acciones),
        descripcion=plan.descripcion,
        costo_bs=round(plan.costo_bs, 2),
        encontrado=plan.encontrado,
        nodos_expandidos=plan.nodos_expandidos,
        restricciones=list(plan.restricciones),
        justificacion=plan.justificacion,
        nodos_generados=plan.nodos_generados,
        profundidad=plan.profundidad,
        nodos=[
            NodoBusquedaDTO(
                id=nodo.id,
                padre_id=nodo.padre_id,
                estado=nodo.estado,
                accion=nodo.accion,
                profundidad=nodo.profundidad,
                costo_bs=nodo.costo_g,
                heuristica=nodo.heuristica_h,
                f=nodo.f,
                expandido=nodo.expandido,
                es_meta=nodo.es_meta,
                descartado=nodo.descartado,
                orden_expansion=nodo.orden_expansion,
            )
            for nodo in plan.nodos
        ],
    )


def comparativa_de(resultado: ResultadoSistema) -> ComparativaDTO:
    """Proyecta la comparativa simbólica versus no simbólica."""
    comparativa = resultado.comparativa
    return ComparativaDTO(
        aporte_ml=comparativa.no_simbólico,
        aporte_experto=comparativa.simbolico,
        complementariedad=comparativa.complementariedad,
        evidencia=comparativa.evidencia,
    )


def reglas_aplicadas_de(resultado: ResultadoSistema) -> list[ReglaAplicadaDTO]:
    """Proyecta la traza real y las reglas difusas activadas en esta ejecución."""
    crisp = [
        ReglaAplicadaDTO(
            orden=paso.orden,
            regla_id=paso.regla_id,
            descripcion=paso.descripcion,
            categoria=paso.categoria,
            premisa=paso.premisa,
            cf_premisa=round(paso.cf_premisa, 4),
            fc_regla=round(paso.fc_regla, 4),
            cf_conclusion=round(paso.cf_conclusion, 4),
            conclusion=paso.conclusion,
            conclusion_atributo=paso.conclusion_atributo,
            conclusion_valor=str(paso.conclusion_valor),
            momento=paso.momento,
            prioridad=paso.prioridad,
            tipo="experta",
        )
        for paso in resultado.reglas_aplicadas
    ]

    por_id = {regla.id: regla for regla in REGLAS_DIFUSAS}
    fuerzas = resultado.riesgo.fuerzas_reglas
    difusas: list[ReglaAplicadaDTO] = []
    for regla_id in resultado.riesgo.reglas_activadas:
        regla = por_id.get(regla_id)
        if regla is None:
            continue
        fuerza = round(fuerzas.get(regla_id, 0.0), 4)
        antecedentes = _pares_linguisticos(regla.si)
        consecuentes = _pares_linguisticos(regla.entonces)
        difusas.append(
            ReglaAplicadaDTO(
                orden=None,
                regla_id=regla.id,
                descripcion=regla.descripcion,
                categoria="difusa",
                premisa=" Y ".join(antecedentes),
                cf_premisa=fuerza,
                fc_regla=fuerza,
                cf_conclusion=fuerza,
                conclusion=" Y ".join(consecuentes),
                conclusion_atributo=", ".join(regla.entonces),
                conclusion_valor=", ".join(regla.entonces.values()),
                momento="",
                prioridad=None,
                tipo="difusa",
            )
        )
    return crisp + difusas


def _condiciones_atomicas(condicion: Condicion | GrupoCondiciones) -> list[str]:
    """Aplana un grupo de condiciones conservando las atómicas en orden."""
    if isinstance(condicion, GrupoCondiciones):
        return [texto for hija in condicion.condiciones for texto in _condiciones_atomicas(hija)]
    return [condicion.texto]


def _pares_linguisticos(mapeo: Mapping[str, str]) -> list[str]:
    """Convierte un mapping variable/etiqueta en pares legibles."""
    return [f"{variable} = {etiqueta}" for variable, etiqueta in mapeo.items()]


def _regla_sistema_de(regla: Regla) -> ReglaSistemaDTO:
    """Proyecta una regla crisp con todos sus campos declarativos."""
    return ReglaSistemaDTO(
        tipo="experta",
        id=regla.id,
        descripcion=regla.descripcion,
        categoria=regla.categoria,
        si=regla.condiciones.texto,
        entonces=regla.conclusion.texto,
        certeza=round(regla.fc, 4),
        prioridad=regla.prioridad,
        antecedentes=_condiciones_atomicas(regla.condiciones),
        consecuentes=[regla.conclusion.texto],
    )


def catalogo_reglas_de(
    base: BaseConocimientos,
    difusas: Sequence[ReglaDifusa] = REGLAS_DIFUSAS,
) -> RespuestaReglas:
    """Proyecta el catálogo completo sin ejecutar inferencia ni búsqueda."""
    expertas = [_regla_sistema_de(regla) for regla in base.reglas]
    reglas_difusas = [
        ReglaSistemaDTO(
            tipo="difusa",
            id=regla.id,
            descripcion=regla.descripcion,
            categoria="difusa",
            si=" Y ".join(_pares_linguisticos(regla.si)),
            entonces=" Y ".join(_pares_linguisticos(regla.entonces)),
            certeza=None,
            prioridad=None,
            antecedentes=_pares_linguisticos(regla.si),
            consecuentes=_pares_linguisticos(regla.entonces),
        )
        for regla in difusas
    ]
    todas = expertas + reglas_difusas
    return RespuestaReglas(
        total=len(todas),
        expertas=len(expertas),
        difusas=len(reglas_difusas),
        reglas=todas,
    )
