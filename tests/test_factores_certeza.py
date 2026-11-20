"""Pruebas de la aritmética de factores de certeza estilo MYCIN."""

from __future__ import annotations

import pytest

from expert_system.factores_certeza import (
    cf_conjuncion,
    cf_disjuncion,
    combinar_fc,
    propagar_fc,
    supera_umbral,
    validar_fc,
)


def test_validar_fc() -> None:
    """Los factores válidos se normalizan a float."""
    assert validar_fc(1) == 1.0
    assert validar_fc(-0.5, "fc") == -0.5


@pytest.mark.parametrize("valor", [1.1, -1.01])
def test_validar_fc_fuera_de_rango(valor: float) -> None:
    """Se rechazan factores fuera de [-1, 1]."""
    with pytest.raises(ValueError, match="\\[-1, 1\\]"):
        validar_fc(valor)


@pytest.mark.parametrize("valor", ["0.5", None, True])
def test_validar_fc_tipo_invalido(valor: object) -> None:
    """Se rechazan booleanos y valores no numéricos."""
    with pytest.raises(TypeError):
        validar_fc(valor)


def test_combinar_positivos() -> None:
    """Dos evidencias positivas se combinan con la fórmula de MYCIN."""
    assert combinar_fc(0.6, 0.6) == pytest.approx(0.84)
    assert combinar_fc(0.3, 0.5, 0.2) == pytest.approx(0.72)
    assert combinar_fc(0.8, 0.0) == pytest.approx(0.8)
    assert combinar_fc() == 0.0


def test_combinar_negativos() -> None:
    """Dos evidencias negativas refuerzan la certeza en contra."""
    assert combinar_fc(-0.6, -0.6) == pytest.approx(-0.84)
    assert combinar_fc(-0.3, -0.5) == pytest.approx(-0.65)


def test_combinar_mixtos() -> None:
    """Evidencias de signos opuestos se atenúan según MYCIN."""
    assert combinar_fc(0.6, -0.6) == pytest.approx(0.0)
    assert combinar_fc(0.8, -0.4) == pytest.approx(2 / 3)
    assert combinar_fc(-0.8, 0.4) == pytest.approx(-2 / 3)
    assert combinar_fc(1.0, -1.0) == 0.0


def test_combinar_es_conmutativa_y_acotada() -> None:
    """El orden no altera el resultado y nunca se sale de [-1, 1]."""
    assert combinar_fc(0.4, -0.7, 0.5) == pytest.approx(combinar_fc(0.5, 0.4, -0.7))
    assert -1.0 <= combinar_fc(0.99, 0.99, 0.99) <= 1.0


def test_combinar_valida_argumentos() -> None:
    """Los factores inválidos se detectan también al combinar."""
    with pytest.raises(TypeError):
        combinar_fc(0.5, "alto")
    with pytest.raises(ValueError):
        combinar_fc(0.5, 2.0)


def test_conjuncion_y_disjuncion() -> None:
    """AND usa el mínimo y OR el máximo; listas vacías dan cero."""
    assert cf_conjuncion([0.9, 0.4, 0.7]) == 0.4
    assert cf_disjuncion([-0.2, 0.4, 0.7]) == 0.7
    assert cf_conjuncion([]) == 0.0
    assert cf_disjuncion([]) == 0.0
    with pytest.raises(ValueError):
        cf_conjuncion([0.5, 1.5])


def test_propagar_y_umbral() -> None:
    """La propagación es el producto y el umbral filtra certezas positivas."""
    assert propagar_fc(0.9, 0.8) == pytest.approx(0.72)
    assert propagar_fc(-0.5, 0.4) == pytest.approx(-0.2)
    assert supera_umbral(0.3, 0.2)
    assert not supera_umbral(0.1, 0.2)
    assert not supera_umbral(-0.9, 0.2)
    with pytest.raises(ValueError):
        propagar_fc(0.5, 3.0)
