"""Prueba estructural de los tres casos de la demostración de la Fase 6."""

from __future__ import annotations

from core.demo import CASOS


def test_demo_cubre_tres_escenarios_representativos() -> None:
    assert len(CASOS) == 3

    titulos = " ".join(str(caso["titulo"]).lower() for caso in CASOS)
    assert "riesgo" in titulos
    assert "normal" in titulos
    assert "exceso de stock" in titulos

    for caso in CASOS:
        assert caso["sucursal"] in {
            "Sopocachi",
            "El Alto",
            "Miraflores",
            "Calacoto",
            "Obrajes",
            "San Pedro",
        }
        assert caso["categoria"] in {"pollo", "cerdo", "embutidos", "congelados"}
        assert "factor_meta" in caso
        assert "stock_cobertura" in caso
