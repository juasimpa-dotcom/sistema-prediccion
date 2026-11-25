"""Utilidades visuales del dashboard: etiquetas legibles y figuras de búsqueda.

Este módulo no ejecuta lógica de negocio. Solo traduce los identificadores que
llegan de la API y dibuja la traza de nodos que los algoritmos ya registraron.
"""

from __future__ import annotations

import html
import re
from collections.abc import Sequence
from typing import Any

import plotly.graph_objects as go

ETIQUETAS: dict[str, str] = {
    # Campos de la API y del modelo.
    "meta_bs": "Meta de ventas",
    "meta_ventas_bs": "Meta de ventas",
    "cumplimiento_meta_pct": "Cumplimiento de la meta",
    "cumplimiento_esperado_pct": "Cumplimiento esperado",
    "cumplimiento_pct": "Cumplimiento esperado",
    "ventas_bs": "Ventas",
    "valor_predicho_bs": "Ventas proyectadas",
    "stock_cobertura": "Cobertura de stock",
    "stock_inicial": "Stock inicial",
    "nivel_stock": "Nivel de stock",
    "ventas_caida_pct": "Caída de ventas (%)",
    "merma_pct": "Merma",
    "merma": "Merma",
    "temperatura_media": "Temperatura promedio",
    "afluencia_rel": "Afluencia relativa",
    "afluencia": "Afluencia",
    "afluencia_clientes": "Afluencia de clientes",
    "precio_vs_competencia": "Precio frente a la competencia",
    "descuento_pct": "Descuento",
    "es_perecible": "Producto perecible",
    "es_feriado": "Semana con feriado",
    "es_feriado_semana": "Semana con feriado",
    "en_promocion": "En promoción",
    "temporada": "Temporada",
    "hay_excedente_en_otra_sucursal": "Excedente en otra sucursal",
    "reabastecimiento_tardia": "Reposición tardía",
    "personal_rel": "Personal disponible",
    "personal_asignado": "Personal asignado",
    "fecha_semana": "Semana",
    "fecha_objetivo": "Semana objetivo",
    "costo_bs": "Costo",
    "nodos_expandidos": "Estados evaluados",
    "nodos_generados": "Estados creados",
    "nodos": "Estados explorados",
    "profundidad": "Pasos desde el inicio",
    "causa_ventas_bajas": "Causa de la caída",
    "causas": "Causas diagnosticadas",
    "nivel_riesgo": "Nivel de riesgo",
    "nivel_riesgo_difuso": "Riesgo difuso",
    "riesgo": "Riesgo",
    "urgencia_accion": "Urgencia de acción",
    "accion_recomendada": "Acción recomendada",
    "reglas_disparadas": "Reglas aplicadas",
    "reglas_activadas": "Reglas activadas",
    "heuristica": "Estimación restante",
    "meta": "Meta",
    "ruta": "Ruta de la solución",
    "generado": "Creado",
    "descartado": "Descartado",
    "expandido": "Evaluado",
    # Causas y valores del dominio.
    "stock_critico": "stock crítico",
    "operacion_critica": "operación crítica",
    "merma_alta": "merma alta",
    "baja_afluencia": "baja afluencia",
    "competencia_precios": "competencia por precios",
    "falta_promocion": "falta de promoción",
    "exceso_stock": "exceso de stock",
    "estacionalidad": "estacionalidad",
    "alto": "alto",
    "medio": "medio",
    "bajo": "bajo",
    "nulo": "nulo",
    "critico": "crítico",
    "ninguna": "ninguna",
    "verde": "verde",
    "amarillo": "amarillo",
    "naranja": "naranja",
    "gris": "gris",
    # Restricciones del planificador.
    "permitir_reasignacion": "reasignación de inventario",
    "permitir_reducir_merma": "reducción de merma",
    # Variables lingüísticas y categorías de reglas.
    "cumplimiento_esperado": "Cumplimiento esperado",
    "intensidad_promocion": "Intensidad de la promoción",
    "nivel_riesgo_incumplimiento": "Nivel de riesgo de incumplimiento",
    "diagnostico": "diagnóstico",
    "recomendacion": "recomendación",
    "difuso": "difusa",
    "puente_difuso": "puente difuso",
    "experta": "experta",
    "difusa": "difusa",
    "adecuado": "adecuado",
    "excesivo": "excesivo",
    "normal": "normal",
    "moderada": "moderada",
    "fuerte": "fuerte",
    "sí": "sí",
    "no": "no",
    # Algoritmos y escenarios del benchmark.
    "BFS": "Amplitud (BFS)",
    "DFS": "Profundidad (DFS)",
    "Backtracking": "Retroceso",
    "Costo uniforme": "Costo uniforme",
    "Greedy": "Voraz (Greedy)",
    "A*": "A*",
    "A* (h=0)": "A* sin heurística",
    "facil": "Fácil",
    "dificil": "Difícil",
    "sin_solucion": "Sin solución",
}

ACCIONES: dict[str, str] = {
    "reponer_stock": "Reponer stock",
    "reasignar_inventario": "Reasignar inventario",
    "reducir_merma": "Reducir merma",
    "reforzar_personal": "Reforzar personal",
    "lanzar_promocion": "Lanzar promoción",
    "promocion": "Promoción",
    "mantener_plan": "Mantener plan",
    "sin_acciones": "Sin acciones",
    "reponer_stock_urgente": "Reponer stock urgente",
    "reducir_pedido_perecible": "Reducir pedido de producto perecible",
    "ajustar_precio": "Ajustar precio",
}

PATRON_ACCION = re.compile(r"^(?P<nombre>[a-z_]+)\((?P<detalle>[^)]*)\)$")
PATRON_CAMPO = re.compile(r"^(?P<variable>[a-zA-Z_]+)=(?P<valor>.+)$")
PATRON_VARIABLE_SHAP = re.compile(r"^(?P<tipo>num|cat)__(?P<nombre>.+)$")
PATRON_IDENTIFICADOR = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
OPERADORES_TEXTO: tuple[tuple[str, str], ...] = (
    (">=", " es al menos "),
    ("<=", " es como máximo "),
    (">", " es mayor que "),
    ("<", " es menor que "),
)

COLORES_NODO: dict[str, str] = {
    "meta": "#2e7d32",
    "ruta": "#f9a825",
    "expandido": "#1565c0",
    "descartado": "#b0bec5",
    "generado": "#eceff1",
}


def etiqueta(valor: object) -> str:
    """Convierte un identificador técnico en texto comprensible."""
    texto = str(valor).strip()
    if not texto:
        return "—"
    if texto in ETIQUETAS:
        return ETIQUETAS[texto]
    if texto in ACCIONES:
        return ACCIONES[texto]

    coincidencia_campo = PATRON_CAMPO.match(texto)
    if coincidencia_campo:
        variable = etiqueta(coincidencia_campo.group("variable"))
        return f"{variable}: {etiqueta(coincidencia_campo.group('valor'))}"

    coincidencia_accion = PATRON_ACCION.match(texto)
    if coincidencia_accion:
        nombre = coincidencia_accion.group("nombre")
        detalle = coincidencia_accion.group("detalle")
        base = ACCIONES.get(nombre, etiqueta(nombre))
        detalle_legible = detalle.replace("u", " u").replace("pp", " pp").replace("%", " %").strip()
        return f"{base} ({detalle_legible})" if detalle_legible else base

    variable_shap = PATRON_VARIABLE_SHAP.match(texto)
    if variable_shap:
        base = etiqueta(variable_shap.group("nombre"))
        return base[0].upper() + base[1:] if base else texto

    if "_" in texto:
        return " ".join(etiqueta(parte) for parte in texto.split("_"))
    return texto


def primera_frase(texto: str) -> str:
    """Devuelve la primera frase de un párrafo largo."""
    limpio = " ".join(texto.split())
    for separador in (". ", ".\n", "!"):
        if separador in limpio:
            return limpio.split(separador, 1)[0].rstrip(".") + "."
    return limpio


def id_regla(texto: str) -> tuple[str, str]:
    """Separa el identificador de una regla de su descripción."""
    coincidencia = re.match(r"^(?P<id>[A-Z]+\d+)\s*[:\-–]?\s*(?P<resto>.*)$", texto.strip())
    if coincidencia is None:
        return "", etiqueta(texto)
    return coincidencia.group("id"), etiqueta(coincidencia.group("resto"))


def certeza_en_palabras(valor: float) -> str:
    """Traduce un factor de certeza a alta, media o baja."""
    if valor >= 0.75:
        return "alta"
    if valor >= 0.45:
        return "media"
    return "baja"


def _capitalizar(texto: str) -> str:
    """Pone en mayúscula la primera letra, aunque el texto empiece por paréntesis."""
    for indice, caracter in enumerate(texto):
        if caracter.isalpha():
            return texto[:indice] + caracter.upper() + texto[indice + 1 :]
    return texto


def traducir_expresion(texto: str) -> str:
    """Traduce una condición o conclusión de regla a lenguaje natural."""
    resultado = texto.strip()
    resultado = re.sub(r"\bes\s+True\b", "= sí", resultado, flags=re.IGNORECASE)
    resultado = re.sub(r"\bes\s+False\b", "= no", resultado, flags=re.IGNORECASE)
    for operador, nombre in OPERADORES_TEXTO:
        resultado = resultado.replace(operador, nombre)
    resultado = re.sub(r"\bno está en\b", "no está entre", resultado)
    resultado = re.sub(r"\bestá en\b", "está entre", resultado)
    resultado = re.sub(r"\bY\b", "y", resultado)
    resultado = re.sub(r"\bO\b", "o", resultado)
    resultado = re.sub(r"\s*=\s*", " = ", resultado)
    resultado = PATRON_IDENTIFICADOR.sub(
        lambda coincidencia: etiqueta(coincidencia.group(0)), resultado
    )
    resultado = re.sub(r"\s+", " ", resultado).strip()
    return _capitalizar(resultado)


EXPLICACION_CAUSAS: dict[str, str] = {
    "stock_critico": "Queda poco stock para la demanda esperada: no alcanza a cubrir la semana.",
    "operacion_critica": "Varias señales de la operación están en nivel crítico al mismo tiempo.",
    "merma_alta": "Se pierde una parte alta del producto antes de poder venderlo.",
    "baja_afluencia": "Entraron menos clientes de lo esperado en la sucursal.",
    "competencia_precios": "Nuestro precio quedó por encima del precio de la competencia.",
    "falta_promocion": "No hubo una promoción que incentive la compra esta semana.",
    "exceso_stock": (
        "Quedó más stock del que se podía vender; el dinero está inmovilizado en inventario."
    ),
    "estacionalidad": "La temporada del año reduce o aumenta la demanda de esta categoría.",
}
"""Explicación breve de cada causa para una audiencia sin conocimientos técnicos."""

PALANCAS_CAUSA: dict[str, tuple[str, ...]] = {
    "stock_critico": ("reponer_stock", "reasignar_inventario"),
    "operacion_critica": ("reponer_stock", "reforzar_personal"),
    "merma_alta": ("reducir_merma",),
    "baja_afluencia": ("lanzar_promocion", "reforzar_personal"),
    "competencia_precios": ("lanzar_promocion", "ajustar_precio"),
    "falta_promocion": ("lanzar_promocion",),
    "exceso_stock": ("reasignar_inventario",),
    "estacionalidad": ("reforzar_personal", "reponer_stock"),
}
"""Palancas comerciales que cada causa habilita o descarta."""

RESTRICCION_POR_PALANCA: dict[str, str] = {
    "reasignar_inventario": "permitir_reasignacion",
    "reducir_merma": "permitir_reducir_merma",
}


def explicacion_causa(causa: str) -> str:
    """Devuelve qué significa una causa en lenguaje sencillo."""
    return EXPLICACION_CAUSAS.get(
        causa,
        "El sistema detectó una señal que influye en la venta esperada.",
    )


def palanca_causa(causa: str, restricciones: Sequence[str]) -> str:
    """Explica qué acción permite o bloquea una causa dado el diagnóstico."""
    permitidas: list[str] = []
    bloqueadas: list[str] = []
    for palanca in PALANCAS_CAUSA.get(causa, ()):
        nombre = etiqueta(palanca)
        restriccion = RESTRICCION_POR_PALANCA.get(palanca)
        if restriccion is not None and restriccion in restricciones:
            bloqueadas.append(nombre)
        else:
            permitidas.append(nombre)
    if permitidas and bloqueadas:
        return f"Permite: {', '.join(permitidas)}. Bloquea: {', '.join(bloqueadas)}."
    if permitidas:
        return f"Permite: {', '.join(permitidas)}."
    if bloqueadas:
        return f"Bloquea: {', '.join(bloqueadas)}."
    return "Aporta contexto, sin abrir ni cerrar una palanca concreta."


def resumen_benchmark(filas: list[dict[str, Any]]) -> dict[str, Any]:
    """Resume qué algoritmo da el mejor plan, cuál es rápido y cuál no llega."""
    exitosas = [fila for fila in filas if fila.get("encontrado")]
    sin_solucion = [fila for fila in filas if not fila.get("encontrado")]
    nombres_sin = [etiqueta(fila["algoritmo"]) for fila in sin_solucion]

    if not exitosas:
        frase = (
            "Ningún algoritmo llega a la meta en este escenario: "
            "el presupuesto o las acciones disponibles no alcanzan."
        )
        if nombres_sin:
            frase += f" No llegan: {', '.join(nombres_sin)}."
        return {
            "frase": frase,
            "mejores_ids": (),
            "mejor_costo": None,
            "rapido_id": None,
            "sin_solucion_ids": tuple(fila["algoritmo"] for fila in sin_solucion),
        }

    costo_minimo = min(float(fila["costo"]) for fila in exitosas)
    mejores_ids = tuple(
        fila["algoritmo"] for fila in exitosas if float(fila["costo"]) == costo_minimo
    )
    mejores = ", ".join(etiqueta(identificador) for identificador in mejores_ids)
    verbo = "lo logran" if len(mejores_ids) > 1 else "lo logra"
    rapida = min(exitosas, key=lambda fila: float(fila["tiempo"]))
    nombre_rapido = etiqueta(rapida["algoritmo"])
    frase = (
        f"El plan más barato {verbo} {mejores} con Bs {costo_minimo:,.0f}. "
        f"El más rápido entre quienes llegan es {nombre_rapido} "
        f"({float(rapida['tiempo']):.4f} s)"
    )
    if float(rapida["costo"]) > costo_minimo:
        frase += f", pero su plan cuesta Bs {float(rapida['costo']):,.0f}"
    frase += "."
    if nombres_sin:
        frase += f" No llegan: {', '.join(nombres_sin)}."
    return {
        "frase": frase,
        "mejores_ids": mejores_ids,
        "mejor_costo": costo_minimo,
        "rapido_id": rapida["algoritmo"],
        "sin_solucion_ids": tuple(fila["algoritmo"] for fila in sin_solucion),
    }


def ruta_solucion(nodos: list[dict[str, Any]]) -> set[int]:
    """Devuelve los identificadores del camino desde el inicio hasta la meta."""
    por_id = {nodo["id"]: nodo for nodo in nodos}
    meta = next(
        (nodo for nodo in nodos if nodo.get("es_meta") and nodo.get("expandido")),
        None,
    )
    if meta is None:
        meta = next((nodo for nodo in reversed(nodos) if nodo.get("expandido")), None)
    if meta is None:
        return set()

    camino: set[int] = set()
    actual: dict[str, Any] | None = meta
    while actual is not None and actual["id"] not in camino:
        camino.add(actual["id"])
        padre_id = actual.get("padre_id")
        actual = por_id.get(padre_id) if padre_id is not None else None
    return camino


def categoria_nodo(nodo: dict[str, Any], camino: set[int]) -> str:
    """Clasifica un nodo para asignarle color y prioridad visual."""
    if nodo.get("es_meta"):
        return "meta"
    if nodo["id"] in camino:
        return "ruta"
    if nodo.get("descartado"):
        return "descartado"
    if nodo.get("expandido"):
        return "expandido"
    return "generado"


def _posiciones(nodos: list[dict[str, Any]]) -> dict[int, tuple[float, float]]:
    """Coloca los nodos por profundidad, repartidos verticalmente."""
    por_nivel: dict[int, list[dict[str, Any]]] = {}
    for nodo in nodos:
        por_nivel.setdefault(nodo["profundidad"], []).append(nodo)

    posiciones: dict[int, tuple[float, float]] = {}
    for profundidad, grupo in por_nivel.items():
        grupo_ordenado = sorted(grupo, key=lambda nodo: nodo["id"])
        total = len(grupo_ordenado)
        for indice, nodo in enumerate(grupo_ordenado):
            y = (indice - (total - 1) / 2) * 1.6
            posiciones[nodo["id"]] = (float(profundidad), float(y))
    return posiciones


def _texto_flotante(nodo: dict[str, Any]) -> str:
    """Construye el tooltip de un nodo sin exponer claves técnicas."""
    lineas = [
        f"<b>Estado {nodo['id']}</b>",
        html.escape(str(nodo.get("estado", ""))),
        f"Acción: {html.escape(etiqueta(nodo.get('accion', '')))}",
        f"Costo acumulado: Bs {nodo.get('costo_bs', 0):,.0f}",
        f"Pasos desde el inicio: {nodo.get('profundidad', 0)}",
    ]
    if nodo.get("heuristica") is not None:
        lineas.append(f"Estimación restante: Bs {nodo['heuristica']:,.0f}")
    return "<br>".join(lineas)


def grafo_nodos(nodos: list[dict[str, Any]]) -> go.Figure:
    """Dibuja el árbol de estados explorados por A*."""
    figura = go.Figure()
    if not nodos:
        figura.add_annotation(text="No hay estados registrados", showarrow=False)
        return figura

    posiciones = _posiciones(nodos)
    camino = ruta_solucion(nodos)
    por_id = {nodo["id"]: nodo for nodo in nodos}

    normales_x: list[float | None] = []
    normales_y: list[float | None] = []
    ruta_x: list[float | None] = []
    ruta_y: list[float | None] = []
    for nodo in nodos:
        padre_id = nodo.get("padre_id")
        if padre_id not in por_id or nodo["id"] not in posiciones:
            continue
        x0, y0 = posiciones[padre_id]
        x1, y1 = posiciones[nodo["id"]]
        destino_x, destino_y = (
            (ruta_x, ruta_y)
            if nodo["id"] in camino and padre_id in camino
            else (normales_x, normales_y)
        )
        destino_x.extend([x0, x1, None])
        destino_y.extend([y0, y1, None])

    figura.add_trace(
        go.Scatter(
            x=normales_x,
            y=normales_y,
            mode="lines",
            line={"color": "#cfd8dc", "width": 1},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    figura.add_trace(
        go.Scatter(
            x=ruta_x,
            y=ruta_y,
            mode="lines",
            line={"color": COLORES_NODO["ruta"], "width": 3},
            hoverinfo="skip",
            name="Plan elegido",
        )
    )

    for categoria, color in COLORES_NODO.items():
        grupo = [nodo for nodo in nodos if categoria_nodo(nodo, camino) == categoria]
        if not grupo:
            continue
        figura.add_trace(
            go.Scatter(
                x=[posiciones[nodo["id"]][0] for nodo in grupo],
                y=[posiciones[nodo["id"]][1] for nodo in grupo],
                mode="markers+text",
                name={
                    "meta": "Meta alcanzada",
                    "ruta": "Plan elegido",
                    "expandido": "Evaluado",
                    "descartado": "Descartado",
                    "generado": "Creado",
                }[categoria],
                marker={
                    "size": 16 if categoria in {"meta", "ruta"} else 11,
                    "color": color,
                    "line": {"color": "#455a64", "width": 1},
                },
                text=[f"#{nodo['id']}" for nodo in grupo],
                textposition="top center",
                textfont={"size": 9},
                hovertext=[_texto_flotante(nodo) for nodo in grupo],
                hoverinfo="text",
            )
        )

    figura.update_layout(
        title="Exploración de estados hasta la meta",
        xaxis_title="Pasos desde el inicio",
        yaxis_title="Ramas exploradas",
        xaxis={"zeroline": False, "showgrid": False},
        yaxis={"showticklabels": False, "showgrid": False},
        height=460,
        hovermode="closest",
        margin={"l": 30, "r": 20, "t": 60, "b": 70},
        legend={"orientation": "h", "y": -0.18},
    )
    return figura


def linea_tiempo_nodos(nodos: list[dict[str, Any]]) -> go.Figure:
    """Dibuja el costo acumulado de cada expansión, en orden cronológico."""
    expandidos = sorted(
        (nodo for nodo in nodos if nodo.get("expandido")),
        key=lambda nodo: nodo.get("orden_expansion") or 0,
    )
    figura = go.Figure()
    if not expandidos:
        figura.add_annotation(text="No hay expansiones registradas", showarrow=False)
        return figura

    camino = ruta_solucion(nodos)
    categoria = [categoria_nodo(nodo, camino) for nodo in expandidos]
    figura.add_trace(
        go.Scatter(
            x=[nodo.get("orden_expansion") for nodo in expandidos],
            y=[nodo.get("costo_bs", 0) for nodo in expandidos],
            mode="lines+markers",
            line={"color": "#90a4ae", "width": 2},
            marker={
                "size": 11,
                "color": [COLORES_NODO[cat] for cat in categoria],
                "line": {"color": "#455a64", "width": 1},
            },
            hovertext=[_texto_flotante(nodo) for nodo in expandidos],
            hoverinfo="text",
            name="Costo acumulado",
        )
    )
    figura.update_layout(
        title="Secuencia de estados evaluados",
        xaxis_title="Orden de evaluación",
        yaxis_title="Costo acumulado (Bs)",
        height=300,
        margin={"l": 50, "r": 20, "t": 60, "b": 50},
        showlegend=False,
    )
    return figura


def resumen_nodos(nodos: list[dict[str, Any]]) -> dict[str, int]:
    """Devuelve conteos simples para los indicadores de la vista."""
    return {
        "expandidos": sum(1 for nodo in nodos if nodo.get("expandido")),
        "creados": len(nodos),
        "descartados": sum(1 for nodo in nodos if nodo.get("descartado")),
        "en_ruta": len(ruta_solucion(nodos)),
    }
