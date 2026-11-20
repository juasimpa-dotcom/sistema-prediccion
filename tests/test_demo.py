"""Pruebas del script de demostración del sistema experto."""

from __future__ import annotations

import pytest

from expert_system import demo


def test_caso_inicial() -> None:
    """El caso de demostración genera hechos con certeza plena."""
    memoria = demo.hechos_del_caso()
    assert memoria.contiene("stock_cobertura")
    assert memoria.consultar("es_perecible").valor is True
    assert len(memoria) == len(demo.DATOS_CASO)


def test_demo_imprime_caso_y_explicaciones(capsys: pytest.CaptureFixture[str]) -> None:
    """La demo imprime traza, conclusión, explicación y preguntas."""
    demo.main()
    salida = capsys.readouterr().out
    assert "30 reglas" in salida
    assert "Traza de inferencia" in salida
    assert "Hechos derivados" in salida
    assert "¿POR QUÉ?" in salida
    assert "¿CÓMO?" in salida
    assert "Encadenamiento hacia atrás" in salida
    assert "reponer_stock_urgente" in salida
    assert "en_promocion" in salida
