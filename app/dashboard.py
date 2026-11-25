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
import sys
from pathlib import Path
from typing import Any

import httpx
import plotly.graph_objects as go
import streamlit as st

# Streamlit antepone la carpeta del script al ``sys.path``. Añadir la raíz del
# proyecto garantiza que ``app`` y ``config`` se resuelvan al arrancar desde
# cualquier directorio (y evita colisiones con otros paquetes llamados ``app``).
RAIZ_PROYECTO = str(Path(__file__).resolve().parent.parent)
if RAIZ_PROYECTO not in sys.path:
    sys.path.insert(0, RAIZ_PROYECTO)

from app.visualizacion import (  # noqa: E402
    categoria_nodo,
    etiqueta,
    grafo_nodos,
    id_regla,
    linea_tiempo_nodos,
    primera_frase,
    resumen_nodos,
    ruta_solucion,
)
from config import DASHBOARD_API_URL, DASHBOARD_TIMEOUT_S  # noqa: E402

COLORES_SEMAFORO: dict[str, str] = {
    "verde": "#2e7d32",
    "amarillo": "#f9a825",
    "naranja": "#ef6c00",
    "rojo": "#c62828",
    "gris": "#757575",
}

PATRON_FACTOR = re.compile(
    r"^(?P<variable>.+?):\s*(?P<signo>[+-])(?P<valor>[\d.,]+)\s*Bs\s*\((?P<detalle>.*)\)$"
)


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
            y=[etiqueta(causa["causa"]) for causa in ordenadas],
            orientation="h",
            marker={"color": "#5e35b1"},
            text=[f"{causa['cf']:+.3f}" for causa in ordenadas],
            textposition="auto",
            hovertext=[causa["descripcion"] for causa in ordenadas],
        )
    )
    figura.update_layout(
        title="Causas diagnosticadas",
        xaxis_title="Certeza (valor absoluto)",
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
                "variable": etiqueta(coincidencia.group("variable")),
                "valor": valor,
                "detalle": etiqueta(coincidencia.group("detalle")),
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
        title="Qué explica la proyección",
        xaxis_title="Aporte a la proyección (Bs)",
        yaxis_title="Variable",
        height=max(240, 65 * len(ordenados)),
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
    )
    return figura


def grafico_benchmark(filas: list[dict[str, Any]]) -> go.Figure:
    """Compara estados evaluados por algoritmo dentro de un escenario."""
    ordenadas = sorted(filas, key=lambda fila: fila["nodos_expandidos"])
    nombres = [etiqueta(fila["algoritmo"]) for fila in ordenadas]
    figura = go.Figure(
        go.Bar(
            x=[fila["nodos_expandidos"] for fila in ordenadas],
            y=nombres,
            orientation="h",
            marker_color=["#1565c0" if fila["encontrado"] else "#90a4ae" for fila in ordenadas],
            text=nombres,
            textposition="outside",
            cliponaxis=False,
        )
    )
    figura.update_layout(
        title="Estados evaluados por algoritmo",
        xaxis_title="Estados evaluados",
        yaxis_title="Algoritmo",
        height=max(260, 45 * len(ordenadas)),
        margin={"l": 40, "r": 60, "t": 60, "b": 40},
    )
    return figura


def mostrar_decision(analisis: dict[str, Any]) -> None:
    """Muestra en primer plano qué hacer esta semana y cuánto cuesta."""
    plan = analisis["plan"]
    st.header("Decisión de esta semana", icon=":material/arrow_forward:")

    with st.container(border=True):
        if plan["encontrado"] and plan["acciones"]:
            for numero, accion in enumerate(plan["acciones"], start=1):
                st.markdown(f"**{numero}. {etiqueta(accion)}**")
            cantidad = len(plan["acciones"])
            st.caption(
                f"Inversión estimada: Bs {plan['costo_bs']:,.0f} · "
                f"{cantidad} {'acción' if cantidad == 1 else 'acciones'} · dentro del presupuesto."
            )
            if plan["justificacion"]:
                st.caption(primera_frase(plan["justificacion"]))
        elif plan["encontrado"]:
            st.success("No hace falta ninguna acción adicional.", title="Sin cambios")
        else:
            st.warning(
                "El presupuesto no alcanza para llegar a la meta. Revisa el escenario.",
                title="Sin plan disponible",
            )


def mostrar_numeros(analisis: dict[str, Any]) -> None:
    """Resume la situación con cuatro cifras y una frase de contexto."""
    prediccion = analisis["prediccion"]
    riesgo = analisis["riesgo"]
    if analisis["causas"]:
        contexto_causa = f"El diagnóstico apunta a {etiqueta(analisis['causas'][0]['causa'])}"
    else:
        contexto_causa = "El diagnóstico no encontró una causa clara"

    with st.container(horizontal=True):
        st.metric(
            "Ventas proyectadas",
            f"{prediccion['valor_predicho_bs']:,.0f} Bs",
            border=True,
        )
        st.metric("Meta", f"{analisis['proyeccion']['meta_bs']:,.0f} Bs", border=True)
        st.metric("Cumplimiento", f"{analisis['cumplimiento_pct']:.1f} %", border=True)
        st.metric("Riesgo", etiqueta(riesgo["etiqueta"]), border=True)

    st.caption(
        f"La proyección llega al {analisis['cumplimiento_pct']:.1f} % de la meta. "
        f"{contexto_causa}; el riesgo es {etiqueta(riesgo['etiqueta'])} "
        f"con urgencia {etiqueta(riesgo['urgencia'])}."
    )


def mostrar_por_que(cliente: httpx.Client, analisis: dict[str, Any]) -> None:
    """Detalle técnico de la predicción, el diagnóstico y el plan, bajo demanda."""
    with st.expander(
        "¿Por qué esta decisión?",
        icon=":material/lightbulb:",
        key="exp_detalle",
        on_change="rerun",
    ) as caja:
        if not caja.open:
            return

        st.markdown("**Diagnóstico**")
        causas = analisis["causas"]
        if not causas:
            st.info("No se diagnosticaron causas con certeza positiva.")
        else:
            st.plotly_chart(
                grafico_causas(causas),
                width="stretch",
                alt="Causas detectadas y nivel de certeza de cada una.",
            )
            st.dataframe(
                [
                    {
                        "Causa": etiqueta(causa["causa"]),
                        "Certeza": f"{causa['cf']:+.3f}",
                        "Evidencia": primera_frase(causa["descripcion"]),
                        "Reglas aplicadas": ", ".join(
                            id_regla(regla)[0] or primera_frase(id_regla(regla)[1])
                            for regla in causa["reglas"]
                        )
                        or "hecho del contexto",
                    }
                    for causa in causas
                ],
                width="stretch",
                hide_index=True,
            )

        riesgo = analisis["riesgo"]
        st.markdown("**Nivel de riesgo**")
        st.write(
            f"El nivel difuso es {riesgo['valor']:.1f} con una certeza de {riesgo['grado']:.0%}; "
            f"la urgencia es {etiqueta(riesgo['urgencia'])}."
        )
        st.caption(
            "Reglas difusas activadas: " + (", ".join(riesgo["reglas_activadas"]) or "ninguna")
        )
        st.plotly_chart(
            grafico_historico(analisis),
            width="stretch",
            alt="Evolución histórica de ventas y proyección para la semana objetivo.",
        )

        st.markdown("**Qué explica la proyección**")
        try:
            explicacion = cargar_explicacion(cliente, analisis["id"])
        except Exception as exc:
            st.error(f"No se pudo cargar la explicación: {mensaje_error(exc)}")
            explicacion = None
        if explicacion is not None:
            st.write(explicacion["texto"])
        factores = (
            explicacion["factores_shap"]
            if explicacion is not None
            else analisis["prediccion"]["principales_factores"]
        )
        datos = factores_shap_como_datos(factores)
        if datos:
            st.plotly_chart(
                grafico_shap(datos),
                width="stretch",
                alt="Aporte en bolivianos de cada variable a la proyección.",
            )
        else:
            st.warning("La API no devolvió factores interpretables para esta predicción.")
            st.caption("Datos recibidos:")
            st.code("\n".join(str(texto) for texto in factores), language="text")

        st.markdown("**Por qué se eligió este plan**")
        plan = analisis["plan"]
        if plan["justificacion"]:
            st.write(plan["justificacion"])
        else:
            st.caption("El plan se seleccionó por menor costo dentro del presupuesto.")
        if plan["restricciones"]:
            st.caption(
                "Acciones no permitidas por el diagnóstico: "
                + ", ".join(etiqueta(restriccion) for restriccion in plan["restricciones"])
            )


def mostrar_exploracion_estados(plan: dict[str, Any]) -> None:
    """Traza real de la búsqueda: grafo interactivo y línea de tiempo, bajo demanda."""
    with st.expander(
        "Cómo se exploraron las opciones",
        icon=":material/account_tree:",
        key="exp_exploracion",
        on_change="rerun",
    ) as caja:
        if not caja.open:
            return

        nodos = plan.get("nodos", [])
        if not nodos:
            st.info(
                "La respuesta actual no incluye la traza de estados. "
                "Vuelve a analizar con la API actualizada para verla."
            )
            return

        resumen = resumen_nodos(nodos)
        columnas = st.columns(4)
        columnas[0].metric("Estados evaluados", f"{resumen['expandidos']:,}")
        columnas[1].metric("Estados creados", f"{resumen['creados']:,}")
        columnas[2].metric("Descartados", f"{resumen['descartados']:,}")
        columnas[3].metric("Estados en la solución", f"{resumen['en_ruta']:,}")

        st.plotly_chart(
            grafo_nodos(nodos),
            width="stretch",
            alt="Grafo interactivo con todos los estados que la búsqueda creó y evaluó.",
        )
        st.plotly_chart(
            linea_tiempo_nodos(nodos),
            width="stretch",
            alt="Línea de tiempo del orden real de evaluación y del costo acumulado.",
        )

        camino = ruta_solucion(nodos)
        expandidos = sorted(
            (nodo for nodo in nodos if nodo.get("expandido")),
            key=lambda nodo: nodo.get("orden_expansion") or 0,
        )
        st.markdown("**Secuencia de decisiones**")
        st.dataframe(
            [
                {
                    "Orden": nodo.get("orden_expansion"),
                    "Acción": etiqueta(nodo["accion"]) if nodo.get("accion") else "Inicio",
                    "Costo (Bs)": f"{nodo.get('costo_bs', 0):,.0f}",
                    "Pasos": nodo.get("profundidad", 0),
                    "Resultado": etiqueta(categoria_nodo(nodo, camino)),
                }
                for nodo in expandidos
            ],
            width="stretch",
            hide_index=True,
            height=260,
        )
        st.caption(
            "Cada círculo es un estado real; la línea dorada es la ruta hasta la meta y "
            "los puntos grises son estados descartados. El gráfico inferior sigue el orden "
            "exacto de evaluación."
        )


def mostrar_detalle_tecnico(cliente: httpx.Client, analisis: dict[str, Any]) -> None:
    """Comparativa de algoritmos, reglas y enfoques de IA, bajo demanda."""
    with st.expander(
        "Comparación y detalle técnico",
        icon=":material/science:",
        key="exp_tecnico",
        on_change="rerun",
    ) as caja:
        if not caja.open:
            return

        st.markdown("**Comparación de algoritmos**")
        benchmark = cargar_benchmark(cliente)
        if benchmark is not None:
            escenarios = {etiqueta(nombre): nombre for nombre in benchmark["escenarios"]}
            opciones = ["Todos", *escenarios]
            seleccion = st.selectbox("Escenario", opciones, key="escenario_benchmark")
            filas = (
                benchmark["filas"]
                if seleccion == "Todos"
                else [
                    fila
                    for fila in benchmark["filas"]
                    if fila["escenario"] == escenarios[seleccion]
                ]
            )
            if filas:
                st.plotly_chart(
                    grafico_benchmark(filas),
                    width="stretch",
                    alt="Estados evaluados por cada algoritmo en los escenarios de prueba.",
                )
                st.dataframe(
                    [
                        {
                            "Algoritmo": etiqueta(fila["algoritmo"]),
                            "Escenario": etiqueta(fila["escenario"]).capitalize(),
                            "Llegó a la meta": "sí" if fila["encontrado"] else "no",
                            "Costo (Bs)": fila["costo"],
                            "Estados evaluados": fila["nodos_expandidos"],
                            "Estados creados": fila["nodos_generados"],
                            "Tiempo (s)": fila["tiempo"],
                        }
                        for fila in filas
                    ],
                    width="stretch",
                    hide_index=True,
                )

        st.markdown("**Reglas aplicadas**")
        reglas = analisis["reglas_disparadas"]
        if reglas:
            for numero, regla in enumerate(reglas, start=1):
                identificador, descripcion = id_regla(regla)
                titulo = (
                    f"**{identificador}** · {primera_frase(descripcion)}"
                    if identificador
                    else primera_frase(descripcion)
                )
                st.markdown(f"{numero:02d}. {titulo}")
            st.caption("Texto original de las reglas:")
            st.code(
                "\n".join(f"{numero:02d}. {regla}" for numero, regla in enumerate(reglas, 1)),
                language="text",
            )
        else:
            st.info("El motor no aplicó reglas en esta ejecución.")

        st.markdown("**Machine Learning y experto difuso**")
        comparativa = analisis["comparativa"]
        columnas = st.columns(2)
        with columnas[0]:
            st.markdown("**Machine Learning**")
            st.write(comparativa["aporte_ml"])
        with columnas[1]:
            st.markdown("**Experto + difuso**")
            st.write(comparativa["aporte_experto"])
        st.markdown("**Cómo se complementan**")
        st.write(comparativa["complementariedad"])
        st.caption("Evidencia de esta ejecución:")
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
        page_title="Plan de la semana | Sistema inteligente",
        page_icon="📈",
        layout="wide",
    )
    st.title("¿Qué hacemos esta semana?")
    st.caption(
        "Elige el escenario en el panel lateral y pulsa «Calcular plan». "
        "Primero verás la acción recomendada; los detalles, al final."
    )

    url_api = st.sidebar.text_input("URL base de la API", value=DASHBOARD_API_URL)
    with httpx.Client(base_url=url_api, timeout=DASHBOARD_TIMEOUT_S) as cliente:
        catalogos = cargar_catalogos(cliente)
        if catalogos is None:
            return

        st.sidebar.header("Selección")
        sucursal = st.sidebar.selectbox("Sucursal", catalogos["sucursales"])
        categoria = st.sidebar.selectbox("Categoría", catalogos["categorias"])

        st.sidebar.header("Meta y presupuesto")
        factor_meta = st.sidebar.slider(
            "Meta de ventas",
            min_value=0.70,
            max_value=1.50,
            value=1.00,
            step=0.05,
            help="1.00 es la meta base; 1.10 significa un 10 % más alta.",
        )
        presupuesto = st.sidebar.number_input(
            "Presupuesto disponible (Bs)",
            min_value=0.0,
            max_value=1_000_000.0,
            value=9000.0,
            step=500.0,
        )
        with st.sidebar.expander("Datos observados (opcional)"):
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
        calcular = st.sidebar.button("Calcular plan", type="primary")
        if calcular or st.session_state.get("clave_analisis") != clave:
            with st.spinner("Calculando el plan de la semana..."):
                try:
                    analisis = cargar_analisis(cliente, payload)
                except Exception as exc:
                    st.error(f"No se pudo completar el análisis: {mensaje_error(exc)}")
                    return
            st.session_state["analisis"] = analisis
            st.session_state["clave_analisis"] = clave

        analisis = st.session_state["analisis"]
        st.caption(
            f"{analisis['sucursal']} · {analisis['categoria']} · "
            f"semana {analisis['fecha_objetivo']}"
        )
        mostrar_decision(analisis)
        mostrar_numeros(analisis)
        mostrar_por_que(cliente, analisis)
        mostrar_exploracion_estados(analisis["plan"])
        mostrar_detalle_tecnico(cliente, analisis)


if __name__ == "__main__":
    main()
