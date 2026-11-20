"""Demostración completa del sistema experto con un caso de retail boliviano.

Ejecutar:

.. code-block:: powershell

    python -m expert_system.demo

El caso usa la base declarativa ``reglas.json``. El motor no conoce el dominio:
todo el vocabulario retail vive en los datos iniciales y en las reglas.
"""

from __future__ import annotations

import logging

from config import ARCHIVO_REGLAS_EXPERTO, ATRIBUTO_RIESGO_DIFUSO
from expert_system.base_conocimientos import BaseConocimientos
from expert_system.explicacion import explicar, por_que_pregunta
from expert_system.logica_difusa import SistemaDifuso
from expert_system.memoria_trabajo import MemoriaTrabajo
from expert_system.motor_inferencia import MotorInferencia, TrazaInferencia

DATOS_CASO: dict[str, object] = {
    "ventas_caida_pct": 18.0,
    "stock_cobertura": 0.12,
    "merma_pct": 14.5,
    "temperatura_media": 17.0,
    "es_perecible": True,
    "en_promocion": False,
    "es_feriado": False,
    "afluencia_rel": 0.72,
    "precio_vs_competencia": 1.12,
    "temporada": "alta",
    "cumplimiento_esperado_pct": 82.0,
    "descuento_pct": 0.0,
    "personal_rel": 0.72,
    "hay_excedente_en_otra_sucursal": True,
    "reabastecimiento_tardia": True,
}


def hechos_del_caso() -> MemoriaTrabajo:
    """Convierte el caso de negocio en hechos tipados de la memoria de trabajo."""
    memoria = MemoriaTrabajo()
    for atributo, valor in DATOS_CASO.items():
        memoria.actualizar(
            atributo,
            valor,
            1.0,
            origen="sensor:ventas_semanales",
            detalle="dato observado y cerrado de la semana",
        )
    return memoria


def _imprimir_traza(traza: TrazaInferencia) -> None:
    """Imprime los pasos de una traza de inferencia."""
    print("\n--- Traza de inferencia ---")
    for paso in traza.pasos:
        print(
            f"  {paso.orden:>2}. [{paso.categoria}] {paso.regla_id}: {paso.descripcion}\n"
            f"       premisa CF {paso.cf_premisa:+.3f} × regla CF {paso.fc_regla:+.3f} "
            f"=> {paso.conclusion} CF {paso.cf_conclusion:+.3f}"
        )
    if not traza.pasos:
        print("  (ninguna regla alcanzó el umbral)")


def demostrar_adelante(base: BaseConocimientos) -> None:
    """Ejecuta el encadenamiento hacia adelante y explica la recomendación final."""
    memoria = hechos_del_caso()
    motor = MotorInferencia(base, memoria)
    traza = motor.encadenar_adelante()
    _imprimir_traza(traza)

    print("\n--- Hechos derivados ---")
    for atributo in ("causa_ventas_bajas", "nivel_riesgo", "accion_recomendada"):
        hecho = memoria.consultar(atributo)
        if hecho is not None:
            print(f"  {hecho.descripcion}")

    accion = memoria.consultar("accion_recomendada")
    if accion is not None:
        print()
        print(
            explicar(
                "accion_recomendada",
                accion.valor,
                base,
                traza=traza,
                memoria=memoria,
            ).a_texto()
        )


def _ejecutar(
    base: BaseConocimientos, con_difuso: bool
) -> tuple[MemoriaTrabajo, TrazaInferencia, MotorInferencia]:
    """Ejecuta el mismo caso con o sin fuzzificador y devuelve su resultado."""
    memoria = hechos_del_caso()
    motor = MotorInferencia(
        base,
        memoria,
        fuzzificador=SistemaDifuso() if con_difuso else None,
    )
    traza = motor.encadenar_adelante()
    return memoria, traza, motor


def _resumen(memoria: MemoriaTrabajo) -> str:
    """Devuelve riesgo y acción final de una memoria ya inferida."""
    riesgo = memoria.consultar("nivel_riesgo")
    accion = memoria.consultar("accion_recomendada")
    riesgo_texto = riesgo.valor if riesgo is not None else "sin conclusión"
    accion_texto = accion.valor if accion is not None else "sin conclusión"
    return f"riesgo={riesgo_texto}, accion={accion_texto}"


def demostrar_comparacion(base: BaseConocimientos) -> None:
    """Muestra el mismo caso con y sin lógica difusa y comenta la diferencia."""
    memoria_crisp, traza_crisp, _ = _ejecutar(base, con_difuso=False)
    memoria_difusa, traza_difusa, motor_difuso = _ejecutar(base, con_difuso=True)

    print("\n=== Mismo caso: sin difuso vs con difuso ===")
    print(
        f"  Sin lógica difusa : {_resumen(memoria_crisp)}; "
        f"{len(traza_crisp)} reglas crisp disparadas"
    )
    print(
        f"  Con lógica difusa : {_resumen(memoria_difusa)}; "
        f"{len(traza_difusa)} reglas disparadas"
    )
    resultado = motor_difuso.ultimo_resultado_difuso
    if resultado is not None:
        print(f"  Defuzzificación   : {resultado.descripcion()}")
        print(f"  Reglas difusas activadas: {', '.join(resultado.reglas_activadas)}")
        print("  Hechos simbólicos con CF = grado de pertenencia:")
        for hecho in resultado.hechos:
            print(f"    - {hecho.descripcion}")
        riesgo = memoria_difusa.consultar(ATRIBUTO_RIESGO_DIFUSO)
        if riesgo is not None:
            print(f"  Riesgo difuso inyectado: {riesgo.descripcion}")
    accion_crisp = memoria_crisp.consultar("accion_recomendada")
    accion_difusa = memoria_difusa.consultar("accion_recomendada")
    coincide = (
        accion_crisp is not None
        and accion_difusa is not None
        and accion_crisp.valor == accion_difusa.valor
    )
    comentario = (
        "sin difuso, los valores 82 % de cumplimiento y 14,5 % de merma cruzan "
        "umbrales rígidos y el razonamiento depende de cortes exactos. Con "
        "difuso, esos mismos números pertenecen parcialmente a varias etiquetas: "
        "el riesgo se defuzzifica por centroide y el motor recibe hechos "
        "simbólicos con CF gradual. "
    )
    if coincide:
        comentario += (
            "En este caso ambas vías coinciden, pero la justificación difusa "
            "cambia con suavidad ante pequeñas variaciones del dato."
        )
    else:
        comentario += (
            "En este caso la recomendación final cambia: los hechos graduales "
            "activan reglas adicionales que reordenan las prioridades. Esa "
            "diferencia es una hipótesis a revisar con el experto de negocio."
        )
    print(f"  Comentario: {comentario}")
    print()
    print(
        explicar(
            "accion_recomendada",
            memoria_difusa.consultar("accion_recomendada").valor,  # type: ignore[union-attr]
            base,
            traza=traza_difusa,
            memoria=memoria_difusa,
        ).a_texto()
    )


def demostrar_atras(base: BaseConocimientos) -> None:
    """Verifica una hipótesis hacia atrás pidiendo los datos que faltan."""
    datos_disponibles = dict(DATOS_CASO)
    datos_disponibles.pop("en_promocion")
    datos_disponibles.pop("es_feriado")

    def proveedor(atributo: str, esperado: object) -> object | None:
        """Devuelve el dato almacenado o ``None`` si no está disponible."""
        del esperado
        return datos_disponibles.get(atributo)

    memoria = MemoriaTrabajo()
    memoria.actualizar("ventas_caida_pct", DATOS_CASO["ventas_caida_pct"], 1.0, "sensor")
    motor = MotorInferencia(base, memoria, proveedor=proveedor)
    resultado = motor.verificar("causa_ventas_bajas", "falta_promocion")

    print("\n=== Encadenamiento hacia atrás ===")
    print(f"Hipótesis: {resultado.descripcion} => {'confirmada' if resultado else 'no confirmada'}")
    print("Preguntas realizadas:")
    for pregunta in resultado.traza.preguntas:
        print(f"  - {pregunta.atributo}: {por_que_pregunta(pregunta, base)}")
    print()
    print(
        explicar(
            "causa_ventas_bajas",
            "falta_promocion",
            base,
            traza=resultado.traza,
            memoria=memoria,
        ).a_texto()
    )


def main() -> None:
    """Carga la base, ejecuta ambos encadenamientos e imprime sus explicaciones."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s | %(message)s")
    base = BaseConocimientos.desde_json(ARCHIVO_REGLAS_EXPERTO)
    print("=== Sistema experto: caso Sucursal El Alto / pollo ===")
    print(f"Base '{base.version}': {len(base.reglas)} reglas")
    for categoria in base.categorias():
        print(f"  - {categoria}: {len(base.por_categoria(categoria))} reglas")
    demostrar_adelante(base)
    demostrar_comparacion(base)
    demostrar_atras(base)


if __name__ == "__main__":
    main()
