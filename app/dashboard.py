"""Dashboard Streamlit del sistema inteligente de predicción de ventas.

Toda la lógica de negocio vive en la API: esta interfaz solo envía parámetros,
muestra las respuestas y dibuja gráficos. No reimplementa predicción,
diagnóstico, riesgo ni planificación.

Ejecutar:

.. code-block:: powershell

    streamlit run app/dashboard.py --server.port 8501
"""

from __future__ import annotations

import re
from typing import Any

import httpx
import plotly.graph_objects as go
import streamlit as st

from config import DASHBOARD_API_URL, DASHBOARD_TIMEOUT_S

COLORES_SEMAFORO: dict[str, str] = {
    "verde": "#2e7d32",
    "amarillo": "#f9a825",
    "naranja": "#ef6c00",
    "rojo": "#c62828",
    "gris": "#757575",
}
"""Colores hexadecimales asociados a cada nivel del semáforo."""

PATRON_FACTOR = re.compile(
    r"^(?P<variable>.+?):\s*(?P<signo>[+-])(?P<valor>[\d.,]+)\s*Bs\s*\((?P<detalle>.*)\)$"
)
"""Expresión para convertir los factores SHAP legibles en barras."""


def mensaje_error(exc: Exception) -> str:
    """Convierte una excepción de ``httpx`` en un mensaje en español."""
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            cuerpo = exc.response.json()
        except ValueError:
            cuerpo = {}
        detalle = cuerpo.get("detalle", {}) if isinstance(cuerpo, dict) else {}
        if isinstance(detalle, dict):
            return str(detalle.get("mensaje", detalle.get("codigo", exc.response.reason_phrase)))
        return str(detalle)
    if isinstance(exc, httpx.RequestError):
        return (
            "No se pudo conectar con la API. Verifica que esté levantada y que la URL sea correcta."
        )
    return str(exc)


def obtener_json(
    cliente: httpx.Client,
    ruta: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Llama a la API y devuelve el cuerpo JSON, lanzando ``HTTPStatusError``."""
    respuesta = cliente.post(ruta, json=payload) if payload is not None else cliente.get(ruta)
    respuesta.raise_for_status()
    return respuesta.json()


def cargar_catalogos(cliente: httpx.Client) -> dict[str, Any] | None:
    """Obtiene los catálogos para los selectores de la barra lateral."""
    try:
        return obtener_json(cliente, "/catalogos")
    except Exception as exc:
        st.error(f"No se pudieron cargar los catálogos: {mensaje_error(exc)}")
        return None


def cargar_analisis(cliente: httpx.Client, payload: dict[str, Any]) -> dict[str, Any]:
    """Ejecuta el análisis completo en la API."""
    return obtener_json(cliente, "/analisis-completo", payload)


def cargar_explicacion(cliente: httpx.Client, identificador: str) -> dict[str, Any]:
    """Obtiene y cachea la explicación detallada de un análisis."""
    clave = f"explicacion_{identificador}"
    if clave not in st.session_state:
        st.session_state[clave] = obtener_json(cliente, f"/explicar/{identificador}")
    return st.session_state[clave]


def cargar_benchmark(cliente: httpx.Client) -> dict[str, Any] | None:
    """Obtiene y cachea el benchmark de algoritmos de búsqueda."""
    if "benchmark" not in st.session_state:
        try:
            st.session_state["benchmark"] = obtener_json(cliente, "/benchmark")
        except Exception as exc:
            st.warning(f"No se pudo cargar el benchmark: {mensaje_error(exc)}")
            return None
    return st.session_state["benchmark"]


def grafico_historico(analisis: dict[str, Any]) -> go.Figure:
    """Dibuja las ventas observadas, la meta y la proyección de la semana t+1."""
    historial = analisis["historial"]
    proyeccion = analisis["proyeccion"]
    fechas = [punto["fecha"] for punto in historial] + [proyeccion["fecha"]]
    ventas = [punto["ventas_bs"] for punto in historial] + [None]
    metas = [punto["meta_bs"] for punto in historial] + [proyeccion["meta_bs"]]

    figura = go.Figure()
    figura.add_trace(
        go.Scatter(
            x=fechas[:-1],
            y=ventas[:-1],
            mode="lines+markers",
            name="Ventas observadas",
            line={"color": "#1565c0", "width": 3},
        )
    )
    figura.add_trace(
        go.Scatter(
            x=fechas,
            y=metas,
            mode="lines",
            name="Meta semanal",
            line={"color": "#90a4ae", "dash": "dash", "width": 2},
        )
    )
    figura.add_trace(
        go.Scatter(
            x=[proyeccion["fecha"]],
            y=[proyeccion["valor_predicho_bs"]],
            mode="markers",
            name="Proyección",
            marker={"color": "#2e7d32", "size": 14, "symbol": "diamond"},
        )
    )
    figura.add_vline(x=proyeccion["fecha"], line={"color": "#b0bec5", "dash": "dot"})
    figura.update_layout(
        title="Histórico semanal versus proyección",
        xaxis_title="Semana",
        yaxis_title="Bolivianos (Bs)",
        legend={"orientation": "h", "y": -0.15},
        hovermode="x unified",
        height=420,
        margin={"l": 40, "r": 20, "t": 60, "b": 80},
    )
    return figura


def grafico_causas(causas: list[dict[str, Any]]) -> go.Figure:
    """Dibuja una barra horizontal por causa, con su certeza absoluta."""
    ordenadas = sorted(causas, key=lambda causa: abs(causa["cf"]))
    figura = go.Figure(
        go.Bar(
            x=[abs(causa["cf"]) for causa in ordenadas],
            y=[causa["causa"] for causa in ordenadas],
            orientation="h",
            marker={"color": "#5e35b1"},
            text=[f"{causa['cf']:+.3f}" for causa in ordenadas],
            textposition="auto",
            hovertext=[causa["descripcion"] for causa in ordenadas],
        )
    )
    figura.update_layout(
        title="Causas diagnosticadas (factor de certeza)",
        xaxis_title="|CF|",
        yaxis_title="Causa",
        height=max(220, 70 * len(ordenadas)),
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
    )
    return figura


def factores_shap_como_datos(factores: list[str]) -> list[dict[str, Any]]:
    """Parsea las cadenas SHAP de la API a registros para graficar."""
    datos: list[dict[str, Any]] = []
    for texto in factores:
        coincidencia = PATRON_FACTOR.match(texto)
        if coincidencia is None:
            continue
        valor = float(coincidencia.group("valor").replace(",", ""))
        if coincidencia.group("signo") == "-":
            valor = -valor
        datos.append(
            {
                "variable": coincidencia.group("variable"),
                "valor": valor,
                "detalle": coincidencia.group("detalle"),
            }
        )
    return datos


def grafico_shap(datos: list[dict[str, Any]]) -> go.Figure:
    """Dibuja el aporte de cada variable a la predicción en bolivianos."""
    ordenados = sorted(datos, key=lambda item: item["valor"])
    figura = go.Figure(
        go.Bar(
            x=[item["valor"] for item in ordenados],
            y=[item["variable"] for item in ordenados],
            orientation="h",
            marker_color=["#2e7d32" if item["valor"] >= 0 else "#c62828" for item in ordenados],
            text=[f"{item['valor']:+,.0f} Bs" for item in ordenados],
            textposition="auto",
            hovertext=[item["detalle"] for item in ordenados],
        )
    )
    figura.add_vline(x=0, line={"color": "#455a64", "width": 1})
    figura.update_layout(
        title="Aporte SHAP a la predicción",
        xaxis_title="Bs sobre la predicción",
        yaxis_title="Variable",
        height=max(240, 65 * len(ordenados)),
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
    )
    return figura


def grafico_benchmark(filas: list[dict[str, Any]]) -> go.Figure:
    """Compara nodos expandidos por algoritmo dentro de un escenario."""
    ordenadas = sorted(filas, key=lambda fila: fila["nodos_expandidos"])
    figura = go.Figure(
        go.Bar(
            x=[fila["nodos_expandidos"] for fila in ordenadas],
            y=[fila["algoritmo"] for fila in ordenadas],
            orientation="h",
            marker_color=["#1565c0" if fila["encontrado"] else "#90a4ae" for fila in ordenadas],
            text=[fila["algoritmo"] for fila in ordenadas],
            textposition="outside",
            cliponaxis=False,
        )
    )
    figura.update_layout(
        title="Nodos expandidos por algoritmo",
        xaxis_title="Nodos expandidos",
        yaxis_title="Algoritmo",
        height=max(260, 45 * len(ordenadas)),
        margin={"l": 40, "r": 60, "t": 60, "b": 40},
    )
    return figura


def mostrar_resumen(analisis: dict[str, Any]) -> None:
    """Muestra los indicadores principales y el semáforo de riesgo."""
    prediccion = analisis["prediccion"]
    riesgo = analisis["riesgo"]
    color = COLORES_SEMAFORO.get(riesgo["semaforo"], COLORES_SEMAFORO["gris"])

    st.subheader("Predicción y proyección")
    columnas = st.columns(4)
    columnas[0].metric("Ventas proyectadas", f"{prediccion['valor_predicho_bs']:,.0f} Bs")
    columnas[1].metric("Cumplimiento esperado", f"{analisis['cumplimiento_pct']:.1f} %")
    columnas[2].metric("Confianza del modelo", f"{prediccion['confianza']:.2f}")
    columnas[3].metric("Meta efectiva", f"{analisis['proyeccion']['meta_bs']:,.0f} Bs")

    st.markdown(
        f"### Semáforo de riesgo: <span style='color:{color}'>● {riesgo['etiqueta']} "
        f"({riesgo['semaforo']})</span>",
        unsafe_allow_html=True,
    )
    st.caption(
        f"Centroide {riesgo['valor']:.1f} · pertenencia {riesgo['grado']:.3f} · "
        f"urgencia: {riesgo['urgencia']}"
    )

    st.plotly_chart(grafico_historico(analisis), width="stretch")


def mostrar_diagnostico(analisis: dict[str, Any]) -> None:
    """Muestra causas con barras de certeza y el riesgo difuso."""
    st.subheader("Diagnóstico: causas y certeza")
    causas = analisis["causas"]
    if not causas:
        st.info("No se diagnosticaron causas con factor de certeza positivo.")
    else:
        st.plotly_chart(grafico_causas(causas), width="stretch")
        st.dataframe(
            [
                {
                    "Causa": causa["causa"],
                    "CF": causa["cf"],
                    "Descripción": causa["descripcion"],
                    "Reglas": ", ".join(causa["reglas"]) or "hecho del contexto",
                }
                for causa in causas
            ],
            width="stretch",
            hide_index=True,
        )
    with st.expander("Detalle del riesgo difuso"):
        st.write(analisis["riesgo"]["descripcion"])
        st.write(
            "Reglas difusas activadas: "
            + (", ".join(analisis["riesgo"]["reglas_activadas"]) or "ninguna")
        )


def mostrar_plan(analisis: dict[str, Any]) -> None:
    """Muestra el plan de acciones y su justificación."""
    st.subheader("Plan de acciones recomendado")
    plan = analisis["plan"]
    if plan["encontrado"]:
        st.success("A* encontró un plan dentro del presupuesto.")
    else:
        st.warning("A* no encontró un plan dentro del presupuesto.")
    columnas = st.columns(3)
    columnas[0].metric("Costo estimado", f"{plan['costo_bs']:,.0f} Bs")
    columnas[1].metric("Nodos expandidos", f"{plan['nodos_expandidos']:,}")
    columnas[2].metric("Acciones", str(len(plan["acciones"])))

    if plan["acciones"]:
        for numero, accion in enumerate(plan["acciones"], start=1):
            st.write(f"{numero}. {accion}")
    else:
        st.info("No se requieren acciones adicionales.")
    st.info(plan["justificacion"])
    if plan["restricciones"]:
        st.caption(
            "Operadores restringidos por el diagnóstico: " + ", ".join(plan["restricciones"])
        )


def mostrar_por_que(cliente: httpx.Client, analisis: dict[str, Any]) -> None:
    """Muestra la explicación unificada y el gráfico SHAP desde la API."""
    st.subheader("¿Por qué?")
    try:
        explicacion = cargar_explicacion(cliente, analisis["id"])
    except Exception as exc:
        st.error(f"No se pudo cargar la explicación: {mensaje_error(exc)}")
        explicacion = None

    if explicacion is not None:
        with st.expander("Explicación unificada", expanded=True):
            st.write(explicacion["texto"])

    factores = (
        explicacion["factores_shap"]
        if explicacion is not None
        else analisis["prediccion"]["principales_factores"]
    )
    datos = factores_shap_como_datos(factores)
    if datos:
        st.plotly_chart(grafico_shap(datos), width="stretch")
    else:
        st.warning("La API no devolvió factores SHAP interpretables para esta predicción.")
        for texto in factores:
            st.write(f"- {texto}")


def mostrar_pestanas(cliente: httpx.Client, analisis: dict[str, Any]) -> None:
    """Muestra las pestañas comparativa, traza de reglas y comparación de IA."""
    pestana_benchmark, pestana_reglas, pestana_ia = st.tabs(
        [
            "Comparación de algoritmos",
            "Reglas disparadas (traza)",
            "IA simbólica vs. no simbólica",
        ]
    )

    with pestana_benchmark:
        st.markdown("Métricas del benchmark de búsqueda de la Fase 5.")
        benchmark = cargar_benchmark(cliente)
        if benchmark is not None:
            opciones = ["Todos", *benchmark["escenarios"]]
            escenario = st.selectbox("Escenario", opciones, key="escenario_benchmark")
            filas = (
                benchmark["filas"]
                if escenario == "Todos"
                else [fila for fila in benchmark["filas"] if fila["escenario"] == escenario]
            )
            if filas:
                st.plotly_chart(grafico_benchmark(filas), width="stretch")
                st.dataframe(
                    [
                        {
                            "Algoritmo": fila["algoritmo"],
                            "Escenario": fila["escenario"],
                            "Encontró solución": "sí" if fila["encontrado"] else "no",
                            "Costo (Bs)": fila["costo"],
                            "Nodos expandidos": fila["nodos_expandidos"],
                            "Tiempo (s)": fila["tiempo"],
                        }
                        for fila in filas
                    ],
                    width="stretch",
                    hide_index=True,
                )

    with pestana_reglas:
        st.markdown("Reglas crisp disparadas por el motor de inferencia, en orden de ejecución.")
        reglas = analisis["reglas_disparadas"]
        if reglas:
            for numero, regla in enumerate(reglas, start=1):
                st.code(f"{numero:02d}. {regla}", language="text")
        else:
            st.info("El motor no disparó reglas crisp en esta ejecución.")
        st.caption("Las reglas difusas activadas se detallan en la sección de diagnóstico.")

    with pestana_ia:
        comparativa = analisis["comparativa"]
        columnas = st.columns(2)
        columnas[0].subheader("No simbólica (Machine Learning)")
        columnas[0].write(comparativa["aporte_ml"])
        columnas[1].subheader("Simbólica (experto + difuso)")
        columnas[1].write(comparativa["aporte_experto"])
        st.subheader("Complementariedad")
        st.write(comparativa["complementariedad"])
        st.subheader("Evidencia de esta ejecución")
        st.write(comparativa["evidencia"])


def construir_payload(
    sucursal: str,
    categoria: str,
    factor_meta: float,
    presupuesto: float,
    personalizado: bool,
    stock_cobertura: float,
    afluencia_rel: float,
    merma_inicial: float,
) -> dict[str, Any]:
    """Construye el cuerpo de la petición con los parámetros de la interfaz."""
    payload: dict[str, Any] = {
        "sucursal": sucursal,
        "categoria": categoria,
        "factor_meta": factor_meta,
        "presupuesto_bs": presupuesto,
    }
    if personalizado:
        payload.update(
            {
                "stock_cobertura": stock_cobertura,
                "afluencia_rel": afluencia_rel,
                "merma_inicial": merma_inicial,
            }
        )
    return payload


def main() -> None:
    """Punto de entrada de la aplicación Streamlit."""
    st.set_page_config(
        page_title="Predicción de ventas | Sistema inteligente",
        page_icon="📈",
        layout="wide",
    )
    st.title("Sistema inteligente de predicción de ventas")
    st.caption(
        "Predicción con SHAP, diagnóstico con factores de certeza, riesgo difuso "
        "y planificación con A*. Todos los datos provienen de la API REST."
    )

    url_api = st.sidebar.text_input("URL base de la API", value=DASHBOARD_API_URL)
    with httpx.Client(base_url=url_api, timeout=DASHBOARD_TIMEOUT_S) as cliente:
        catalogos = cargar_catalogos(cliente)
        if catalogos is None:
            return

        st.sidebar.header("Selección")
        sucursal = st.sidebar.selectbox("Sucursal", catalogos["sucursales"])
        categoria = st.sidebar.selectbox("Categoría", catalogos["categorias"])

        st.sidebar.header("Escenario")
        factor_meta = st.sidebar.slider(
            "Factor de meta", min_value=0.70, max_value=1.50, value=1.00, step=0.05
        )
        presupuesto = st.sidebar.number_input(
            "Presupuesto (Bs)",
            min_value=0.0,
            max_value=1_000_000.0,
            value=9000.0,
            step=500.0,
        )
        with st.sidebar.expander("Ajustar datos observados"):
            personalizado = st.checkbox("Personalizar escenario", value=False)
            stock_cobertura = st.number_input(
                "Cobertura de stock",
                min_value=0.0,
                max_value=5.0,
                value=0.80,
                step=0.05,
                disabled=not personalizado,
            )
            afluencia_rel = st.slider(
                "Afluencia relativa",
                min_value=0.30,
                max_value=1.60,
                value=1.00,
                step=0.05,
                disabled=not personalizado,
            )
            merma_inicial = st.slider(
                "Merma (%)",
                min_value=0.0,
                max_value=30.0,
                value=5.0,
                step=0.5,
                disabled=not personalizado,
            )

        payload = construir_payload(
            sucursal,
            categoria,
            factor_meta,
            presupuesto,
            personalizado,
            stock_cobertura,
            afluencia_rel,
            merma_inicial,
        )
        clave = (url_api, *payload.items())
        analizar = st.sidebar.button("Analizar", type="primary")
        if analizar or st.session_state.get("clave_analisis") != clave:
            with st.spinner("Consultando la API y ejecutando el sistema..."):
                try:
                    analisis = cargar_analisis(cliente, payload)
                except Exception as exc:
                    st.error(f"No se pudo completar el análisis: {mensaje_error(exc)}")
                    return
            st.session_state["analisis"] = analisis
            st.session_state["clave_analisis"] = clave

        analisis = st.session_state["analisis"]
        st.success(
            f"Análisis {analisis['id']} · {analisis['sucursal']} / "
            f"{analisis['categoria']} · semana {analisis['fecha_objetivo']}"
        )
        mostrar_resumen(analisis)
        mostrar_diagnostico(analisis)
        mostrar_plan(analisis)
        mostrar_por_que(cliente, analisis)
        mostrar_pestanas(cliente, analisis)


if __name__ == "__main__":
    main()
