"""Pruebas del sistema difuso, su interfaz y sus gráficos de pertenencia."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from config import (
    ATRIBUTO_RIESGO_DIFUSO,
    ATRIBUTO_URGENCIA,
    MAPEO_DIFUSO_HECHOS,
    REGLAS_DIFUSAS,
    SALIDAS_DIFUSAS,
    UMBRAL_PERTENENCIA_DIFUSA,
    VARIABLES_DIFUSAS,
    RegionDifusa,
    ReglaDifusa,
    VariableDifusa,
)
from expert_system.logica_difusa import (
    Fuzzificador,
    HechoDifuso,
    ResultadoDifuso,
    SistemaDifuso,
    main,
)

CASO_CRITICO: dict[str, float] = {
    "cumplimiento_esperado_pct": 50.0,
    "stock_cobertura": 0.0,
    "merma_pct": 28.0,
    "afluencia_rel": 0.2,
    "descuento_pct": 0.0,
}
CASO_IDEAL: dict[str, float] = {
    "cumplimiento_esperado_pct": 125.0,
    "stock_cobertura": 1.5,
    "merma_pct": 2.0,
    "afluencia_rel": 1.4,
    "descuento_pct": 28.0,
}
CASO_BASE: dict[str, float] = {
    "cumplimiento_esperado_pct": 95.0,
    "stock_cobertura": 0.7,
    "merma_pct": 8.0,
    "afluencia_rel": 1.0,
    "descuento_pct": 10.0,
}


@pytest.fixture(scope="module")
def sistema() -> SistemaDifuso:
    """Sistema difuso construido desde la configuración real."""
    return SistemaDifuso()


def test_configuracion_declarada() -> None:
    """La configuración cumple los requisitos de variables, reglas y salidas."""
    entradas = {
        "cumplimiento_esperado",
        "nivel_stock",
        "merma",
        "afluencia",
        "intensidad_promocion",
    }
    assert entradas <= VARIABLES_DIFUSAS.keys()
    assert set(SALIDAS_DIFUSAS) <= VARIABLES_DIFUSAS.keys()
    assert {"bajo", "medio", "alto"} <= VARIABLES_DIFUSAS["cumplimiento_esperado"].etiquetas.keys()
    assert {"crítico", "adecuado", "excesivo"} <= VARIABLES_DIFUSAS["nivel_stock"].etiquetas.keys()
    assert {"baja", "media", "alta"} <= VARIABLES_DIFUSAS["merma"].etiquetas.keys()
    assert {"baja", "normal", "alta"} <= VARIABLES_DIFUSAS["afluencia"].etiquetas.keys()
    assert {"ninguna", "moderada", "fuerte"} <= VARIABLES_DIFUSAS[
        "intensidad_promocion"
    ].etiquetas.keys()
    assert {"bajo", "medio", "alto", "crítico"} <= VARIABLES_DIFUSAS[
        "nivel_riesgo_incumplimiento"
    ].etiquetas.keys()
    assert len(REGLAS_DIFUSAS) >= 15
    assert len({regla.id for regla in REGLAS_DIFUSAS}) == len(REGLAS_DIFUSAS)
    assert all(
        region.tipo in {"triangular", "trapezoidal"}
        for variable in VARIABLES_DIFUSAS.values()
        for region in variable.etiquetas.values()
    )
    assert set(MAPEO_DIFUSO_HECHOS.values()) <= entradas


def test_interfaces_y_protocolo(sistema: SistemaDifuso) -> None:
    """El sistema cumple el protocolo y expone sus variables y etiquetas."""
    assert isinstance(sistema, Fuzzificador)
    assert len(sistema.variables()) == 5
    assert set(sistema.variables_salida()) == set(SALIDAS_DIFUSAS)
    assert sistema.etiquetas("nivel_stock") == ("crítico", "adecuado", "excesivo")
    assert sistema.etiquetas("nivel_riesgo_incumplimiento") == (
        "bajo",
        "medio",
        "alto",
        "crítico",
    )
    with pytest.raises(ValueError, match="desconocida"):
        sistema.etiquetas("inexistente")
    with pytest.raises(ValueError, match="desconocida"):
        sistema.pertenencia("nivel_stock", "inexistente", 0.5)


@pytest.mark.parametrize(
    ("variable", "etiqueta", "valor", "esperado"),
    [
        ("nivel_stock", "crítico", 0.0, 1.0),
        ("nivel_stock", "crítico", 0.7, 0.0),
        ("nivel_stock", "adecuado", 0.7, 1.0),
        ("nivel_stock", "excesivo", 2.0, 1.0),
        ("cumplimiento_esperado", "medio", 95.0, 1.0),
        ("cumplimiento_esperado", "bajo", 0.0, 1.0),
        ("cumplimiento_esperado", "alto", 130.0, 1.0),
        ("merma", "baja", 0.0, 1.0),
        ("merma", "media", 11.0, 1.0),
        ("merma", "alta", 30.0, 1.0),
        ("afluencia", "normal", 1.0, 1.0),
        ("intensidad_promocion", "ninguna", 0.0, 1.0),
        ("intensidad_promocion", "fuerte", 30.0, 1.0),
        ("nivel_riesgo_incumplimiento", "crítico", 100.0, 1.0),
        ("urgencia_accion", "ninguna", 0.0, 1.0),
    ],
)
def test_pertenencia_en_picos_y_limites(
    sistema: SistemaDifuso,
    variable: str,
    etiqueta: str,
    valor: float,
    esperado: float,
) -> None:
    """Cada función alcanza 1 en su pico y 0 en el extremo opuesto."""
    assert sistema.pertenencia(variable, etiqueta, valor) == pytest.approx(esperado, abs=1e-6)


def test_pertenencia_intermedia_y_recorte(sistema: SistemaDifuso) -> None:
    """Los valores intermedios gradúan la pertenencia y se recorta el universo."""
    valor = sistema.pertenencia("nivel_stock", "crítico", 0.4)
    assert 0.0 < valor < 1.0
    # Los hombros planos hacen que fuera del universo la pertenencia sea 0.
    assert sistema.pertenencia("nivel_stock", "crítico", -5.0) == pytest.approx(0.0)
    assert sistema.pertenencia("nivel_stock", "excesivo", 2.0) == pytest.approx(1.0)
    assert 0.0 <= sistema.pertenencia("nivel_stock", "excesivo", 99.0) <= 1.0
    with pytest.raises(TypeError):
        sistema.pertenencia("nivel_stock", "crítico", "alto")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        sistema.pertenencia("nivel_stock", "crítico", True)  # type: ignore[arg-type]


def test_casos_conocidos(sistema: SistemaDifuso) -> None:
    """Los escenarios ideal y crítico producen salidas coherentes."""
    ideal = sistema.calcular(CASO_IDEAL)
    critico = sistema.calcular(CASO_CRITICO)
    assert ideal.etiquetas["nivel_riesgo_incumplimiento"] == "bajo"
    assert ideal.etiquetas["urgencia_accion"] == "ninguna"
    assert ideal.valores["nivel_riesgo_incumplimiento"] < 30.0
    assert critico.valores["nivel_riesgo_incumplimiento"] > 75.0
    assert critico.valores["urgencia_accion"] > 70.0
    assert "DF01" in critico.reglas_activadas
    assert critico.fuerzas["DF01"] > 0.9
    assert isinstance(ideal, ResultadoDifuso)
    assert "bajo" in ideal.descripcion()
    assert set(ideal.entradas) == set(sistema.variables())


def test_entradas_ausentes_usan_valor_neutro(sistema: SistemaDifuso) -> None:
    """Las entradas omitidas se completan con el punto medio del universo."""
    resultado = sistema.calcular({})
    assert set(resultado.entradas) == set(sistema.variables())
    assert resultado.entradas["cumplimiento_esperado"] == pytest.approx(65.0)
    assert resultado.entradas["nivel_stock"] == pytest.approx(1.0)
    assert resultado.hechos == ()


@pytest.mark.parametrize(
    ("variable", "opciones", "clave", "sentido"),
    [
        ("cumplimiento_esperado_pct", (60, 80, 100, 120), "nivel_riesgo_incumplimiento", -1),
        ("stock_cobertura", (0.1, 0.4, 0.7, 1.5), "nivel_riesgo_incumplimiento", -1),
        ("merma_pct", (2, 8, 16, 25), "nivel_riesgo_incumplimiento", 1),
        ("afluencia_rel", (0.4, 0.8, 1.0, 1.4), "nivel_riesgo_incumplimiento", -1),
        ("cumplimiento_esperado_pct", (60, 80, 100, 120), "urgencia_accion", -1),
        ("stock_cobertura", (0.1, 0.4, 0.7, 1.5), "urgencia_accion", -1),
        ("merma_pct", (2, 8, 16, 25), "urgencia_accion", 1),
    ],
)
def test_monotonia(
    sistema: SistemaDifuso,
    variable: str,
    opciones: tuple[float, ...],
    clave: str,
    sentido: int,
) -> None:
    """Más cumplimiento o stock reduce el riesgo; más merma lo aumenta."""
    valores = [
        sistema.calcular({**CASO_BASE, variable: opcion}).valores[clave] for opcion in opciones
    ]
    for anterior, posterior in zip(valores, valores[1:], strict=False):
        if sentido < 0:
            assert posterior <= anterior + 1e-6
        else:
            assert posterior >= anterior - 1e-6


def test_determinismo_y_fuerzas(sistema: SistemaDifuso) -> None:
    """El mismo caso produce el mismo centroide y fuerzas coherentes."""
    primero = sistema.calcular(CASO_CRITICO)
    segundo = sistema.calcular(CASO_CRITICO)
    assert primero.valores == segundo.valores
    assert primero.reglas_activadas == segundo.reglas_activadas
    assert all(0.0 <= fuerza <= 1.0 for fuerza in primero.fuerzas.values())
    assert len(primero.fuerzas) == len(REGLAS_DIFUSAS)
    for regla in REGLAS_DIFUSAS:
        if regla.id in primero.reglas_activadas:
            assert primero.fuerzas[regla.id] > 0.0


def test_fuzzificacion_con_cf_de_pertenencia(sistema: SistemaDifuso) -> None:
    """Cada hecho simbólico usa el grado de pertenencia como CF."""
    hechos = sistema.fuzzificar(CASO_CRITICO)
    assert hechos
    assert all(isinstance(hecho, HechoDifuso) for hecho in hechos)
    assert all(hecho.fc >= UMBRAL_PERTENENCIA_DIFUSA for hecho in hechos)
    assert all(hecho.hecho_origen in CASO_CRITICO for hecho in hechos)
    for hecho in hechos:
        assert hecho.fc == pytest.approx(
            sistema.pertenencia(hecho.variable, hecho.valor, CASO_CRITICO[hecho.hecho_origen])
        )
    criticos = [hecho for hecho in hechos if hecho.valor == "crítico"]
    assert any(
        hecho.variable == "nivel_stock" and hecho.fc == pytest.approx(1.0) for hecho in criticos
    )


def test_hechos_salida_listos_para_el_motor(sistema: SistemaDifuso) -> None:
    """Las salidas se entregan como hechos con atributo, CF y trazabilidad."""
    resultado = sistema.calcular(CASO_CRITICO)
    por_variable = {hecho.variable: hecho for hecho in resultado.hechos_salida}
    assert len(resultado.hechos_salida) == len(SALIDAS_DIFUSAS)
    assert set(por_variable) == set(SALIDAS_DIFUSAS)

    riesgo = por_variable["nivel_riesgo_incumplimiento"]
    urgencia = por_variable["urgencia_accion"]
    assert riesgo.atributo == ATRIBUTO_RIESGO_DIFUSO
    assert urgencia.atributo == ATRIBUTO_URGENCIA
    assert riesgo.origen == urgencia.origen == "sistema_difuso"
    assert riesgo.valor == resultado.etiquetas[riesgo.variable]
    assert riesgo.fc == pytest.approx(resultado.grados[riesgo.variable][riesgo.valor])
    assert urgencia.fc == pytest.approx(resultado.grados[urgencia.variable][urgencia.valor])
    assert "centroide" in riesgo.detalle and "reglas activadas" in riesgo.detalle


def test_fuzzificar_ignora_datos_no_difusos_y_filtra_umbral() -> None:
    """Los hechos ajenos se ignoran y el umbral recorta pertenencias débiles."""
    sistema = SistemaDifuso(umbral=0.9)
    hechos = sistema.fuzzificar({"temporada": "alta", **CASO_CRITICO})
    assert all(hecho.hecho_origen in CASO_CRITICO for hecho in hechos)
    assert all(hecho.fc >= 0.9 for hecho in hechos)
    with pytest.raises(TypeError):
        sistema.fuzzificar({"stock_cobertura": "alto"})  # type: ignore[dict-item]
    with pytest.raises(TypeError):
        sistema.fuzzificar([])  # type: ignore[arg-type]


def test_graficos_guardados(sistema: SistemaDifuso, tmp_path: Path) -> None:
    """Se genera un PNG por variable en el directorio solicitado."""
    rutas = sistema.guardar_graficos(tmp_path)
    assert len(rutas) == len(VARIABLES_DIFUSAS)
    assert all(ruta.is_file() and ruta.stat().st_size > 0 for ruta in rutas)
    assert all(ruta.name.startswith("pertenencia_") and ruta.suffix == ".png" for ruta in rutas)


def test_cli_imprime_resumen(capsys: pytest.CaptureFixture[str]) -> None:
    """El módulo ejecutable muestra el caso, reglas y hechos simbólicos."""
    main()
    salida = capsys.readouterr().out
    assert "Sistema difuso" in salida
    assert "Reglas declaradas: 22" in salida
    assert "Hechos simbólicos" in salida
    assert "Gráficos guardados" in salida


def _variable_minima() -> VariableDifusa:
    """Variable sencilla para probar validaciones de configuración."""
    return VariableDifusa(
        (0.0, 10.0, 1.0),
        {"bajo": RegionDifusa("triangular", (0.0, 0.0, 5.0))},
    )


@pytest.mark.parametrize(
    ("variable", "mensaje"),
    [
        (VariableDifusa((0.0, 10.0), {"bajo": RegionDifusa("triangular", (0, 5, 10))}), "universo"),
        (
            VariableDifusa((10.0, 0.0, 1.0), {"bajo": RegionDifusa("triangular", (0, 5, 10))}),
            "Universo",
        ),
        (
            VariableDifusa((0.0, 10.0, 0.0), {"bajo": RegionDifusa("triangular", (0, 5, 10))}),
            "Universo",
        ),
        (VariableDifusa((0.0, 10.0, 1.0), {}), "etiqueta"),
        (VariableDifusa((0.0, 10.0, 1.0), {"bajo": RegionDifusa("curva", (0, 5, 10))}), "Tipo"),
        (VariableDifusa((0.0, 10.0, 1.0), {"bajo": RegionDifusa("triangular", (0, 5))}), "puntos"),
        (
            VariableDifusa((0.0, 10.0, 1.0), {"bajo": RegionDifusa("triangular", (5, 0, 10))}),
            "ordenados",
        ),
        (
            VariableDifusa((0.0, 10.0, 1.0), {"bajo": RegionDifusa("triangular", (0, 5, 20))}),
            "universo",
        ),
        (
            VariableDifusa((0.0, 10.0, 1.0), {"bajo": RegionDifusa("trapezoidal", (0, 5, 10, 11))}),
            "universo",
        ),
        (
            VariableDifusa((0.0, 10.0, 1.0), {"bajo": RegionDifusa("triangular", (0, "x", 10))}),
            "numéricos",
        ),
        ("no es variable", "VariableDifusa"),
    ],
)
def test_validacion_de_variables(variable: object, mensaje: str) -> None:
    """Las declaraciones de variables inválidas se rechazan al construir."""
    with pytest.raises((TypeError, ValueError), match=mensaje):
        SistemaDifuso(variables={"entrada": variable})  # type: ignore[dict-item]


def test_validacion_de_reglas_y_mapeo() -> None:
    """Se rechazan reglas vacías, duplicadas, desconocidas y mapeos inválidos."""
    variable = _variable_minima()
    salida = SALIDAS_DIFUSAS[0]
    variables = {"entrada": variable, **dict.fromkeys(SALIDAS_DIFUSAS, variable)}

    def construir(reglas: list[ReglaDifusa]) -> SistemaDifuso:
        """Construye un sistema con variables mínimas y sin mapeo de hechos."""
        return SistemaDifuso(variables=variables, reglas=reglas, mapeo={})

    regla = ReglaDifusa("RX", "Regla de prueba", {"entrada": "bajo"}, {salida: "bajo"})
    with pytest.raises(ValueError, match="regla difusa"):
        SistemaDifuso(reglas=[])
    with pytest.raises(ValueError, match="repetido"):
        construir([regla, regla])
    with pytest.raises(ValueError, match="antecedentes"):
        construir([ReglaDifusa("R", "x", {}, {salida: "bajo"})])
    with pytest.raises(ValueError, match="entrada desconocida"):
        construir([ReglaDifusa("R", "x", {"otra": "bajo"}, {salida: "bajo"})])
    with pytest.raises(ValueError, match="etiqueta desconocida"):
        construir([ReglaDifusa("R", "x", {"entrada": "x"}, {salida: "bajo"})])
    with pytest.raises(ValueError, match="salida desconocida"):
        construir([ReglaDifusa("R", "x", {"entrada": "bajo"}, {"otra_salida": "bajo"})])
    with pytest.raises(ValueError, match="etiqueta desconocida"):
        construir([ReglaDifusa("R", "x", {"entrada": "bajo"}, {salida: "x"})])
    with pytest.raises(TypeError, match="ReglaDifusa"):
        SistemaDifuso(reglas=["no es regla"])  # type: ignore[list-item]
    with pytest.raises(TypeError, match="Mapping"):
        SistemaDifuso(mapeo=[])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="variable de entrada desconocida"):
        SistemaDifuso(mapeo={"dato": "no_existe"})
    with pytest.raises(ValueError, match="umbral"):
        SistemaDifuso(umbral=1.5)
    with pytest.raises(ValueError, match="variable difusa"):
        SistemaDifuso(variables={})
    with pytest.raises(TypeError, match="Mapping"):
        SistemaDifuso(variables=[])  # type: ignore[arg-type]


def test_resultado_y_hecho_difuso(sistema: SistemaDifuso) -> None:
    """Las estructuras de resultado exponen descripciones legibles."""
    hecho = HechoDifuso("nivel_stock", "crítico", 1.0, "nivel_stock", "stock_cobertura")
    assert "desde stock_cobertura" in hecho.descripcion
    assert HechoDifuso("merma", "alta", 0.5, "merma").descripcion.count("desde") == 0
    resultado = sistema.calcular(CASO_BASE)
    assert "nivel_riesgo_incumplimiento" in resultado.descripcion()
    assert set(resultado.grados) == set(SALIDAS_DIFUSAS)
    for etiquetas in resultado.grados.values():
        assert all(0.0 <= grado <= 1.0 for grado in etiquetas.values())


def test_configuracion_no_se_muta() -> None:
    """La construcción del sistema no altera la configuración global."""
    original = deepcopy(dict(VARIABLES_DIFUSAS))
    SistemaDifuso()
    assert set(VARIABLES_DIFUSAS) == set(original)
