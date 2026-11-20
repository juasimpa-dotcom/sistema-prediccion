"""Pruebas unitarias de la fachada con dobles inyectados por constructor."""

from __future__ import annotations

from config import (
    ATRIBUTO_CONFIANZA_ML,
    ATRIBUTO_PREDICCION_BS,
    SALIDAS_DIFUSAS,
)
from core.planificador import PlanificadorComercial, SolicitudPlan, restricciones_por_causas
from core.resultado import CausaDiagnostico, PlanRecomendado
from core.sistema import SistemaInteligente
from expert_system.explicacion import Explicacion
from expert_system.logica_difusa import ResultadoDifuso
from expert_system.memoria_trabajo import MemoriaTrabajo
from expert_system.motor_inferencia import PasoInferencia, TrazaInferencia
from ml.predictor import PrediccionVentas


class PredictorFalso:
    """Predictor de prueba que devuelve una predicción fija."""

    def __init__(self, prediccion: PrediccionVentas) -> None:
        self.prediccion = prediccion
        self.entrada: object = None

    def predecir(self, entrada: object) -> PrediccionVentas:
        self.entrada = entrada
        return self.prediccion


class MotorFalso:
    """Motor de prueba que registra el orden de las etapas y una causa."""

    def __init__(self, difuso: ResultadoDifuso) -> None:
        self.ultimo_resultado_difuso = difuso
        self.llamadas: list[str] = []

    def fuzzificar(self, memoria: MemoriaTrabajo | None = None) -> tuple:
        assert memoria is not None
        self.llamadas.append("fuzzificar")
        return ()

    def aplicar_difuso(self, memoria: MemoriaTrabajo | None = None) -> ResultadoDifuso:
        assert memoria is not None
        self.llamadas.append("aplicar_difuso")
        return self.ultimo_resultado_difuso

    def encadenar_adelante(self, memoria: MemoriaTrabajo | None = None) -> TrazaInferencia:
        assert memoria is not None
        self.llamadas.append("encadenar_adelante")
        memoria.actualizar(
            "causa_ventas_bajas",
            "merma_alta",
            0.7,
            "regla:D03",
            "merma elevada en perecibles",
        )
        traza = TrazaInferencia(modo="adelante")
        traza.registrar_disparo(
            PasoInferencia(
                orden=1,
                regla_id="D03",
                descripcion="Merma elevada en perecibles",
                categoria="diagnostico",
                premisa="merma_pct > 12",
                cf_premisa=1.0,
                fc_regla=0.85,
                cf_conclusion=0.7,
                conclusion_atributo="causa_ventas_bajas",
                conclusion_valor="merma_alta",
                momento="2026-01-01T00:00:00+00:00",
            )
        )
        return traza


class PlanificadorFalso:
    """Planificador de prueba que solo recuerda la solicitud recibida."""

    def __init__(self) -> None:
        self.solicitud: object = None

    def planificar(self, solicitud: object) -> PlanRecomendado:
        self.solicitud = solicitud
        return PlanRecomendado(
            acciones=("reponer_stock(+400u)",),
            costo_bs=1_234.0,
            encontrado=True,
            nodos_expandidos=7,
            restricciones=("permitir_reasignacion",),
            justificacion="Plan simulado para la prueba unitaria.",
        )


def _difuso_de_prueba() -> ResultadoDifuso:
    riesgo, urgencia = SALIDAS_DIFUSAS
    return ResultadoDifuso(
        entradas={"cumplimiento_esperado_pct": 80.0},
        valores={riesgo: 78.0, urgencia: 70.0},
        etiquetas={riesgo: "alto", urgencia: "media"},
        grados={riesgo: {"alto": 0.6}, urgencia: {"media": 0.5}},
        fuerzas={"DF01": 0.5},
        hechos=(),
        hechos_salida=(),
    )


def _contexto_de_prueba():
    from core.contexto import ContextoNegocio

    fila = {
        "fecha_semana": "2025-12-22",
        "sucursal": "El Alto",
        "categoria": "pollo",
        "stock_inicial": 400.0,
        "unidades_vendidas": 900.0,
        "merma_pct": 14.0,
        "afluencia_clientes": 10_000.0,
        "personal_asignado": 6.0,
        "meta_ventas_bs": 40_000.0,
        "descuento_pct": 0.0,
        "temporada": "alta",
        "en_promocion": False,
        "es_feriado_semana": False,
        "temperatura_media": 15.0,
    }
    return ContextoNegocio(
        sucursal="El Alto",
        categoria="pollo",
        historial=(dict(fila),) * 8,
        meta_bs=45_000.0,
    )


def test_ejecutar_devuelve_resultado_completo_y_ordena_etapas(base_reglas) -> None:
    prediccion = PrediccionVentas(
        valor_predicho=30_000.0,
        cumplimiento_esperado_pct=66.67,
        confianza=0.42,
        principales_factores=("ventas_lag_1=29000.0", "afluencia_clientes=10000.0"),
    )
    predictor = PredictorFalso(prediccion)
    memoria = MemoriaTrabajo()
    motor = MotorFalso(_difuso_de_prueba())
    planificador = PlanificadorFalso()
    llamadas_explicador: list[tuple[object, object]] = []

    def explicador(objetivo, valor, base, traza=None, memoria=None):
        llamadas_explicador.append((objetivo, valor))
        return Explicacion(objetivo=str(objetivo), por_que="por qué falso", como="cómo falso")

    sistema = SistemaInteligente(
        predictor=predictor,
        base=base_reglas,
        memoria=memoria,
        motor=motor,
        planificador=planificador,
        explicador=explicador,
    )

    resultado = sistema.ejecutar(_contexto_de_prueba())

    assert resultado.prediccion is prediccion
    assert resultado.confianza == 0.42
    assert resultado.cumplimiento_pct == 66.67
    assert len(resultado.diagnostico) == 1
    assert resultado.diagnostico[0] == CausaDiagnostico(
        causa="merma_alta",
        cf=0.7,
        descripcion="Merma elevada en perecibles",
        reglas=("D03",),
    )
    assert resultado.riesgo.etiqueta == "alto"
    assert resultado.riesgo.urgencia == "media"
    assert resultado.riesgo.reglas_activadas == ("DF01",)
    assert resultado.plan.acciones == ("reponer_stock(+400u)",)
    assert resultado.plan.costo_bs == 1_234.0
    assert resultado.reglas_disparadas == ("D03",)

    assert motor.llamadas == ["fuzzificar", "aplicar_difuso", "encadenar_adelante"]
    assert predictor.entrada is not None
    assert len(predictor.entrada["historial"]) == 8  # type: ignore[index]
    assert planificador.solicitud is not None
    assert planificador.solicitud.causas == resultado.diagnostico  # type: ignore[union-attr]
    assert planificador.solicitud.meta_bs == 45_000.0  # type: ignore[union-attr]
    assert llamadas_explicador == [("causa_ventas_bajas", "merma_alta")]

    assert memoria.consultar(ATRIBUTO_PREDICCION_BS).fc == 0.42
    assert memoria.consultar(ATRIBUTO_CONFIANZA_ML).fc == 0.42

    texto = resultado.explicacion
    assert "POR QUÉ PREDIJO" in texto
    assert "QUÉ REGLAS DISPARARON" in texto
    assert "CÓMO SE GRADUÓ EL RIESGO" in texto
    assert "POR QUÉ RECOMIENDA ESE PLAN" in texto
    assert "COMPARATIVA SIMBÓLICO" in texto
    assert "ventas_lag_1=29000.0" in texto
    assert "por qué falso" in texto


def test_restricciones_del_diagnostico_se_combinan_con_and() -> None:
    causas = (
        CausaDiagnostico("merma_alta", 0.8, ""),
        CausaDiagnostico("exceso_stock", 0.4, ""),
    )
    assert restricciones_por_causas(causas) == ("permitir_reasignacion",)
    assert restricciones_por_causas(()) == ()


def test_constructor_rechaza_dependencias_incompletas(base_reglas) -> None:
    class MotorIncompleto:
        def fuzzificar(self, memoria=None):
            return ()

    try:
        SistemaInteligente(
            predictor=PredictorFalso(PrediccionVentas(1.0, 1.0, 0.5, ("factor",))),
            base=base_reglas,
            memoria=MemoriaTrabajo(),
            motor=MotorIncompleto(),
            planificador=PlanificadorFalso(),
        )
    except TypeError as error:
        assert "aplicar_difuso" in str(error)
    else:
        raise AssertionError("El constructor debió rechazar un motor incompleto")


def test_planificador_real_pasa_flags_a_la_fabrica() -> None:
    vistos: dict[str, object] = {}

    def crear_problema(**kwargs):
        vistos.update(kwargs)
        return object()

    def buscar(problema):
        from search.resultado import Resultado

        return Resultado(
            plan=(),
            costo=0.0,
            nodos_expandidos=1,
            nodos_generados=0,
            profundidad=0,
            tiempo=0.0,
        )

    planificador = PlanificadorComercial(crear_problema=crear_problema, buscar=buscar)
    solicitud = SolicitudPlan(
        sucursal="El Alto",
        categoria="pollo",
        meta_bs=30_000.0,
        presupuesto_bs=9_000.0,
        stock_inicial=2_476.0,
        merma_inicial=14.0,
        personal_inicial=9.0,
        afluencia=21_157.0,
        causas=(CausaDiagnostico("merma_alta", 0.8, ""),),
    )

    plan = planificador.planificar(solicitud)

    assert vistos["permitir_reasignacion"] is False
    assert vistos["permitir_reducir_merma"] is True
    assert vistos["stock_inicial"] == 2_476
    assert vistos["stock_maximo"] == 2_876
    assert plan.restricciones == ("permitir_reasignacion",)
