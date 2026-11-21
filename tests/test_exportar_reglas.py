"""Pruebas del exportador de reglas reales a Markdown."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from config import ARCHIVO_REGLAS_EXPERTO, REGLAS_DIFUSAS
from expert_system.base_conocimientos import BaseConocimientos
from expert_system.exportar_reglas import generar_documento

RAIZ = Path(__file__).resolve().parents[1]


def test_exportar_reglas_se_ejecuta_como_modulo(tmp_path: Path) -> None:
    salida = tmp_path / "reglas.md"
    resultado = subprocess.run(
        [
            sys.executable,
            "-m",
            "expert_system.exportar_reglas",
            "--salida",
            str(salida),
        ],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        check=False,
    )

    assert resultado.returncode == 0, resultado.stderr
    assert salida.is_file()
    assert "Documento generado" in resultado.stdout


def test_documento_incluye_todas_las_reglas_de_la_base(tmp_path: Path) -> None:
    salida = tmp_path / "reglas.md"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "expert_system.exportar_reglas",
            "--salida",
            str(salida),
        ],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        check=True,
    )
    texto = salida.read_text(encoding="utf-8")
    base = BaseConocimientos.desde_json(ARCHIVO_REGLAS_EXPERTO)

    esperadas = {regla.id for regla in base.reglas}
    exportadas = {regla.id for regla in base.reglas if f"| {regla.id} |" in texto}

    assert len(exportadas) == len(base.reglas)
    assert exportadas == esperadas

    difusas_esperadas = {regla.id for regla in REGLAS_DIFUSAS}
    difusas_exportadas = {regla.id for regla in REGLAS_DIFUSAS if f"| {regla.id} |" in texto}
    assert difusas_exportadas == difusas_esperadas


def test_resumen_coincide_con_fuentes_reales() -> None:
    base = BaseConocimientos.desde_json(ARCHIVO_REGLAS_EXPERTO)
    documento = generar_documento(base)

    total = len(base.reglas) + len(REGLAS_DIFUSAS)
    assert f"| **Total exportado** | **{total}** |" in documento
    for categoria in base.categorias():
        cantidad = sum(1 for regla in base.reglas if regla.categoria == categoria)
        assert f"| {categoria} | {cantidad} |" in documento
    assert f"| Reglas difusas (`config.py`) | {len(REGLAS_DIFUSAS)} |" in documento
