"""Pruebas de integración extremo a extremo de la Fase 6."""

from __future__ import annotations

import pandas as pd

from config import (
    ATRIBUTO_CONFIANZA_ML,
    ATRIBUTO_PREDICCION_BS,
    UMBRAL_EXCESO_STOCK,
)
from core.contexto import contexto_desde_dataframe
from core.fabrica import construir_sistema


def test_flujo_completo_sucursal_en_riesgo(crudo: pd.DataFrame) -> None:
    sistema = construir_sistema()
    contexto = contexto_desde_dataframe(
        crudo,
        "El Alto",
        "pollo",
        factor_meta=1.20,
        stock_cobertura=0.18,
        afluencia_rel=0.70,
        precio_vs_competencia=1.12,
        merma_inicial=14.5,
        hay_excedente_en_otra_sucursal=True,
        reabastecimiento_tardia=True,
    )

    resultado = sistema.ejecutar(contexto)

    assert resultado.sucursal == "El Alto"
    assert resultado.categoria == "pollo"
    assert resultado.prediccion.valor_predicho > 0
    assert 0.0 < resultado.confianza <= 1.0
    assert resultado.cumplimiento_pct > 0
    assert resultado.diagnostico
    assert all(-1.0 <= causa.cf <= 1.0 for causa in resultado.diagnostico)
    assert resultado.riesgo.etiqueta in {"bajo", "medio", "alto", "crítico"}
    assert resultado.riesgo.reglas_activadas
    assert resultado.plan.encontrado
    assert resultado.plan.acciones
    assert resultado.plan.costo_bs > 0
    assert resultado.reglas_disparadas
    assert "SHAP" in resultado.explicacion
    assert "Reglas disparadas" in resultado.explicacion
    assert "COMPARATIVA" in resultado.explicacion

    assert sistema.memoria.consultar(ATRIBUTO_PREDICCION_BS).fc == resultado.confianza
    assert sistema.memoria.consultar(ATRIBUTO_CONFIANZA_ML).fc == resultado.confianza
    riesgo_memoria = sistema.memoria.consultar("nivel_riesgo_difuso")
    assert riesgo_memoria is not None
    assert riesgo_memoria.valor == resultado.riesgo.etiqueta


def test_flujo_completo_sucursal_normal(crudo: pd.DataFrame) -> None:
    sistema = construir_sistema(incluir_explicacion=False)
    contexto = contexto_desde_dataframe(
        crudo,
        "Sopocachi",
        "cerdo",
        factor_meta=0.85,
        stock_cobertura=0.80,
        afluencia_rel=1.05,
        merma_inicial=4.0,
        es_perecible=False,
    )

    resultado = sistema.ejecutar(contexto)

    assert not resultado.diagnostico
    assert resultado.riesgo.etiqueta == "bajo"
    assert resultado.plan.encontrado
    assert resultado.plan.acciones == ()
    assert resultado.plan.costo_bs == 0.0
    assert "mantener_plan" in " ".join(resultado.reglas_disparadas + resultado.plan.acciones) or (
        "mantener_plan" in resultado.explicacion
    )


def test_flujo_completo_exceso_stock_restringe_operadores(crudo: pd.DataFrame) -> None:
    sistema = construir_sistema(incluir_explicacion=False)
    contexto = contexto_desde_dataframe(
        crudo,
        "Miraflores",
        "embutidos",
        factor_meta=1.05,
        stock_cobertura=UMBRAL_EXCESO_STOCK + 0.35,
        afluencia_rel=0.95,
        merma_inicial=6.0,
    )

    resultado = sistema.ejecutar(contexto)

    assert any(causa.causa == "exceso_stock" for causa in resultado.diagnostico)
    assert "permitir_reasignacion" in resultado.plan.restricciones
    assert "permitir_reducir_merma" not in resultado.plan.restricciones
    assert "reasignar_inventario" not in resultado.plan.descripcion
    assert "Riesgo difuso" in resultado.explicacion


def test_resultado_incluye_comparativa_documentada(crudo: pd.DataFrame) -> None:
    sistema = construir_sistema(incluir_explicacion=False)
    contexto = contexto_desde_dataframe(crudo, "El Alto", "pollo", factor_meta=1.20)

    resultado = sistema.ejecutar(contexto)
    texto = resultado.comparativa.a_texto()

    for fragmento in ("No simbólico", "Simbólico", "Complementariedad", "Evidencia"):
        assert fragmento in texto
    assert "MYCIN" in texto
    assert "difusa" in texto
    assert "A*" in texto
