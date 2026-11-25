"""Pruebas de la API REST con ``fastapi.testclient.TestClient``."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api.main import crear_app
from config import API_TITULO, API_VERSION
from core.fabrica import construir_sistema
from expert_system.base_conocimientos import BaseConocimientos

PETICION_BASE: dict[str, object] = {
    "sucursal": "El Alto",
    "categoria": "pollo",
    "factor_meta": 1.2,
    "stock_cobertura": 0.18,
    "afluencia_rel": 0.70,
    "merma_inicial": 14.5,
}
"""Escenario en riesgo usado por las pruebas de extremo a extremo."""


@pytest.fixture(scope="module")
def cliente() -> TestClient:
    """Aplicación real montada en ``TestClient`` para todas las pruebas."""
    with TestClient(crear_app()) as prueba:
        yield prueba


def analizar(cliente: TestClient, ruta: str = "/analisis-completo") -> dict[str, object]:
    """Ejecuta un endpoint de análisis con el escenario de prueba."""
    respuesta = cliente.post(ruta, json=PETICION_BASE)
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def test_salud(cliente: TestClient) -> None:
    """El endpoint de salud informa de los artefactos disponibles."""
    respuesta = cliente.get("/salud")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["estado"] == "saludable"
    assert datos["version"] == API_VERSION
    assert all(datos["artefactos"].values())


def test_openapi_en_espanol(cliente: TestClient) -> None:
    """La documentación automática usa título, versión y etiquetas en español."""
    esquema = cliente.get("/openapi.json").json()
    assert esquema["info"]["title"] == API_TITULO
    assert esquema["info"]["version"] == API_VERSION
    assert any(tag["name"] == "Análisis" for tag in esquema["tags"])
    assert any(tag["name"] == "Conocimiento" for tag in esquema["tags"])
    for ruta in (
        "/predecir",
        "/diagnosticar",
        "/planificar",
        "/analisis-completo",
        "/reglas",
    ):
        assert ruta in esquema["paths"]


def test_catalogos(cliente: TestClient) -> None:
    """Los catálogos alimentan los selectores del dashboard."""
    respuesta = cliente.get("/catalogos")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert "El Alto" in datos["sucursales"]
    assert "pollo" in datos["categorias"]
    assert "alta" in datos["temporadas"]


def test_predecir(cliente: TestClient) -> None:
    """``/predecir`` devuelve histórico, proyección y factores SHAP."""
    datos = analizar(cliente, "/predecir")
    assert datos["sucursal"] == "El Alto"
    assert len(datos["historial"]) == 8
    assert datos["proyeccion"]["fecha"] > datos["historial"][-1]["fecha"]
    assert 0 <= datos["prediccion"]["confianza"] <= 1
    assert isinstance(datos["prediccion"]["principales_factores"], list)


def test_diagnosticar(cliente: TestClient) -> None:
    """``/diagnosticar`` devuelve causas, riesgo y semáforo."""
    datos = analizar(cliente, "/diagnosticar")
    assert isinstance(datos["causas"], list)
    assert isinstance(datos["reglas_disparadas"], list)
    assert datos["riesgo"]["etiqueta"]
    assert datos["riesgo"]["semaforo"] in {"verde", "amarillo", "naranja", "rojo", "gris"}


def test_planificar(cliente: TestClient) -> None:
    """``/planificar`` devuelve el plan con costo y estado de búsqueda."""
    datos = analizar(cliente, "/planificar")
    plan = datos["plan"]
    assert isinstance(plan["acciones"], list)
    assert isinstance(plan["encontrado"], bool)
    assert plan["costo_bs"] >= 0
    assert plan["nodos_expandidos"] >= 0
    assert isinstance(datos["causas_consideradas"], list)


def test_analisis_completo_y_explicar(cliente: TestClient) -> None:
    """El identificador devuelto permite recuperar la explicación completa."""
    analisis = analizar(cliente)
    identificador = str(analisis["id"])
    assert analisis["explicacion"]
    assert analisis["comparativa"]["aporte_ml"]

    respuesta = cliente.get(f"/explicar/{identificador}")
    assert respuesta.status_code == 200
    explicacion = respuesta.json()
    assert explicacion["id"] == identificador
    assert explicacion["texto"] == analisis["explicacion"]
    assert explicacion["factores_shap"] == analisis["prediccion"]["principales_factores"]


def test_explicar_inexistente(cliente: TestClient) -> None:
    """Un identificador desconocido produce 404 con código aplicado."""
    respuesta = cliente.get(f"/explicar/{uuid4()}")
    assert respuesta.status_code == 404
    assert respuesta.json()["detalle"]["codigo"] == "no_encontrado"


def test_validacion_estricta(cliente: TestClient) -> None:
    """Campos desconocidos, catálogos inválidos y tipos coercibles se rechazan."""
    casos = [
        {**PETICION_BASE, "campo_desconocido": 1},
        {**PETICION_BASE, "sucursal": "Ciudad Inexistente"},
        {**PETICION_BASE, "factor_meta": 0},
        {**PETICION_BASE, "semanas": "8"},
    ]
    for caso in casos:
        respuesta = cliente.post("/predecir", json=caso)
        assert respuesta.status_code == 422, respuesta.text
        assert respuesta.json()["detalle"]["codigo"] == "validacion"


def test_benchmark(cliente: TestClient) -> None:
    """El benchmark de la Fase 5 se expone sin recalcular los algoritmos."""
    respuesta = cliente.get("/benchmark")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert len(datos["filas"]) == 28
    assert "A*" in {fila["algoritmo"] for fila in datos["filas"]}
    assert set(datos["escenarios"]) == {"facil", "medio", "dificil", "sin_solucion"}


def test_reglas(cliente: TestClient) -> None:
    """``/reglas`` entrega el catálogo completo sin ejecutar inferencia."""
    respuesta = cliente.get("/reglas")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["expertas"] == 38
    assert datos["difusas"] == 22
    assert datos["total"] == 60 == datos["expertas"] + datos["difusas"]

    por_id = {regla["id"]: regla for regla in datos["reglas"]}
    assert len(por_id) == datos["total"]
    campos = {
        "tipo",
        "id",
        "descripcion",
        "categoria",
        "si",
        "entonces",
        "certeza",
        "prioridad",
        "antecedentes",
        "consecuentes",
    }
    assert all(campos <= set(regla) for regla in datos["reglas"])

    experta = por_id["D01"]
    assert experta["tipo"] == "experta"
    assert experta["certeza"] == 0.9
    assert experta["prioridad"] == 80
    assert "stock_cobertura" in experta["si"]
    assert "stock_critico" in experta["entonces"]
    assert experta["antecedentes"]

    difusa = por_id["DF22"]
    assert difusa["tipo"] == "difusa"
    assert difusa["certeza"] is None
    assert difusa["prioridad"] is None
    assert len(difusa["antecedentes"]) == 2
    assert difusa["consecuentes"]


def test_base_reglas_inyectada() -> None:
    """La base cacheada puede inyectarse al crear la aplicación."""
    base = BaseConocimientos.desde_json()
    aplicacion = crear_app(base_reglas=base)
    assert aplicacion.state.base_reglas is base
    with TestClient(aplicacion) as prueba:
        respuesta = prueba.get("/reglas")
    assert respuesta.status_code == 200
    assert respuesta.json()["total"] == 60


def test_reglas_aplicadas_en_las_respuestas(cliente: TestClient) -> None:
    """Las respuestas incluyen las reglas reales con toda su información."""
    analisis = analizar(cliente)
    reglas = analisis["reglas_aplicadas"]
    assert isinstance(reglas, list) and reglas

    campos = {
        "orden",
        "regla_id",
        "descripcion",
        "categoria",
        "premisa",
        "cf_premisa",
        "fc_regla",
        "cf_conclusion",
        "conclusion",
        "conclusion_atributo",
        "conclusion_valor",
        "momento",
        "prioridad",
        "tipo",
    }
    assert all(campos <= set(regla) for regla in reglas)
    assert all(regla["premisa"] and regla["conclusion"] for regla in reglas)

    expertas = [regla for regla in reglas if regla["tipo"] == "experta"]
    difusas = [regla for regla in reglas if regla["tipo"] == "difusa"]
    assert expertas and difusas
    assert [regla["orden"] for regla in expertas] == list(range(1, len(expertas) + 1))
    assert any(regla["prioridad"] is not None for regla in expertas)
    assert all(regla["prioridad"] is None for regla in difusas)
    assert all(regla["fc_regla"] > 0 for regla in difusas)
    assert set(analisis["reglas_disparadas"]) <= {regla["regla_id"] for regla in expertas}

    diagnostico = analizar(cliente, "/diagnosticar")
    assert len(diagnostico["reglas_aplicadas"]) == len(reglas)

    explicacion = cliente.get(f"/explicar/{analisis['id']}").json()
    assert explicacion["reglas_aplicadas"] == reglas


def test_cors(cliente: TestClient) -> None:
    """El origen del dashboard recibe la cabecera CORS configurada."""
    respuesta = cliente.options(
        "/predecir",
        headers={
            "Origin": "http://localhost:8501",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert respuesta.status_code == 200
    assert respuesta.headers["access-control-allow-origin"] == "http://localhost:8501"


def test_salud_sin_artefactos() -> None:
    """Si falta un artefacto, ``/salud`` responde 503."""
    aplicacion = crear_app(rutas_artefactos=(Path("no_existe.joblib"),))
    with TestClient(aplicacion) as prueba:
        respuesta = prueba.get("/salud")
    assert respuesta.status_code == 503
    assert respuesta.json()["detalle"]["codigo"] == "servicio_no_disponible"


def test_fabrica_inyectada_por_app_state() -> None:
    """La fábrica configurada se usa por petición, sin globales."""
    llamadas: list[int] = []

    def fabrica_contada():  # type: ignore[no-untyped-def]
        """Cuenta las construcciones y delega en la fábrica real."""
        llamadas.append(1)
        return construir_sistema()

    aplicacion = crear_app(fabrica_sistema=fabrica_contada)
    with TestClient(aplicacion) as prueba:
        respuesta = prueba.post("/predecir", json=PETICION_BASE)
    assert respuesta.status_code == 200
    assert len(llamadas) == 1
