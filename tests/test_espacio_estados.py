"""Pruebas del espacio de estados y del modelo comercial de la Fase 5."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import FrozenInstanceError, replace

import pytest

from search.espacio_estados import (
    Accion,
    EstadoPlan,
    Problema,
    ProblemaPlanComercial,
    TipoAccion,
)
from search.no_informada import costo_uniforme


class ProblemaDesde(Problema[EstadoPlan, Accion]):
    """Envuelve un problema para iniciar la búsqueda en un estado arbitrario."""

    def __init__(self, base: ProblemaPlanComercial, inicial: EstadoPlan) -> None:
        self.base = base
        self.inicial = inicial

    def estado_inicial(self) -> EstadoPlan:
        return self.inicial

    def es_meta(self, estado: EstadoPlan) -> bool:
        return self.base.es_meta(estado)

    def acciones(self, estado: EstadoPlan) -> tuple[Accion, ...]:
        return self.base.acciones(estado)

    def resultado(self, estado: EstadoPlan, accion: Accion) -> EstadoPlan:
        return self.base.resultado(estado, accion)

    def costo_paso(self, estado: EstadoPlan, accion: Accion) -> float:
        return self.base.costo_paso(estado, accion)

    @property
    def descripcion(self) -> str:
        return self.base.descripcion


@pytest.fixture
def problema() -> ProblemaPlanComercial:
    """Escenario pequeño y rápido para probar el modelo."""
    return ProblemaPlanComercial(
        meta_bs=12_000.0,
        presupuesto_bs=6_000.0,
        stock_inicial=400,
        merma_inicial=12.0,
    )


def estados_alcanzables(problema: ProblemaPlanComercial, profundidad_max: int) -> list[EstadoPlan]:
    """Devuelve estados únicos hasta ``profundidad_max`` pasos desde el inicial."""
    inicial = problema.estado_inicial()
    frontera = deque([(inicial, 0)])
    vistos: set[EstadoPlan] = {inicial}
    while frontera:
        estado, profundidad = frontera.popleft()
        if profundidad >= profundidad_max:
            continue
        for accion in problema.acciones(estado):
            sucesor = problema.resultado(estado, accion)
            if sucesor in vistos:
                continue
            vistos.add(sucesor)
            frontera.append((sucesor, profundidad + 1))
    return list(vistos)


def test_problema_es_abstracto() -> None:
    """No se puede instanciar el contrato sin implementar sus métodos."""
    with pytest.raises(TypeError):
        Problema()  # type: ignore[abstract]


def test_estado_es_inmutable_y_hashable() -> None:
    """El estado es ``frozen`` y utilizable como clave de conjuntos."""
    estado = EstadoPlan(400, 10.0, 4, 12.0, 8_000.0, 5_000.0)
    assert {estado, replace(estado)} == {estado}
    with pytest.raises(FrozenInstanceError):
        estado.stock = 500  # type: ignore[misc]


def test_accion_es_inmutable_y_descriptiva() -> None:
    """Las acciones son hashables y se imprimen con su parámetro."""
    accion = Accion(TipoAccion.PROMOCION, 20.0)
    assert hash(accion) == hash(Accion(TipoAccion.PROMOCION, 20.0))
    assert str(accion) == "promocion(20%)"


@pytest.mark.parametrize(
    ("cambios", "excepcion"),
    [
        ({"sucursal": "Desconocida"}, ValueError),
        ({"categoria": "desconocida"}, ValueError),
        ({"meta_bs": 0}, ValueError),
        ({"presupuesto_bs": -1}, ValueError),
        ({"stock_inicial": -5}, ValueError),
        ({"stock_inicial": 2_000}, ValueError),
        ({"merma_inicial": 99}, ValueError),
        ({"niveles_promocion": (10.0, 0.0)}, ValueError),
        ({"niveles_promocion": (0.0, 10.0, 10.0)}, ValueError),
        ({"niveles_promocion": (0.0, 100.0)}, ValueError),
    ],
)
def test_validaciones_de_entrada(cambios: dict, excepcion: type[Exception]) -> None:
    """Los parámetros inválidos se rechazan tempranamente."""
    with pytest.raises(excepcion):
        ProblemaPlanComercial(**cambios)


def test_parametros_deben_ser_la_estructura_configurada() -> None:
    """El objeto de elasticidades no puede sustituirse por un dict arbitrario."""
    with pytest.raises(TypeError):
        ProblemaPlanComercial(parametros={"elasticidad_promocion": 1.0})


def test_proyeccion_respeta_el_modelo_de_la_fase_1() -> None:
    """Con stock suficiente, cada palanca mueve las ventas en la dirección esperada."""
    problema = ProblemaPlanComercial(
        meta_bs=12_000.0,
        presupuesto_bs=6_000.0,
        stock_inicial=2_000,
        stock_maximo=2_400,
        merma_inicial=12.0,
    )
    base = problema.estado_inicial()
    mas_personal = replace(base, personal=base.personal + 2)
    menos_merma = replace(base, merma_pct=base.merma_pct - 4.0)
    promo = replace(base, descuento_pct=20.0)

    assert problema.proyectar(mas_personal) > problema.proyectar(base)
    assert problema.proyectar(menos_merma) > problema.proyectar(base)
    # Más tráfico y conversión compensan el menor precio si hay stock para atenderlos.
    assert problema.proyectar(promo) > problema.proyectar(base)


def test_stock_limita_las_ventas() -> None:
    """Con poco stock, reponer aumenta las ventas proyectadas."""
    problema = ProblemaPlanComercial(
        meta_bs=12_000.0,
        presupuesto_bs=6_000.0,
        stock_inicial=100,
        merma_inicial=12.0,
    )
    base = problema.estado_inicial()
    assert problema.proyectar(replace(base, stock=200)) > problema.proyectar(base)


def test_acciones_respetan_presupuesto(problema: ProblemaPlanComercial) -> None:
    """Solo se ofrecen operadores cuyo costo cabe en el presupuesto restante."""
    caro = replace(problema.estado_inicial(), presupuesto_restante=300.0)
    nombres = {accion.tipo for accion in problema.acciones(caro)}
    assert TipoAccion.REDUCIR_MERMA in nombres
    assert TipoAccion.REFORZAR_PERSONAL in nombres
    assert TipoAccion.PROMOCION not in nombres
    assert TipoAccion.REPONER_STOCK not in nombres


def test_resultado_aplica_cada_operador(problema: ProblemaPlanComercial) -> None:
    """El sucesor recalcula ventas y descuenta exactamente el costo."""
    estado = problema.estado_inicial()
    for accion in problema.acciones(estado):
        sucesor = problema.resultado(estado, accion)
        costo = problema.costo_paso(estado, accion)
        assert sucesor.ventas_proyectadas == pytest.approx(problema.proyectar(sucesor))
        assert sucesor.presupuesto_restante == pytest.approx(estado.presupuesto_restante - costo)
        if accion.tipo == TipoAccion.PROMOCION:
            assert sucesor.descuento_pct == accion.nivel
        elif accion.tipo in {TipoAccion.REPONER_STOCK, TipoAccion.REASIGNAR_INVENTARIO}:
            assert sucesor.stock > estado.stock
        elif accion.tipo == TipoAccion.REFORZAR_PERSONAL:
            assert sucesor.personal == estado.personal + 1
        else:
            assert sucesor.merma_pct < estado.merma_pct


def test_resultado_rechaza_acciones_no_aplicables(problema: ProblemaPlanComercial) -> None:
    """No se pueden aplicar acciones agotadas ni tipos desconocidos."""
    estado = problema.estado_inicial()
    with pytest.raises(TypeError):
        problema.resultado(estado, "promocion")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        problema.resultado(estado, Accion(TipoAccion.PROMOCION, 15.0))
    with pytest.raises(ValueError):
        problema.costo_paso(estado, Accion("inventado"))  # type: ignore[arg-type]


def test_heuristica_en_meta_y_sin_presupuesto(problema: ProblemaPlanComercial) -> None:
    """La meta cuesta cero y un estado sin fondos no puede progresar."""
    estado = problema.estado_inicial()
    en_meta = replace(estado, ventas_proyectadas=problema.meta_bs)
    sin_fondos = replace(estado, presupuesto_restante=0.0)
    assert problema.heuristica(en_meta) == 0.0
    assert math.isinf(problema.heuristica(sin_fondos))


def test_heuristica_admisible_y_consistente(problema: ProblemaPlanComercial) -> None:
    """``h`` nunca sobreestima el costo real y satisface la desigualdad de consenso.

    Se enumeran los estados alcanzables hasta profundidad 2. Para cada uno se
    compara ``h`` con el costo óptimo calculado por costo uniforme desde ese
    estado (admisibilidad) y con ``c + h(s')`` para cada sucesor (consistencia).
    """
    estados = estados_alcanzables(problema, profundidad_max=2)
    assert len(estados) > 10

    for estado in estados:
        if problema.es_meta(estado):
            assert problema.heuristica(estado) == 0.0
            continue
        optimo = costo_uniforme(ProblemaDesde(problema, estado))
        assert optimo.encontrado
        assert problema.heuristica(estado) <= optimo.costo + 1e-6
        for accion in problema.acciones(estado):
            sucesor = problema.resultado(estado, accion)
            esperado = problema.costo_paso(estado, accion) + problema.heuristica(sucesor)
            assert problema.heuristica(estado) <= esperado + 1e-6
