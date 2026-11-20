"""Pruebas de integración entre la lógica difusa y el motor de inferencia."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from config import ARCHIVO_REGLAS_EXPERTO, ATRIBUTO_RIESGO_DIFUSO
from expert_system.base_conocimientos import BaseConocimientos
from expert_system.demo import DATOS_CASO, hechos_del_caso
from expert_system.logica_difusa import (
    Fuzzificador,
    HechoDifuso,
    ResultadoDifuso,
    SistemaDifuso,
)
from expert_system.memoria_trabajo import MemoriaTrabajo
from expert_system.motor_inferencia import MotorInferencia


@pytest.fixture(scope="module")
def base() -> BaseConocimientos:
    """Base retail con reglas crisp y reglas consumidoras de hechos difusos."""
    return BaseConocimientos.desde_json(ARCHIVO_REGLAS_EXPERTO)


class FuzzificadorFalso:
    """Implementación mínima del protocolo para probar el desacople del motor."""

    def __init__(self) -> None:
        """Inicializa el contador de llamadas."""
        self.llamadas_fuzzificar = 0
        self.llamadas_calcular = 0
        self.resultado = ResultadoDifuso(
            entradas={"x": 1.0},
            valores={"nivel_riesgo_incumplimiento": 95.0, "urgencia_accion": 90.0},
            etiquetas={"nivel_riesgo_incumplimiento": "crítico", "urgencia_accion": "alta"},
            grados={
                "nivel_riesgo_incumplimiento": {"crítico": 0.9},
                "urgencia_accion": {"alta": 0.8},
            },
            fuerzas={"DF99": 1.0},
            hechos=(HechoDifuso("merma", "alta", 0.7, "merma", "merma_pct"),),
            hechos_salida=(
                HechoDifuso(
                    atributo=ATRIBUTO_RIESGO_DIFUSO,
                    valor="crítico",
                    fc=0.9,
                    variable="nivel_riesgo_incumplimiento",
                    origen="sistema_difuso",
                    detalle="centroide 95.0; pertenencia 0.900; reglas activadas: DF99",
                ),
                HechoDifuso(
                    atributo="urgencia_accion",
                    valor="alta",
                    fc=0.8,
                    variable="urgencia_accion",
                    origen="sistema_difuso",
                    detalle="centroide 90.0; pertenencia 0.800; reglas activadas: DF99",
                ),
            ),
        )

    def variables(self) -> tuple[str, ...]:
        """Devuelve una variable de prueba."""
        return ("merma",)

    def etiquetas(self, variable: str) -> tuple[str, ...]:
        """Devuelve una etiqueta de prueba."""
        return ("alta",)

    def pertenencia(self, variable: str, etiqueta: str, valor: float) -> float:
        """Devuelve una pertenencia fija."""
        return 0.7

    def fuzzificar(self, valores: Mapping[str, float]) -> tuple[HechoDifuso, ...]:
        """Registra la llamada y devuelve el hecho preparado."""
        self.llamadas_fuzzificar += 1
        return self.resultado.hechos

    def calcular(self, valores: Mapping[str, float]) -> ResultadoDifuso:
        """Registra la llamada y devuelve el resultado preparado."""
        self.llamadas_calcular += 1
        return self.resultado


def test_motor_usa_solo_la_interfaz_del_fuzzificador(base: BaseConocimientos) -> None:
    """Un fuzzificador arbitrario basta: el motor no conoce scikit-fuzzy."""
    falso = FuzzificadorFalso()
    memoria = MemoriaTrabajo()
    memoria.actualizar("merma_pct", 20.0, 1.0, "sensor")
    motor = MotorInferencia(base, memoria, fuzzificador=falso)
    traza = motor.encadenar_adelante()

    assert isinstance(falso, Fuzzificador)
    assert falso.llamadas_fuzzificar == 1
    assert falso.llamadas_calcular == 1
    assert len(traza) > 0
    hecho = memoria.consultar("merma", "alta")
    assert hecho is not None
    assert hecho.fc == pytest.approx(0.7)
    assert hecho.origen == "fuzzificacion"
    riesgo = memoria.consultar(ATRIBUTO_RIESGO_DIFUSO, "crítico")
    assert riesgo is not None
    assert riesgo.fc == pytest.approx(0.9)
    assert riesgo.origen == "sistema_difuso"
    assert "centroide 95.0" in riesgo.detalle
    urgencia = memoria.consultar("urgencia_accion", "alta")
    assert urgencia is not None
    assert urgencia.fc == pytest.approx(0.8)
    assert motor.ultimo_resultado_difuso is falso.resultado


def test_no_duplica_hechos_difusos_en_llamadas_repetidas(base: BaseConocimientos) -> None:
    """El motor aplica la fuzzificación una sola vez por memoria."""
    falso = FuzzificadorFalso()
    memoria = MemoriaTrabajo()
    memoria.actualizar("merma_pct", 20.0, 1.0, "sensor")
    motor = MotorInferencia(base, memoria, fuzzificador=falso)
    motor.encadenar_adelante()
    motor.encadenar_adelante()
    motor.verificar("nivel_riesgo", "alto")

    assert falso.llamadas_fuzzificar == 1
    assert falso.llamadas_calcular == 1
    assert len(memoria.evidencias("merma", "alta")) == 1
    assert len(memoria.evidencias(ATRIBUTO_RIESGO_DIFUSO, "crítico")) == 1
    assert motor.aplicar_difuso() is falso.resultado


def test_aplicar_y_fuzzificar_con_memoria_explicita(base: BaseConocimientos) -> None:
    """Los métodos públicos aceptan una memoria distinta de la del motor."""
    falso = FuzzificadorFalso()
    motor = MotorInferencia(base, fuzzificador=falso)
    externa = MemoriaTrabajo()
    externa.actualizar("merma_pct", 20.0, 1.0, "sensor")
    hechos = motor.fuzzificar(externa)
    assert len(hechos) == 1
    assert motor.aplicar_difuso(externa) is falso.resultado
    with pytest.raises(TypeError):
        motor.fuzzificar(memoria="no es memoria")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        motor.aplicar_difuso(memoria="no es memoria")  # type: ignore[arg-type]


def test_sin_fuzzificador_no_hay_efecto(base: BaseConocimientos) -> None:
    """El motor sigue funcionando igual si no se le inyecta difuso."""
    motor = MotorInferencia(base)
    assert motor.fuzzificar() == ()
    assert motor.aplicar_difuso() is None
    assert motor.ultimo_resultado_difuso is None
    with pytest.raises(TypeError):
        MotorInferencia(base, fuzzificador="no es fuzzificador")  # type: ignore[arg-type]


def test_integracion_real_con_sistema_difuso(base: BaseConocimientos) -> None:
    """El sistema difuso real inyecta hechos con CF gradual y reglas crisp reaccionan."""
    sistema = SistemaDifuso()
    sin_difuso = MotorInferencia(base, hechos_del_caso())
    con_difuso = MotorInferencia(base, hechos_del_caso(), fuzzificador=sistema)
    traza_crisp = sin_difuso.encadenar_adelante()
    traza_difusa = con_difuso.encadenar_adelante()

    assert con_difuso.ultimo_resultado_difuso is not None
    assert con_difuso.ultimo_resultado_difuso.hechos
    assert "F01" in traza_difusa.reglas_usadas() or "F02" in traza_difusa.reglas_usadas()
    assert "F04" in traza_difusa.reglas_usadas() or "F05" in traza_difusa.reglas_usadas()
    assert len(traza_difusa) > len(traza_crisp)
    assert con_difuso.memoria.contiene("nivel_stock", "crítico")
    assert con_difuso.memoria.contiene("urgencia_accion")
    assert DATOS_CASO["stock_cobertura"] == 0.12
    riesgo = con_difuso.memoria.consultar(ATRIBUTO_RIESGO_DIFUSO)
    assert riesgo is not None and riesgo.fc > 0.0


def test_verificar_prepara_difuso_una_solavez(base: BaseConocimientos) -> None:
    """El encadenamiento hacia atrás también prepara la fuzzificación."""
    falso = FuzzificadorFalso()
    memoria = MemoriaTrabajo()
    memoria.actualizar("merma_pct", 20.0, 1.0, "sensor")
    motor = MotorInferencia(base, memoria, fuzzificador=falso)
    resultado = motor.verificar("nivel_riesgo", "alto")
    assert resultado.traza.modo == "atras"
    assert falso.llamadas_fuzzificar == 1
    assert falso.llamadas_calcular == 1
    assert memoria.contiene("merma", "alta")
