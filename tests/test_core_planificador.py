"""Pruebas de los operadores condicionados por el diagnóstico."""

from __future__ import annotations

from search.espacio_estados import ProblemaPlanComercial, TipoAccion
from search.informada import a_estrella
from search.no_informada import costo_uniforme


def test_problema_puede_deshabilitar_operadores() -> None:
    problema = ProblemaPlanComercial(
        meta_bs=24_000.0,
        presupuesto_bs=9_000.0,
        stock_inicial=400,
        merma_inicial=12.0,
        permitir_reasignacion=False,
        permitir_reducir_merma=False,
    )

    inicial = problema.estado_inicial()
    tipos = {accion.tipo for accion in problema.acciones(inicial)}

    assert TipoAccion.REASIGNAR_INVENTARIO not in tipos
    assert TipoAccion.REDUCIR_MERMA not in tipos
    assert TipoAccion.REPONER_STOCK in tipos
    assert TipoAccion.PROMOCION in tipos


def test_a_estrella_sigue_siendo_optimo_con_operadores_deshabilitados() -> None:
    problema = ProblemaPlanComercial(
        meta_bs=24_000.0,
        presupuesto_bs=9_000.0,
        stock_inicial=400,
        merma_inicial=12.0,
        permitir_reasignacion=False,
        permitir_reducir_merma=False,
    )

    informada = a_estrella(problema)
    referencia = costo_uniforme(problema)

    assert informada.encontrado == referencia.encontrado
    if informada.encontrado:
        assert informada.costo == referencia.costo
        assert all(
            accion.tipo not in {TipoAccion.REASIGNAR_INVENTARIO, TipoAccion.REDUCIR_MERMA}
            for accion in informada.plan
        )


def test_defaults_de_operadores_conservan_la_fase_5() -> None:
    problema = ProblemaPlanComercial(
        meta_bs=24_000.0,
        presupuesto_bs=9_000.0,
        stock_inicial=400,
        merma_inicial=12.0,
    )
    tipos = {accion.tipo for accion in problema.acciones(problema.estado_inicial())}

    assert TipoAccion.REASIGNAR_INVENTARIO in tipos
    assert TipoAccion.REDUCIR_MERMA in tipos
