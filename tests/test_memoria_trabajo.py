"""Pruebas de la memoria de trabajo tipada y trazable."""

from __future__ import annotations

import pytest

from expert_system.memoria_trabajo import Hecho, MemoriaTrabajo


def test_hecho_valido() -> None:
    """Un hecho conserva atributo, valor, FC, origen y detalle."""
    hecho = Hecho("stock", 12.0, 0.8, "regla:D01", "premisa 0.9")
    assert hecho.atributo == "stock"
    assert hecho.valor == 12.0
    assert hecho.fc == 0.8
    assert hecho.origen == "regla:D01"
    assert "stock=12.0" in hecho.descripcion
    assert "paso 0" in hecho.descripcion
    assert hecho.momento


@pytest.mark.parametrize(
    ("atributo", "valor", "fc", "origen"),
    [
        ("", 1, 0.5, "usuario"),
        ("stock", 1, 1.2, "usuario"),
        ("stock", 1, 0.5, ""),
    ],
)
def test_hecho_invalido(atributo: str, valor: object, fc: float, origen: str) -> None:
    """Se rechazan atributos, FC y orígenes inválidos."""
    with pytest.raises(ValueError):
        Hecho(atributo, valor, fc, origen)


def test_hecho_valor_no_hashable_y_paso_invalido() -> None:
    """El valor debe ser hashable y el paso un entero no negativo."""
    with pytest.raises(TypeError):
        Hecho("stock", [1, 2], 0.5, "usuario")
    with pytest.raises(ValueError):
        Hecho("stock", 1, 0.5, "usuario", paso=-1)


def test_registrar_y_consultar() -> None:
    """La memoria asigna pasos y permite consultar por atributo o hipótesis."""
    memoria = MemoriaTrabajo()
    memoria.registrar(Hecho("causa", "stock", 0.6, "regla:D01", "por falta de stock"))
    combinado = memoria.actualizar("causa", "stock", 0.5, "regla:D02", "más evidencia")

    assert len(memoria) == 2
    assert combinado.fc == pytest.approx(0.8)
    assert combinado.paso == 1
    assert memoria.consultar("causa", "stock").fc == pytest.approx(0.8)  # type: ignore[union-attr]
    assert "regla:D01" in combinado.detalle
    assert "regla:D02" in combinado.detalle


def test_consultar_hipotesis_mas_cierta() -> None:
    """Sin valor explícito se devuelve la hipótesis de mayor certeza."""
    memoria = MemoriaTrabajo()
    memoria.actualizar("causa", "merma", 0.4, "regla:D03")
    memoria.actualizar("causa", "stock", 0.85, "regla:D01")
    assert memoria.consultar("causa").valor == "stock"
    assert memoria.consultar("causa", "merma").fc == 0.4


def test_consultar_inexistente_y_evidencias() -> None:
    """Las consultas sin evidencia devuelven None o tuplas vacías."""
    memoria = MemoriaTrabajo()
    assert memoria.consultar("causa") is None
    assert memoria.consultar("causa", "stock") is None
    assert memoria.evidencias("causa") == ()
    assert memoria.atributos() == ()
    assert not memoria.contiene("causa")
    memoria.actualizar("causa", "stock", 0.5, "usuario")
    assert memoria.contiene("causa", "stock")
    assert not memoria.contiene("causa", "merma")
    assert len(memoria.evidencias("causa", "stock")) == 1


def test_historial_ordenado_y_paso_explicito() -> None:
    """El historial respeta los pasos, incluso si se entregan explícitamente."""
    memoria = MemoriaTrabajo()
    memoria.registrar(Hecho("a", 1, 0.5, "usuario", paso=7))
    memoria.registrar(Hecho("b", 2, 0.5, "usuario"))
    assert [hecho.paso for hecho in memoria.historial()] == [7, 8]
    assert memoria.atributos() == ("a", "b")


def test_combinar_evidencia_con_signos_opuestos() -> None:
    """La combinación MYCIN se aplica también dentro de la memoria."""
    memoria = MemoriaTrabajo()
    memoria.actualizar("causa", "stock", 0.8, "regla:D01")
    memoria.actualizar("causa", "stock", -0.4, "regla:D99")
    assert memoria.consultar("causa", "stock").fc == pytest.approx(2 / 3)  # type: ignore[union-attr]


def test_valor_no_hashable_en_consulta() -> None:
    """Consultar con un valor no hashable se rechaza explícitamente."""
    with pytest.raises(TypeError):
        MemoriaTrabajo().consultar("causa", ["stock"])
