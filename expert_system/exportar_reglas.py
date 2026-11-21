"""Exporta a Markdown las reglas reales del sistema.

Uso desde la raíz del repositorio:

.. code-block:: powershell

    python -m expert_system.exportar_reglas
    python -m expert_system.exportar_reglas --salida docs/reglas.md

Las reglas expertas se leen de ``expert_system/reglas.json``, las difusas de
``config.REGLAS_DIFUSAS`` y la traza de ejemplo se ejecuta con el caso de
``expert_system.demo``. El script solo presenta datos declarativos: no define
reglas nuevas ni modifica la lógica del motor.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from config import ARCHIVO_REGLAS_EXPERTO, DIR_DOCS, REGLAS_DIFUSAS, ReglaDifusa
from expert_system.base_conocimientos import BaseConocimientos, Regla
from expert_system.demo import DATOS_CASO, hechos_del_caso
from expert_system.motor_inferencia import MotorInferencia, TrazaInferencia

ARCHIVO_SALIDA: Path = DIR_DOCS / "reglas.md"
CATEGORIAS_PRINCIPALES: tuple[str, ...] = ("diagnostico", "riesgo", "recomendacion")
ATRIBUTOS_DESTACADOS: tuple[str, ...] = (
    "causa_ventas_bajas",
    "nivel_riesgo",
    "accion_recomendada",
)


def _valor_texto(valor: object) -> str:
    """Devuelve un valor python en formato legible para el documento."""
    if isinstance(valor, bool):
        return "sí" if valor else "no"
    if isinstance(valor, (list, tuple)):
        return "[" + ", ".join(_valor_texto(item) for item in valor) + "]"
    return str(valor)


def _md(texto: object) -> str:
    """Escapa celdas Markdown para que las reglas no rompan las tablas."""
    return _valor_texto(texto).replace("|", "\\|").replace("\n", "<br>")


def _fc(valor: float) -> str:
    """Formatea un factor de certeza con signo y dos decimales."""
    return f"{valor:+.2f}"


def _tabla(cabeceras: tuple[str, ...], filas: Iterable[tuple[object, ...]]) -> list[str]:
    """Construye una tabla Markdown con las celdas escapadas."""
    lineas = [
        "| " + " | ".join(cabeceras) + " |",
        "| " + " | ".join("---" for _ in cabeceras) + " |",
    ]
    lineas.extend("| " + " | ".join(_md(celda) for celda in fila) + " |" for fila in filas)
    return lineas


def _pares_linguisticos(mapeo: Mapping[str, str]) -> str:
    """Junta pares variable/etiqueta en una frase legible."""
    return " Y ".join(f"{variable} = {etiqueta}" for variable, etiqueta in mapeo.items())


def _tabla_reglas(
    reglas: Iterable[Regla],
    cabecera_categoria: str = "Categoría",
) -> list[str]:
    """Tabla de reglas expertas con sus campos declarativos reales."""
    return _tabla(
        (
            "ID",
            cabecera_categoria,
            "SI (condiciones)",
            "ENTONCES (conclusión)",
            "CF de la regla",
            "Prioridad",
        ),
        (
            (
                regla.id,
                regla.categoria,
                regla.condiciones.texto,
                regla.conclusion.texto,
                _fc(regla.fc),
                regla.prioridad,
            )
            for regla in reglas
        ),
    )


def _tabla_difusas(reglas: Iterable[ReglaDifusa]) -> list[str]:
    """Tabla de reglas difusas con antecedentes y consecuentes reales."""
    return _tabla(
        ("ID", "Antecedentes lingüísticos", "Consecuente"),
        (
            (regla.id, _pares_linguisticos(regla.si), _pares_linguisticos(regla.entonces))
            for regla in reglas
        ),
    )


def _seccion_reglas(base: BaseConocimientos) -> list[str]:
    """Escribe las tablas de reglas expertas y difusas."""
    principales = [regla for regla in base.reglas if regla.categoria in CATEGORIAS_PRINCIPALES]
    puente = [regla for regla in base.reglas if regla.categoria not in CATEGORIAS_PRINCIPALES]
    lineas = [
        "## 1. Tablas de reglas",
        "",
        "### 1.1 Reglas experto (diagnóstico, riesgo y recomendación)",
        "",
        *_tabla_reglas(
            principales,
            "Categoría (diagnóstico / riesgo / recomendación)",
        ),
    ]
    if puente:
        lineas.extend(
            [
                "",
                "### 1.2 Reglas puente difuso a simbólico",
                "",
                "Estas reglas también viven en la base de conocimientos y traducen los",
                "hechos graduales del motor difuso al razonamiento simbólico.",
                "",
                *_tabla_reglas(puente),
            ]
        )
    lineas.extend(
        [
            "",
            "### 1.3 Reglas difusas (Mamdani)",
            "",
            *_tabla_difusas(REGLAS_DIFUSAS),
        ]
    )
    return lineas


def _seccion_lenguaje_natural(base: BaseConocimientos) -> list[str]:
    """Escribe todas las reglas en lenguaje natural usando sus descripciones."""
    lineas = ["## 2. Reglas en lenguaje natural", "", "### 2.1 Reglas experto", ""]
    for regla in base.reglas:
        lineas.append(
            f"- **{regla.id} · {regla.categoria}.** {regla.descripcion} "
            f"_Formulación:_ `{regla.texto}` (prioridad {regla.prioridad})."
        )
    lineas.extend(["", "### 2.2 Reglas difusas", ""])
    for regla in REGLAS_DIFUSAS:
        lineas.append(
            f"- **{regla.id}.** {regla.descripcion} "
            f"SI {_pares_linguisticos(regla.si)}; ENTONCES "
            f"{_pares_linguisticos(regla.entonces)}."
        )
    return lineas


def _seccion_resumen(base: BaseConocimientos) -> list[str]:
    """Resume cuántas reglas reales hay por categoría."""
    conteo = Counter(regla.categoria for regla in base.reglas)
    filas: list[tuple[object, ...]] = [
        (categoria, conteo[categoria]) for categoria in base.categorias()
    ]
    filas.append(("Reglas difusas (`config.py`)", len(REGLAS_DIFUSAS)))
    filas.append(("**Total exportado**", f"**{len(base.reglas) + len(REGLAS_DIFUSAS)}**"))
    return [
        "## 3. Resumen de reglas",
        "",
        *_tabla(("Categoría", "Cantidad"), filas),
    ]


def _datos_del_caso() -> list[str]:
    """Tabla con los hechos observados del caso de demostración."""
    return _tabla(
        ("Hecho observado", "Valor"),
        ((atributo, valor) for atributo, valor in DATOS_CASO.items()),
    )


def _tabla_traza(traza: TrazaInferencia) -> list[str]:
    """Tabla con los disparos reales y sus tres factores de certeza."""
    return _tabla(
        (
            "Orden",
            "Regla",
            "Categoría",
            "Premisa",
            "CF premisa",
            "FC regla",
            "CF conclusión",
            "Conclusión",
        ),
        (
            (
                paso.orden,
                paso.regla_id,
                paso.categoria,
                paso.premisa,
                _fc(paso.cf_premisa),
                _fc(paso.fc_regla),
                _fc(paso.cf_conclusion),
                paso.conclusion,
            )
            for paso in traza.pasos
        ),
    )


def _seccion_traza(base: BaseConocimientos) -> list[str]:
    """Ejecuta el caso real y documenta su traza y certezas acumuladas."""
    memoria = hechos_del_caso()
    motor = MotorInferencia(base, memoria)
    traza = motor.encadenar_adelante()

    filas_finales: list[tuple[object, ...]] = []
    for atributo in ATRIBUTOS_DESTACADOS:
        hecho = memoria.consultar(atributo)
        if hecho is not None:
            filas_finales.append((atributo, hecho.valor, _fc(hecho.fc)))

    return [
        "## 4. Ejemplo de traza con caso concreto",
        "",
        "Caso `Sucursal El Alto / pollo` de `expert_system/demo.py`. Los datos se",
        "inyectan con certeza 1.0 y el encadenamiento hacia adelante usa el umbral",
        "declarado en `config.UMBRAL_CF_EXPERTO`.",
        "",
        "### 4.1 Hechos del caso",
        "",
        *_datos_del_caso(),
        "",
        "### 4.2 Reglas disparadas, en orden",
        "",
        "El CF de conclusión de cada fila es `CF premisa × FC regla`. El CF final",
        "puede cambiar después al combinarse varias reglas con MYCIN.",
        "",
        *_tabla_traza(traza),
        "",
        f"Se dispararon **{len(traza)} reglas** en total.",
        "",
        "### 4.3 Certeza final acumulada",
        "",
        *_tabla(("Atributo", "Conclusión", "CF final"), filas_finales),
    ]


def generar_documento(base: BaseConocimientos | None = None) -> str:
    """Genera el contenido completo de ``docs/reglas.md`` sin escribir archivos."""
    base = base if base is not None else BaseConocimientos.desde_json(ARCHIVO_REGLAS_EXPERTO)
    lineas = [
        "# Reglas reales del sistema inteligente",
        "",
        "> Documento generado automáticamente con `python -m expert_system.exportar_reglas`.",
        "> Fuentes: `expert_system/reglas.json`, `config.REGLAS_DIFUSAS` y la traza real",
        "> del caso de `expert_system.demo`. No editar a mano.",
        "",
        *_seccion_reglas(base),
        "",
        *_seccion_lenguaje_natural(base),
        "",
        *_seccion_resumen(base),
        "",
        *_seccion_traza(base),
        "",
    ]
    return "\n".join(lineas)


def exportar(destino: Path | str = ARCHIVO_SALIDA) -> Path:
    """Escribe el documento generado en ``destino`` y devuelve la ruta."""
    ruta = Path(destino)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(generar_documento(), encoding="utf-8")
    return ruta


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del módulo ejecutable."""
    parser = argparse.ArgumentParser(description="Exporta las reglas reales a Markdown.")
    parser.add_argument(
        "--salida",
        type=Path,
        default=ARCHIVO_SALIDA,
        help=f"Archivo Markdown a generar (por defecto: {ARCHIVO_SALIDA})",
    )
    args = parser.parse_args(argv)
    ruta = exportar(args.salida)
    print(f"Documento generado: {ruta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
