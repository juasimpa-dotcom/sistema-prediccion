"""Demostración del flujo completo con tres casos representativos.

Ejecutar:

.. code-block:: powershell

    python -m core.demo

Cada caso construye su propia fachada para que la memoria de trabajo y el
motor arranquen limpios; no hay estado global entre ejecuciones.
"""

from __future__ import annotations

from core.fabrica import construir_contexto_desde_csv, construir_sistema

CASOS: tuple[dict[str, object], ...] = (
    {
        "titulo": "1) Sucursal en riesgo (El Alto / pollo)",
        "sucursal": "El Alto",
        "categoria": "pollo",
        "factor_meta": 1.20,
        "stock_cobertura": 0.18,
        "afluencia_rel": 0.70,
        "precio_vs_competencia": 1.12,
        "merma_inicial": 14.5,
        "hay_excedente_en_otra_sucursal": True,
        "reabastecimiento_tardia": True,
    },
    {
        "titulo": "2) Sucursal normal (Sopocachi / cerdo)",
        "sucursal": "Sopocachi",
        "categoria": "cerdo",
        "factor_meta": 0.85,
        "stock_cobertura": 0.80,
        "afluencia_rel": 1.05,
        "merma_inicial": 4.0,
        "es_perecible": False,
        "precio_vs_competencia": 1.0,
    },
    {
        "titulo": "3) Sucursal con exceso de stock (Miraflores / embutidos)",
        "sucursal": "Miraflores",
        "categoria": "embutidos",
        "factor_meta": 1.05,
        "stock_cobertura": 1.60,
        "afluencia_rel": 0.95,
        "merma_inicial": 6.0,
        "es_perecible": True,
        "precio_vs_competencia": 1.05,
    },
)


def main() -> None:
    """Ejecuta e imprime los tres casos con su explicación completa."""
    for caso in CASOS:
        titulo = str(caso["titulo"])
        datos = {clave: valor for clave, valor in caso.items() if clave != "titulo"}
        print(f"\n{'=' * 78}\n{titulo}\n{'=' * 78}")

        sistema = construir_sistema()
        contexto = construir_contexto_desde_csv(**datos)
        resultado = sistema.ejecutar(contexto)

        print(resultado.resumen())
        print(f"Reglas crisp disparadas: {', '.join(resultado.reglas_disparadas) or 'ninguna'}")
        print(f"Plan: {resultado.plan.descripcion} ({resultado.plan.costo_bs:,.2f} Bs)")
        print("\n" + resultado.explicacion)


if __name__ == "__main__":
    main()
