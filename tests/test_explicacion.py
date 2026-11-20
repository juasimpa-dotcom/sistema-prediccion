"""Pruebas de las explicaciones generadas desde la traza."""

from __future__ import annotations

import pytest

from expert_system.base_conocimientos import BaseConocimientos
from expert_system.explicacion import Explicacion, como, explicar, por_que, por_que_pregunta
from expert_system.memoria_trabajo import MemoriaTrabajo
from expert_system.motor_inferencia import (
    MotorInferencia,
    PasoInferencia,
    Pregunta,
    TrazaInferencia,
)


def _base() -> BaseConocimientos:
    """Base mínima con una regla de diagnóstico y una de recomendación."""
    return BaseConocimientos.desde_dict(
        {
            "version": "test",
            "reglas": [
                {
                    "id": "D",
                    "descripcion": "Falta de stock explica la caída",
                    "categoria": "diagnostico",
                    "prioridad": 5,
                    "fc": 0.9,
                    "condiciones": {
                        "operador": "and",
                        "condiciones": [{"atributo": "stock", "operador": "menor_que", "valor": 1}],
                    },
                    "conclusion": {"atributo": "causa", "valor": "stock"},
                },
                {
                    "id": "A",
                    "descripcion": "Reponer ante falta de stock",
                    "categoria": "recomendacion",
                    "prioridad": 9,
                    "fc": 0.8,
                    "condiciones": {
                        "operador": "and",
                        "condiciones": [
                            {"atributo": "causa", "operador": "igual", "valor": "stock"}
                        ],
                    },
                    "conclusion": {"atributo": "accion", "valor": "reponer"},
                },
            ],
        }
    )


def test_por_que_con_reglas_disparadas() -> None:
    """La explicación nombra las reglas y sus factores."""
    base = _base()
    motor = MotorInferencia(base)
    motor.memoria.actualizar("stock", 0.5, 1.0, "sensor")
    traza = motor.encadenar_adelante()
    texto = por_que("causa", "stock", base, traza, motor.memoria)
    assert "Regla D" in texto
    assert "FC de la premisa +1.00" in texto
    assert "aportó +0.90" in texto


def test_por_que_sin_disparo_pero_con_reglas() -> None:
    """Sin pasos, se listan las reglas aplicables."""
    base = _base()
    texto = por_que("causa", "stock", base, TrazaInferencia(modo="adelante"))
    assert "No se disparó ninguna regla" in texto
    assert "D: Falta de stock explica la caída" in texto


def test_por_que_sin_reglas_y_con_evidencia_directa() -> None:
    """Se informa cuando no hay reglas y se cita la evidencia del usuario."""
    base = _base()
    assert "No hay reglas" in por_que("otro", "x", base)
    memoria = MemoriaTrabajo()
    memoria.actualizar("causa", "stock", 0.7, "sensor", "medición directa")
    texto = por_que("causa", "stock", base, memoria=memoria)
    assert "evidencia directa" in texto
    assert "medición directa" in texto


def test_como_con_pasos_y_combinacion() -> None:
    """La narración incluye orden, premisas, propagación y combinación."""
    base = _base()
    motor = MotorInferencia(base)
    motor.memoria.actualizar("stock", 0.5, 1.0, "sensor")
    traza = motor.encadenar_adelante()
    texto = como(traza, base)
    assert "encadenamiento hacia adelante en 2 pasos" in texto
    assert "CF premisa +1.000" in texto
    assert "se derivó «causa=stock»" in texto
    assert "1. [diagnostico] D:" in texto


def test_como_sin_pasos_y_con_descripcion_desde_base() -> None:
    """Una traza vacía se explica y un paso sin descripción se enriquece."""
    base = _base()
    assert "No se disparó ninguna regla" in como(TrazaInferencia(modo="atras"))

    traza = TrazaInferencia(modo="atras")
    traza.registrar_disparo(
        PasoInferencia(
            orden=1,
            regla_id="D",
            descripcion="",
            categoria="diagnostico",
            premisa="(stock < 1)",
            cf_premisa=1.0,
            fc_regla=0.9,
            cf_conclusion=0.9,
            conclusion_atributo="causa",
            conclusion_valor="stock",
            momento="2026-01-01T00:00:00+00:00",
        )
    )
    assert "Falta de stock explica la caída" in como(traza, base)


def test_por_que_pregunta_con_regla_conocida_y_desconocida() -> None:
    """La pregunta se justifica con la regla que la originó."""
    base = _base()
    pregunta = Pregunta("stock", 1, "D", "causa=stock", "2026-01-01T00:00:00+00:00")
    texto = por_que_pregunta(pregunta, base)
    assert "Te pido «stock=1»" in texto
    assert "Falta de stock explica la caída" in texto
    desconocida = Pregunta("x", 1, "ZZZ", "objetivo", "2026-01-01T00:00:00+00:00")
    assert "la regla ZZZ" in por_que_pregunta(desconocida, base)


def test_explicar_incluye_preguntas_y_texto() -> None:
    """La explicación agregada conserva las tres secciones."""
    base = _base()
    pregunta = Pregunta("stock", 1, "D", "causa=stock", "2026-01-01T00:00:00+00:00")
    traza = TrazaInferencia(modo="atras", objetivo="causa=stock")
    traza.registrar_pregunta(pregunta)
    explicacion = explicar("causa", "stock", base, traza)
    texto = explicacion.a_texto()
    assert "¿POR QUÉ?" in texto
    assert "¿CÓMO?" in texto
    assert "¿POR QUÉ ME PIDES ESTOS DATOS?" in texto
    assert explicacion.objetivo == "causa=stock"
    assert isinstance(explicacion, Explicacion)


def test_explicar_rechaza_resultado_como_valor() -> None:
    """Se induce a pasar el resultado completo en lugar de sus campos."""
    base = _base()
    resultado = MotorInferencia(base).verificar("causa", "stock")
    with pytest.raises(TypeError, match="resultado.atributo"):
        explicar("causa", resultado, base)


def test_combinacion_aparece_en_explicacion() -> None:
    """Cuando dos reglas respaldan lo mismo se menciona la combinación MYCIN."""
    base = _base()
    traza = TrazaInferencia(modo="adelante")
    for regla_id in ("D", "A"):
        traza.registrar_disparo(
            PasoInferencia(
                orden=len(traza) + 1,
                regla_id=regla_id,
                descripcion="desc",
                categoria="prueba",
                premisa="(x)",
                cf_premisa=1.0,
                fc_regla=0.5,
                cf_conclusion=0.5,
                conclusion_atributo="causa",
                conclusion_valor="stock",
                momento="2026-01-01T00:00:00+00:00",
            )
        )
    assert "combinada con MYCIN" in como(traza, base)
