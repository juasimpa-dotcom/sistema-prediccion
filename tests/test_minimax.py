"""Pruebas del modelo de competencia con Minimax y poda alfa-beta."""

from __future__ import annotations

import pytest

from config import RESPUESTA_COMPETIDOR
from search.espacio_estados import ProblemaPlanComercial
from search.minimax import (
    FACTORES_RESPUESTA,
    JuegoCompetencia,
    RespuestaCompetidor,
    decidir,
)


@pytest.fixture
def problema() -> ProblemaPlanComercial:
    """Escenario medio para evaluar la decisión adversarial."""
    return ProblemaPlanComercial(
        meta_bs=24_000.0,
        presupuesto_bs=9_000.0,
        stock_inicial=400,
        merma_inicial=12.0,
    )


def test_factores_de_respuesta_vienen_de_config() -> None:
    """Cada estrategia rival usa el factor declarado en ``config.py``."""
    assert tuple(FACTORES_RESPUESTA.values()) == RESPUESTA_COMPETIDOR
    assert set(FACTORES_RESPUESTA) == set(RespuestaCompetidor)


def test_respuesta_del_competidor_degrada_ventas(problema: ProblemaPlanComercial) -> None:
    """El peor escenario reduce más las ventas que no hacer nada."""
    juego = JuegoCompetencia(problema)
    estado = problema.estado_inicial()
    neutro = juego.resultado_min(estado, RespuestaCompetidor.SIN_CAMBIO)
    promocion = juego.resultado_min(estado, RespuestaCompetidor.PROMOCION)
    bajada = juego.resultado_min(estado, RespuestaCompetidor.BAJADA_PRECIO)
    assert neutro.ventas_proyectadas == estado.ventas_proyectadas
    assert promocion.ventas_proyectadas < neutro.ventas_proyectadas
    assert bajada.ventas_proyectadas < promocion.ventas_proyectadas


def test_alfa_beta_coincide_con_minimax(problema: ProblemaPlanComercial) -> None:
    """La poda no cambia el valor óptimo y reduce nodos evaluados."""
    decision = decidir(problema, turnos=1)
    assert decision.coinciden
    assert decision.mejor_accion is not None
    assert decision.valor == pytest.approx(decision.valor_minimax)
    assert decision.nodos_alfa_beta < decision.nodos_minimax
    assert decision.podas > 0
    assert decision.turnos == 1


def test_alfa_beta_con_dos_turnos(problema: ProblemaPlanComercial) -> None:
    """La coincidencia se mantiene al profundizar el árbol de juego."""
    decision = decidir(problema, turnos=2)
    assert decision.coinciden
    assert decision.mejor_accion is not None
    assert decision.nodos_minimax > 0


def test_turnos_invalidos_se_rechazan(problema: ProblemaPlanComercial) -> None:
    """Se requiere al menos un turno."""
    with pytest.raises(ValueError):
        decidir(problema, turnos=0)
