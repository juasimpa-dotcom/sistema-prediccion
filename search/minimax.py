"""Decisión adversarial simple: el competidor responde a nuestra promoción.

Modelo de dos turnos por ronda: elegimos un operador comercial (nodo MAX) y el
competidor responde con «no hacer nada», «lanzar su propia promoción» o «bajar
precios» (nodo MIN). La utilidad es ``ventas_proyectadas - inversión``; el
competidor degrada las ventas con los factores declarados en ``config.py``.

Se calcula el valor con Minimax puro y con poda alfa-beta. Ambos deben coincidir;
la diferencia de nodos evaluados mide la utilidad de la poda.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import StrEnum

from config import RESPUESTA_COMPETIDOR
from search.espacio_estados import Accion, EstadoPlan, ProblemaPlanComercial


class RespuestaCompetidor(StrEnum):
    """Estrategias disponibles para el competidor."""

    SIN_CAMBIO = "sin_cambio"
    PROMOCION = "promocion"
    BAJADA_PRECIO = "bajada_precio"


FACTORES_RESPUESTA: dict[RespuestaCompetidor, float] = {
    RespuestaCompetidor.SIN_CAMBIO: RESPUESTA_COMPETIDOR[0],
    RespuestaCompetidor.PROMOCION: RESPUESTA_COMPETIDOR[1],
    RespuestaCompetidor.BAJADA_PRECIO: RESPUESTA_COMPETIDOR[2],
}


@dataclass
class Contador:
    """Contadores de trabajo de la poda alfa-beta."""

    nodos: int = 0
    podas: int = 0


@dataclass(frozen=True, slots=True)
class ResultadoMinimax:
    """Decisión robusta y comparación entre Minimax y alfa-beta.

    Attributes:
        mejor_accion: Operador que maximiza la utilidad en el peor escenario.
        valor: Utilidad garantizada por la decisión con alfa-beta.
        valor_minimax: Utilidad calculada sin poda; sirve de verificación.
        nodos_minimax: Hojas y nodos internos evaluados sin poda.
        nodos_alfa_beta: Nodos evaluados con poda.
        podas: Ramas cortadas por los límites alfa/beta.
        turnos: Rondas completas nuestro turno + respuesta del competidor.
    """

    mejor_accion: Accion | None
    valor: float
    valor_minimax: float
    nodos_minimax: int
    nodos_alfa_beta: int
    podas: int
    turnos: int

    @property
    def coinciden(self) -> bool:
        """Indica si la poda preservó el valor de Minimax."""
        return math.isclose(self.valor, self.valor_minimax, rel_tol=0.0, abs_tol=1e-6)


class JuegoCompetencia:
    """Adaptador que convierte el problema comercial en un juego por turnos."""

    def __init__(self, problema: ProblemaPlanComercial) -> None:
        """Guarda el problema comercial subyacente.

        Args:
            problema: Instancia del espacio de estados de la Fase 5.
        """
        self.problema = problema

    def acciones_max(self, estado: EstadoPlan) -> tuple[Accion, ...]:
        """Devuelve nuestros operadores disponibles."""
        return self.problema.acciones(estado)

    def resultado_max(self, estado: EstadoPlan, accion: Accion) -> EstadoPlan:
        """Aplica nuestro operador usando el modelo comercial."""
        return self.problema.resultado(estado, accion)

    def acciones_min(self, estado: EstadoPlan) -> tuple[RespuestaCompetidor, ...]:
        """Devuelve las respuestas posibles del competidor."""
        del estado
        return tuple(RespuestaCompetidor)

    def resultado_min(self, estado: EstadoPlan, respuesta: RespuestaCompetidor) -> EstadoPlan:
        """Degrada las ventas según la respuesta del competidor."""
        factor = FACTORES_RESPUESTA[respuesta]
        return replace(estado, ventas_proyectadas=round(estado.ventas_proyectadas * factor, 2))

    def utilidad(self, estado: EstadoPlan, inversion: float) -> float:
        """Valora la situación desde nuestro punto de vista."""
        return round(estado.ventas_proyectadas - inversion, 2)

    def terminal(self, estado: EstadoPlan, profundidad: int, maximizando: bool) -> bool:
        """Indica si la rama termina por profundidad o falta de operadores."""
        return profundidad == 0 or (maximizando and not self.acciones_max(estado))


def _minimax(
    juego: JuegoCompetencia,
    estado: EstadoPlan,
    profundidad: int,
    inversion: float,
    maximizando: bool,
) -> tuple[float, int]:
    """Evalúa el árbol completo sin poda."""
    if juego.terminal(estado, profundidad, maximizando):
        return juego.utilidad(estado, inversion), 1

    nodos = 1
    if maximizando:
        mejor = -math.inf
        for accion in juego.acciones_max(estado):
            sucesor = juego.resultado_max(estado, accion)
            valor, evaluados = _minimax(
                juego,
                sucesor,
                profundidad - 1,
                inversion + juego.problema.costo_paso(estado, accion),
                False,
            )
            mejor = max(mejor, valor)
            nodos += evaluados
        return mejor, nodos

    mejor = math.inf
    for respuesta in juego.acciones_min(estado):
        sucesor = juego.resultado_min(estado, respuesta)
        valor, evaluados = _minimax(juego, sucesor, profundidad - 1, inversion, True)
        mejor = min(mejor, valor)
        nodos += evaluados
    return mejor, nodos


def _alfa_beta(
    juego: JuegoCompetencia,
    estado: EstadoPlan,
    profundidad: int,
    inversion: float,
    maximizando: bool,
    alfa: float,
    beta: float,
    contador: Contador,
) -> float:
    """Evalúa el árbol con poda alfa-beta."""
    contador.nodos += 1
    if juego.terminal(estado, profundidad, maximizando):
        return juego.utilidad(estado, inversion)

    if maximizando:
        mejor = -math.inf
        for accion in juego.acciones_max(estado):
            sucesor = juego.resultado_max(estado, accion)
            valor = _alfa_beta(
                juego,
                sucesor,
                profundidad - 1,
                inversion + juego.problema.costo_paso(estado, accion),
                False,
                alfa,
                beta,
                contador,
            )
            mejor = max(mejor, valor)
            alfa = max(alfa, mejor)
            if beta <= alfa:
                contador.podas += 1
                break
        return mejor

    mejor = math.inf
    for respuesta in juego.acciones_min(estado):
        sucesor = juego.resultado_min(estado, respuesta)
        valor = _alfa_beta(juego, sucesor, profundidad - 1, inversion, True, alfa, beta, contador)
        mejor = min(mejor, valor)
        beta = min(beta, mejor)
        if beta <= alfa:
            contador.podas += 1
            break
    return mejor


def decidir(
    problema: ProblemaPlanComercial,
    turnos: int = 1,
) -> ResultadoMinimax:
    """Elige el operador robusto ante la respuesta del competidor.

    Args:
        problema: Escenario comercial.
        turnos: Rondas completas (nuestro turno y respuesta rival).

    Returns:
        Decisión con utilidad verificada contra Minimax sin poda.

    Raises:
        ValueError: Si ``turnos`` no es positivo.
    """
    if turnos < 1:
        raise ValueError("Debe jugarse al menos un turno")
    juego = JuegoCompetencia(problema)
    estado = problema.estado_inicial()
    profundidad = 2 * turnos
    valor_minimax, nodos_minimax = _minimax(juego, estado, profundidad, 0.0, True)

    contador = Contador()
    alfa = -math.inf
    mejor_accion: Accion | None = None
    for accion in juego.acciones_max(estado):
        sucesor = juego.resultado_max(estado, accion)
        valor = _alfa_beta(
            juego,
            sucesor,
            profundidad - 1,
            juego.problema.costo_paso(estado, accion),
            False,
            alfa,
            math.inf,
            contador,
        )
        if mejor_accion is None or valor > alfa:
            mejor_accion = accion
            alfa = valor

    return ResultadoMinimax(
        mejor_accion=mejor_accion,
        valor=round(alfa, 2),
        valor_minimax=round(valor_minimax, 2),
        nodos_minimax=nodos_minimax,
        nodos_alfa_beta=contador.nodos,
        podas=contador.podas,
        turnos=turnos,
    )
