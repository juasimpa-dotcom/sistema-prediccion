"""Pruebas de la traza de nodos y de las figuras del dashboard."""

from __future__ import annotations

import plotly.graph_objects as go

from api.esquemas import NodoBusquedaDTO, PlanDTO
from app.visualizacion import (
    certeza_en_palabras,
    etiqueta,
    explicacion_causa,
    grafo_nodos,
    id_regla,
    linea_tiempo_nodos,
    palanca_causa,
    primera_frase,
    resumen_benchmark,
    resumen_nodos,
    ruta_solucion,
    traducir_expresion,
)
from search.espacio_estados import ProblemaPlanComercial
from search.informada import a_estrella
from search.no_informada import busqueda_amplitud
from search.resultado import RegistroNodos


def hacer_problema() -> ProblemaPlanComercial:
    """Construye un escenario pequeño con solución conocida."""
    return ProblemaPlanComercial(
        meta_bs=12_000.0,
        presupuesto_bs=6_000.0,
        stock_inicial=400,
        merma_inicial=12.0,
    )


NODOS: list[dict[str, object]] = [
    {
        "id": 0,
        "padre_id": None,
        "estado": "Stock 400 u · descuento 0 %",
        "accion": "",
        "profundidad": 0,
        "costo_bs": 0.0,
        "heuristica": 1_400.0,
        "f": 1_400.0,
        "expandido": True,
        "es_meta": False,
        "descartado": False,
        "orden_expansion": 1,
    },
    {
        "id": 1,
        "padre_id": 0,
        "estado": "Stock 800 u · descuento 0 %",
        "accion": "reponer_stock(+400u)",
        "profundidad": 1,
        "costo_bs": 1_400.0,
        "heuristica": 0.0,
        "f": 1_400.0,
        "expandido": True,
        "es_meta": True,
        "descartado": False,
        "orden_expansion": 2,
    },
    {
        "id": 2,
        "padre_id": 0,
        "estado": "Stock 400 u · descuento 15 %",
        "accion": "reducir_merma(-3pp)",
        "profundidad": 1,
        "costo_bs": 900.0,
        "heuristica": None,
        "f": None,
        "expandido": False,
        "es_meta": False,
        "descartado": True,
        "orden_expansion": None,
    },
]


def test_a_estrella_captura_estados_reales() -> None:
    """La traza de A* incluye inicio, expansiones y meta con sus métricas."""
    resultado = a_estrella(hacer_problema())
    assert resultado.nodos
    assert resultado.nodos[0].padre_id is None
    assert sum(1 for nodo in resultado.nodos if nodo.expandido) == resultado.nodos_expandidos
    assert sum(1 for nodo in resultado.nodos if nodo.es_meta and nodo.expandido) == 1
    assert all(nodo.profundidad >= 0 for nodo in resultado.nodos)
    assert all(nodo.costo_g >= 0 for nodo in resultado.nodos)


def test_busqueda_amplitud_captura_relaciones_y_costo() -> None:
    """BFS registra el padre, la acción y el costo de cada sucesor."""
    resultado = busqueda_amplitud(hacer_problema())
    assert resultado.encontrado
    assert resultado.nodos[0].padre_id is None
    assert any(nodo.es_meta for nodo in resultado.nodos)
    for nodo in resultado.nodos[1:]:
        if nodo.padre_id is None:
            continue
        assert 0 <= nodo.padre_id < nodo.id
        assert nodo.accion


def test_registrar_expansion_no_sobrescribe_costo() -> None:
    """Marcar una expansión no debe borrar el costo acumulado del estado."""
    registro = RegistroNodos()
    registro.registrar("estado", costo_g=100.0)
    registro.registrar("estado", expandido=True, orden_expansion=3)

    nodo = registro.nodos()[0]
    assert nodo.costo_g == 100.0
    assert nodo.expandido
    assert nodo.orden_expansion == 3


def test_plan_dto_expone_la_traza() -> None:
    """El contrato REST entrega los nodos al dashboard."""
    nodo = NodoBusquedaDTO(
        id=0,
        padre_id=None,
        estado="Inicio",
        accion="",
        profundidad=0,
        costo_bs=0.0,
        heuristica=None,
        f=None,
        expandido=True,
        es_meta=False,
        descartado=False,
        orden_expansion=1,
    )
    plan = PlanDTO(
        acciones=[],
        descripcion="sin acciones",
        costo_bs=0.0,
        encontrado=True,
        nodos_expandidos=1,
        restricciones=[],
        justificacion="",
        nodos_generados=1,
        profundidad=0,
        nodos=[nodo],
    )

    assert plan.nodos[0].id == 0
    assert plan.profundidad == 0
    assert plan.nodos_generados == 1


def test_etiquetas_tradicen_identificadores_tecnicos() -> None:
    """Las claves técnicas y las acciones se muestran en lenguaje natural."""
    assert etiqueta("meta_bs") == "Meta de ventas"
    assert etiqueta("stock_cobertura") == "Cobertura de stock"
    assert etiqueta("nodos_expandidos") == "Estados evaluados"
    assert etiqueta("reponer_stock(+400u)") == "Reponer stock (+400 u)"
    assert etiqueta("num__stock_cobertura") == "Cobertura de stock"
    assert primera_frase("Primera frase. Segunda frase.") == "Primera frase."
    assert id_regla("FC01: merma_alta") == ("FC01", "merma alta")


def test_resumen_y_ruta_de_nodos() -> None:
    """Los indicadores y la ruta se derivan de la traza real."""
    assert ruta_solucion(NODOS) == {0, 1}
    assert resumen_nodos(NODOS) == {
        "expandidos": 2,
        "creados": 3,
        "descartados": 1,
        "en_ruta": 2,
    }


def test_certeza_en_palabras() -> None:
    """La certeza se comunica sin números en la explicación principal."""
    assert certeza_en_palabras(0.88) == "alta"
    assert certeza_en_palabras(0.75) == "alta"
    assert certeza_en_palabras(0.60) == "media"
    assert certeza_en_palabras(0.45) == "media"
    assert certeza_en_palabras(0.20) == "baja"
    assert certeza_en_palabras(-0.80) == "baja"


def test_traducir_expresion_de_reglas() -> None:
    """Las condiciones y conclusiones se leen en español."""
    assert (
        traducir_expresion("(stock_cobertura < 0.35 Y ventas_caida_pct > 8)")
        == "(Cobertura de stock es menor que 0.35 y Caída de ventas (%) es mayor que 8)"
    )
    assert (
        traducir_expresion("causa_ventas_bajas=stock_critico")
        == "Causa de la caída = stock crítico"
    )
    assert traducir_expresion("(urgencia_accion es alta)") == "(Urgencia de acción es alta)"
    assert (
        traducir_expresion("cumplimiento_esperado = bajo Y nivel_stock = excesivo")
        == "Cumplimiento esperado = bajo y Nivel de stock = excesivo"
    )


def test_explicacion_y_palanca_de_causas() -> None:
    """Cada causa dice qué significa y qué acción abre o cierra."""
    assert "poco stock" in explicacion_causa("stock_critico")
    assert explicacion_causa("causa_no_catalogada").startswith("El sistema detectó")

    assert palanca_causa("merma_alta", ()) == "Permite: Reducir merma."
    assert palanca_causa("merma_alta", ("permitir_reducir_merma",)) == "Bloquea: Reducir merma."
    assert (
        palanca_causa("exceso_stock", ("permitir_reasignacion",))
        == "Bloquea: Reasignar inventario."
    )
    assert "Permite" in palanca_causa("competencia_precios", ())


def test_resumen_benchmark_dice_quien_gana_y_quien_no_llega() -> None:
    """El resumen responde la pregunta del usuario sin leer barras."""
    filas = [
        {
            "algoritmo": "A*",
            "escenario": "facil",
            "encontrado": True,
            "costo": 1400.0,
            "tiempo": 0.0072,
        },
        {
            "algoritmo": "Greedy",
            "escenario": "facil",
            "encontrado": True,
            "costo": 1400.0,
            "tiempo": 0.0004,
        },
        {
            "algoritmo": "BFS",
            "escenario": "facil",
            "encontrado": False,
            "costo": 0.0,
            "tiempo": 0.5,
        },
    ]
    resumen = resumen_benchmark(filas)
    assert resumen["mejores_ids"] == ("A*", "Greedy")
    assert resumen["mejor_costo"] == 1400.0
    assert resumen["rapido_id"] == "Greedy"
    assert resumen["sin_solucion_ids"] == ("BFS",)
    assert "El plan más barato lo logran" in resumen["frase"]
    assert "Voraz (Greedy)" in resumen["frase"]
    assert "No llegan: Amplitud (BFS)" in resumen["frase"]

    sin_plan = resumen_benchmark([filas[2]])
    assert sin_plan["mejores_ids"] == ()
    assert sin_plan["mejor_costo"] is None
    assert "Ningún algoritmo llega a la meta" in sin_plan["frase"]


def test_figuras_de_la_traza_son_plotly_y_usan_etiquetas() -> None:
    """El grafo y la línea de tiempo dibujan nodos sin claves técnicas."""
    grafo = grafo_nodos(NODOS)
    linea = linea_tiempo_nodos(NODOS)

    assert isinstance(grafo, go.Figure)
    assert isinstance(linea, go.Figure)
    assert len(grafo.data) >= 3
    assert any("Reponer stock" in str(getattr(traza, "hovertext", "")) for traza in grafo.data)
    assert list(linea.data[0].x) == [1, 2]
