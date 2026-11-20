"""Configuración central del proyecto de predicción de ventas.

Concentra rutas, semilla, catálogos del dominio y parámetros del generador de
datos. Ningún otro módulo debe declarar rutas, semillas ni constantes de
negocio por su cuenta.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final

# ---------------------------------------------------------------------------
# Rutas del proyecto
# ---------------------------------------------------------------------------
RAIZ_PROYECTO: Final[Path] = Path(__file__).resolve().parent
DIR_DATOS: Final[Path] = RAIZ_PROYECTO / "data"
DIR_DATOS_CRUDOS: Final[Path] = DIR_DATOS / "raw"
DIR_DATOS_PROCESADOS: Final[Path] = DIR_DATOS / "processed"
DIR_MODELOS: Final[Path] = RAIZ_PROYECTO / "models"
DIR_DOCS: Final[Path] = RAIZ_PROYECTO / "docs"
DIR_NOTEBOOKS: Final[Path] = RAIZ_PROYECTO / "notebooks"
DIR_FIGURAS: Final[Path] = DIR_NOTEBOOKS / "figuras"
DIR_FIGURAS_DIFUSAS: Final[Path] = DIR_DOCS / "figuras"

ARCHIVO_VENTAS_CRUDO: Final[Path] = DIR_DATOS_CRUDOS / "ventas_semanales.csv"

# Artefactos de la Fase 2.
ARCHIVO_MODELO: Final[Path] = DIR_MODELOS / "predictor_ventas.joblib"
ARCHIVO_COMPARACION: Final[Path] = DIR_DOCS / "comparacion_modelos.csv"
ARCHIVO_COMPARACION_MD: Final[Path] = DIR_DOCS / "comparacion_modelos.md"
ARCHIVO_METRICAS: Final[Path] = DIR_DOCS / "metricas_modelo.json"
ARCHIVO_IMPORTANCIAS: Final[Path] = DIR_DOCS / "importancia_variables.csv"
DIR_FIGURAS_MODELOS: Final[Path] = DIR_DOCS / "figuras"

# ---------------------------------------------------------------------------
# Reproducibilidad
# ---------------------------------------------------------------------------
SEMILLA: Final[int] = 2026

# ---------------------------------------------------------------------------
# Catálogos del dominio
# ---------------------------------------------------------------------------
SUCURSALES: Final[tuple[str, ...]] = (
    "Sopocachi",
    "El Alto",
    "Miraflores",
    "Calacoto",
    "Obrajes",
    "San Pedro",
)

CATEGORIAS: Final[tuple[str, ...]] = ("pollo", "cerdo", "embutidos", "congelados")

TEMPORADAS: Final[tuple[str, ...]] = ("alta", "media", "baja")

COLUMNAS_DATASET: Final[tuple[str, ...]] = (
    "fecha_semana",
    "sucursal",
    "categoria",
    "ventas_bs",
    "unidades_vendidas",
    "precio_promedio",
    "en_promocion",
    "descuento_pct",
    "stock_inicial",
    "merma_pct",
    "temporada",
    "es_feriado_semana",
    "temperatura_media",
    "afluencia_clientes",
    "personal_asignado",
    "meta_ventas_bs",
    "cumplimiento_meta_pct",
)

# Columnas que nunca deben quedar vacías: identifican la observación y el
# resultado del negocio.
COLUMNAS_CRITICAS: Final[tuple[str, ...]] = (
    "fecha_semana",
    "sucursal",
    "categoria",
    "ventas_bs",
    "unidades_vendidas",
    "meta_ventas_bs",
)

# Columnas donde se inyectan valores faltantes para practicar la limpieza.
COLUMNAS_CON_FALTANTES: Final[tuple[str, ...]] = (
    "stock_inicial",
    "merma_pct",
    "temperatura_media",
    "afluencia_clientes",
    "personal_asignado",
    "descuento_pct",
)

# ---------------------------------------------------------------------------
# Parámetros estructurales de las sucursales y categorías
# ---------------------------------------------------------------------------
# Afluencia semanal esperada de clientes por sucursal.
AFLUENCIA_BASE_SUCURSAL: Final[dict[str, float]] = {
    "Sopocachi": 8_200.0,
    "El Alto": 12_500.0,
    "Miraflores": 9_000.0,
    "Calacoto": 6_200.0,
    "Obrajes": 7_000.0,
    "San Pedro": 9_800.0,
}

# Las sucursales de mayor poder adquisitivo sostienen precios más altos.
FACTOR_PRECIO_SUCURSAL: Final[dict[str, float]] = {
    "Sopocachi": 1.00,
    "El Alto": 0.94,
    "Miraflores": 0.98,
    "Calacoto": 1.12,
    "Obrajes": 1.02,
    "San Pedro": 0.96,
}

# Qué tan exigente es la meta de cada sucursal: valores altos = meta más fácil.
FACTOR_META_SUCURSAL: Final[dict[str, float]] = {
    "Sopocachi": 1.02,
    "El Alto": 1.10,
    "Miraflores": 1.05,
    "Calacoto": 0.96,
    "Obrajes": 0.98,
    "San Pedro": 1.04,
}

# Clientes que terminan comprando por categoría (conversión de afluencia).
TASA_CONVERSION_CATEGORIA: Final[dict[str, float]] = {
    "pollo": 0.085,
    "cerdo": 0.042,
    "embutidos": 0.060,
    "congelados": 0.028,
}

PRECIO_BASE_CATEGORIA: Final[dict[str, float]] = {
    "pollo": 24.5,
    "cerdo": 38.0,
    "embutidos": 19.5,
    "congelados": 31.0,
}

# Merma semanal típica (porcentaje del stock) y su variabilidad.
MERMA_BASE_CATEGORIA: Final[dict[str, float]] = {
    "pollo": 5.5,
    "cerdo": 4.2,
    "embutidos": 3.0,
    "congelados": 2.0,
}

MERMA_DESVIO_CATEGORIA: Final[dict[str, float]] = {
    "pollo": 1.6,
    "cerdo": 1.3,
    "embutidos": 1.0,
    "congelados": 0.8,
}

# Dotación base de personal por categoría y sucursal.
PERSONAL_BASE_CATEGORIA: Final[dict[str, int]] = {
    "pollo": 4,
    "cerdo": 3,
    "embutidos": 3,
    "congelados": 2,
}

# La altura modifica la temperatura percibida en cada sucursal.
AJUSTE_TEMPERATURA_SUCURSAL: Final[dict[str, float]] = {
    "Sopocachi": 0.0,
    "El Alto": -3.0,
    "Miraflores": 0.0,
    "Calacoto": -1.0,
    "Obrajes": -0.5,
    "San Pedro": 0.5,
}

# ---------------------------------------------------------------------------
# Estacionalidad
# ---------------------------------------------------------------------------
TEMPORADA_POR_MES: Final[dict[int, str]] = {
    1: "alta",
    2: "alta",
    3: "media",
    4: "baja",
    5: "baja",
    6: "media",
    7: "alta",
    8: "media",
    9: "baja",
    10: "media",
    11: "media",
    12: "alta",
}

# Demanda relativa esperada por mes, antes de ajustar por categoría.
ESTACIONALIDAD_MENSUAL: Final[dict[int, float]] = {
    1: 1.12,
    2: 1.08,
    3: 0.96,
    4: 0.92,
    5: 0.95,
    6: 1.00,
    7: 1.10,
    8: 1.02,
    9: 0.97,
    10: 1.00,
    11: 1.05,
    12: 1.22,
}

# Ajuste fino por categoría: solo se declaran los meses que se desvían de 1.0.
AJUSTE_ESTACIONAL_CATEGORIA: Final[dict[str, dict[int, float]]] = {
    "pollo": {4: 0.94, 7: 1.05, 12: 1.15},
    "cerdo": {2: 1.10, 4: 0.90, 12: 1.15},
    "embutidos": {1: 1.05, 2: 1.08, 12: 1.18},
    "congelados": {3: 0.94, 6: 1.06, 7: 1.10, 12: 1.10},
}

# Temperatura media mensual de referencia en La Paz (grados Celsius).
TEMPERATURA_MEDIA_MES: Final[dict[int, float]] = {
    1: 12.0,
    2: 12.0,
    3: 12.0,
    4: 11.0,
    5: 10.0,
    6: 9.0,
    7: 9.0,
    8: 10.0,
    9: 11.0,
    10: 12.0,
    11: 12.0,
    12: 12.0,
}

# Sensibilidad de las ventas a la temperatura (por grado sobre 10 °C).
SENSIBILIDAD_TERMICA_CATEGORIA: Final[dict[str, float]] = {
    "pollo": 0.004,
    "cerdo": 0.000,
    "embutidos": 0.000,
    "congelados": 0.015,
}

# Temperatura a partir de la cual el calor empieza a afectar la demanda y la merma.
GRADOS_REFERENCIA_TERMICA: Final[float] = 10.0

# Constantes de calendario.
DIAS_POR_SEMANA: Final[int] = 7
MESES_POR_ANIO: Final[int] = 12

# Límites de negocio para variables acotadas.
MERMA_MINIMA_PCT: Final[float] = 0.3
MERMA_MAXIMA_PCT: Final[float] = 35.0
UNIDADES_MINIMAS: Final[int] = 1
PRECIO_MINIMO_BS: Final[float] = 0.5
META_MINIMA_BS: Final[float] = 1.0
PERSONAL_MINIMO: Final[int] = 1
PERSONAL_MAXIMO: Final[int] = 15

# Cada punto de merma reduce la demanda atendible por pérdida de calidad.
PENALIDAD_DEMANDA_MERMA: Final[float] = 0.6

# Incremento de merma por cada grado por encima de la temperatura de referencia.
EFECTO_TERMICO_MERMA: Final[float] = 0.20

# Multiplicador de afluencia en semanas con feriado.
FACTOR_AFLUENCIA_FERIADO: Final[float] = 1.10

# Feriados nacionales de Bolivia (mes, día) más el feriado departamental de
# La Paz, donde se ubican todas las sucursales.
FERIADOS_FIJOS: Final[tuple[tuple[int, int, str], ...]] = (
    (1, 1, "Año Nuevo"),
    (1, 22, "Estado Plurinacional"),
    (5, 1, "Día del Trabajo"),
    (6, 21, "Año Nuevo Andino"),
    (7, 16, "Efeméride de La Paz"),
    (8, 6, "Independencia de Bolivia"),
    (11, 2, "Todos Santos"),
    (12, 25, "Navidad"),
)


# ---------------------------------------------------------------------------
# Parámetros del generador
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ParametrosGeneracion:
    """Hiperparámetros del simulador de ventas semanales.

    Attributes:
        fecha_inicio: Primer lunes del horizonte simulado.
        numero_semanas: Cantidad de semanas generadas (104 = dos años).
        probabilidad_promocion: Probabilidad de que una fila tenga promoción.
        descuento_min_pct: Descuento mínimo aplicado en promoción.
        descuento_max_pct: Descuento máximo aplicado en promoción.
        elasticidad_promocion: Incremento de unidades por punto de descuento.
        elasticidad_trafico_promocion: Incremento de afluencia por descuento.
        probabilidad_atipico: Proporción de semanas con comportamiento anómalo.
        probabilidad_atipico_negativo: Proporción de atípicos que son caídas.
        rango_atipico_bajo: Multiplicador de afluencia en atípicos negativos.
        rango_atipico_alto: Multiplicador de afluencia en atípicos positivos.
        probabilidad_incidente_merma: Probabilidad de una falla de cadena de frío.
        rango_incidente_merma: Merma adicional (puntos) cuando falla la cadena de frío.
        personal_piso_volumen: Dotación mínima relativa al volumen medio.
        personal_escala_volumen: Sensibilidad de la dotación al volumen esperado.
        proporcion_faltantes: Proporción de valores faltantes por columna.
        tendencia_semanal: Crecimiento relativo de la demanda por semana.
        ruido_afluencia: Desviación del ruido multiplicativo de la afluencia.
        ruido_conversion: Desviación del ruido de conversión a unidades.
        ruido_temperatura: Desviación de la temperatura semanal.
        ruido_precio: Desviación relativa del precio promedio.
        ruido_planificacion: Desviación del error de pronóstico al planificar stock.
        rango_factor_stock: Rango del stock respecto de la demanda esperada.
        rango_factor_meta: Rango del margen de holgura de la meta.
    """

    fecha_inicio: date = date(2024, 1, 1)
    numero_semanas: int = 104
    probabilidad_promocion: float = 0.24
    descuento_min_pct: float = 5.0
    descuento_max_pct: float = 25.0
    elasticidad_promocion: float = 1.8
    elasticidad_trafico_promocion: float = 0.5
    probabilidad_atipico: float = 0.015
    probabilidad_atipico_negativo: float = 0.45
    rango_atipico_bajo: tuple[float, float] = (0.30, 0.60)
    rango_atipico_alto: tuple[float, float] = (1.60, 2.40)
    probabilidad_incidente_merma: float = 0.04
    rango_incidente_merma: tuple[float, float] = (8.0, 18.0)
    personal_piso_volumen: float = 0.7
    personal_escala_volumen: float = 0.6
    proporcion_faltantes: float = 0.02
    tendencia_semanal: float = 0.0015
    ruido_afluencia: float = 0.09
    ruido_conversion: float = 0.10
    ruido_temperatura: float = 1.2
    ruido_precio: float = 0.015
    ruido_planificacion: float = 0.10
    rango_factor_stock: tuple[float, float] = (1.00, 1.50)
    rango_factor_meta: tuple[float, float] = (0.90, 1.15)


PARAMETROS_GENERACION: Final[ParametrosGeneracion] = ParametrosGeneracion()


# ---------------------------------------------------------------------------
# Parámetros de Machine Learning (Fase 2)
# ---------------------------------------------------------------------------
VERSION_MODELO: Final[str] = "2.0.0"

# El objetivo es la venta de la semana siguiente. Para predecirla se usa toda
# la información de la semana t (cerrada) y el calendario conocido de t+1.
LAGS_VENTAS: Final[tuple[int, ...]] = (1, 2, 4)
VENTANAS_MEDIA_MOVIL: Final[tuple[int, ...]] = (2, 4, 8)
HISTORIA_MINIMA_SEMANAS: Final[int] = max(LAGS_VENTAS + VENTANAS_MEDIA_MOVIL)

# Primeros 18 meses para entrenar; último medio año para probar.
FECHA_CORTE_ENTRENAMIENTO: Final[date] = date(2025, 6, 30)
DIVISIONES_TIEMPO: Final[int] = 5

# Características numéricas: lags y medias móviles de ventas, covariates de la
# semana cerrada y calendario de la semana objetivo.
CARACTERISTICAS_NUMERICAS: Final[tuple[str, ...]] = (
    "ventas_lag_1",
    "ventas_lag_2",
    "ventas_lag_4",
    "ventas_media_2",
    "ventas_media_4",
    "ventas_media_8",
    "unidades_vendidas",
    "precio_promedio",
    "en_promocion",
    "descuento_pct",
    "stock_inicial",
    "merma_pct",
    "temperatura_media",
    "afluencia_clientes",
    "personal_asignado",
    "meta_ventas_bs",
    "semana_anio",
    "mes",
    "es_feriado_objetivo",
)

# Características categóricas codificadas con One-Hot.
CARACTERISTICAS_CATEGORICAS: Final[tuple[str, ...]] = (
    "sucursal",
    "categoria",
    "temporada_objetivo",
)

CLAVE_SERIE: Final[tuple[str, str]] = ("sucursal", "categoria")
COLUMNAS_IDENTIFICADOR: Final[tuple[str, ...]] = (
    "fecha_origen",
    "fecha_objetivo",
    "sucursal",
    "categoria",
)
COLUMNA_OBJETIVO: Final[str] = "ventas_objetivo"
COLUMNA_META_OBJETIVO: Final[str] = "meta_objetivo"

# Parámetros de explicabilidad y confianza.
NUMERO_FACTORES_LOCALES: Final[int] = 5
MAX_MUESTRAS_SHAP: Final[int] = 200
CONFIANZA_MINIMA: Final[float] = 0.05
CONFIANZA_MAXIMA: Final[float] = 0.98

# Tolerancia para evitar divisiones por cero en métricas y confianza.
EPSILON: Final[float] = 1e-9

# ---------------------------------------------------------------------------
# Parámetros del sistema experto (Fase 3)
# ---------------------------------------------------------------------------
DIR_EXPERTO: Final[Path] = RAIZ_PROYECTO / "expert_system"
ARCHIVO_REGLAS_EXPERTO: Final[Path] = DIR_EXPERTO / "reglas.json"
VERSION_BASE_CONOCIMIENTOS: Final[str] = "3.0.0"

# Una regla solo se dispara cuando la certeza de su premisa alcanza este valor.
UMBRAL_CF_EXPERTO: Final[float] = 0.20


# ---------------------------------------------------------------------------
# Lógica difusa (Fase 4)
# ---------------------------------------------------------------------------
# Universo = (mínimo, máximo, paso). Las regiones se declaran con tres puntos
# para triángulos y cuatro para trapecios, en orden creciente.
@dataclass(frozen=True, slots=True)
class RegionDifusa:
    """Región de pertenencia declarativa de una variable lingüística.

    Attributes:
        tipo: ``triangular`` o ``trapezoidal``.
        puntos: Tres puntos (triángulo) o cuatro (trapecio) en orden creciente.
    """

    tipo: str
    puntos: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class VariableDifusa:
    """Variable lingüística con universo numérico y etiquetas graduales.

    Attributes:
        universo: Triple ``(mínimo, máximo, paso)``.
        etiquetas: Nombre de cada etiqueta y su región de pertenencia.
    """

    universo: tuple[float, float, float]
    etiquetas: dict[str, RegionDifusa]


@dataclass(frozen=True, slots=True)
class ReglaDifusa:
    """Regla difusa declarativa ``SI ... ENTONCES ...``.

    Attributes:
        id: Identificador único.
        descripcion: Intuición de negocio de la regla.
        si: Mapping de variable lingüística a etiqueta antecedente.
        entonces: Mapping de variable lingüística a etiqueta consecuente.
    """

    id: str
    descripcion: str
    si: dict[str, str]
    entonces: dict[str, str]


VARIABLES_DIFUSAS: Final[dict[str, VariableDifusa]] = {
    "cumplimiento_esperado": VariableDifusa(
        (0.0, 130.0, 1.0),
        {
            "bajo": RegionDifusa("trapezoidal", (0.0, 0.0, 70.0, 90.0)),
            "medio": RegionDifusa("triangular", (80.0, 95.0, 110.0)),
            "alto": RegionDifusa("trapezoidal", (100.0, 115.0, 130.0, 130.0)),
        },
    ),
    "nivel_stock": VariableDifusa(
        (0.0, 2.0, 0.01),
        {
            "crítico": RegionDifusa("trapezoidal", (0.0, 0.0, 0.25, 0.5)),
            "adecuado": RegionDifusa("triangular", (0.35, 0.7, 1.05)),
            "excesivo": RegionDifusa("trapezoidal", (0.9, 1.25, 2.0, 2.0)),
        },
    ),
    "merma": VariableDifusa(
        (0.0, 30.0, 0.5),
        {
            "baja": RegionDifusa("trapezoidal", (0.0, 0.0, 4.0, 8.0)),
            "media": RegionDifusa("triangular", (6.0, 11.0, 16.0)),
            "alta": RegionDifusa("trapezoidal", (14.0, 20.0, 30.0, 30.0)),
        },
    ),
    "afluencia": VariableDifusa(
        (0.0, 1.5, 0.01),
        {
            "baja": RegionDifusa("trapezoidal", (0.0, 0.0, 0.7, 0.9)),
            "normal": RegionDifusa("triangular", (0.8, 1.0, 1.2)),
            "alta": RegionDifusa("trapezoidal", (1.1, 1.3, 1.5, 1.5)),
        },
    ),
    "intensidad_promocion": VariableDifusa(
        (0.0, 30.0, 0.5),
        {
            "ninguna": RegionDifusa("trapezoidal", (0.0, 0.0, 0.0, 5.0)),
            "moderada": RegionDifusa("triangular", (3.0, 10.0, 17.0)),
            "fuerte": RegionDifusa("trapezoidal", (15.0, 22.0, 30.0, 30.0)),
        },
    ),
    "nivel_riesgo_incumplimiento": VariableDifusa(
        (0.0, 100.0, 1.0),
        {
            "bajo": RegionDifusa("trapezoidal", (0.0, 0.0, 20.0, 40.0)),
            "medio": RegionDifusa("triangular", (30.0, 50.0, 70.0)),
            "alto": RegionDifusa("triangular", (60.0, 75.0, 90.0)),
            "crítico": RegionDifusa("trapezoidal", (85.0, 95.0, 100.0, 100.0)),
        },
    ),
    "urgencia_accion": VariableDifusa(
        (0.0, 100.0, 1.0),
        {
            "ninguna": RegionDifusa("trapezoidal", (0.0, 0.0, 10.0, 25.0)),
            "baja": RegionDifusa("triangular", (20.0, 35.0, 50.0)),
            "media": RegionDifusa("triangular", (45.0, 60.0, 75.0)),
            "alta": RegionDifusa("trapezoidal", (70.0, 85.0, 100.0, 100.0)),
        },
    ),
}

SALIDAS_DIFUSAS: Final[tuple[str, ...]] = (
    "nivel_riesgo_incumplimiento",
    "urgencia_accion",
)

# Defuzzificación por centroide de un sistema Mamdani con conectivos min/max.
REGLAS_DIFUSAS: Final[tuple[ReglaDifusa, ...]] = (
    ReglaDifusa(
        "DF01",
        "Cumplimiento bajo con stock crítico: riesgo crítico y acción inmediata",
        {"cumplimiento_esperado": "bajo", "nivel_stock": "crítico"},
        {"nivel_riesgo_incumplimiento": "crítico", "urgencia_accion": "alta"},
    ),
    ReglaDifusa(
        "DF02",
        "Cumplimiento bajo con merma alta agrava el riesgo",
        {"cumplimiento_esperado": "bajo", "merma": "alta"},
        {"nivel_riesgo_incumplimiento": "crítico", "urgencia_accion": "alta"},
    ),
    ReglaDifusa(
        "DF03",
        "Cumplimiento bajo y poca afluencia: riesgo alto",
        {"cumplimiento_esperado": "bajo", "afluencia": "baja"},
        {"nivel_riesgo_incumplimiento": "alto", "urgencia_accion": "alta"},
    ),
    ReglaDifusa(
        "DF04",
        "Cumplimiento bajo sin promoción: riesgo alto",
        {"cumplimiento_esperado": "bajo", "intensidad_promocion": "ninguna"},
        {"nivel_riesgo_incumplimiento": "alto", "urgencia_accion": "media"},
    ),
    ReglaDifusa(
        "DF05",
        "Cumplimiento bajo con stock adecuado: riesgo alto",
        {"cumplimiento_esperado": "bajo", "nivel_stock": "adecuado"},
        {"nivel_riesgo_incumplimiento": "alto", "urgencia_accion": "media"},
    ),
    ReglaDifusa(
        "DF06",
        "Cumplimiento medio con stock crítico: riesgo alto",
        {"cumplimiento_esperado": "medio", "nivel_stock": "crítico"},
        {"nivel_riesgo_incumplimiento": "alto", "urgencia_accion": "alta"},
    ),
    ReglaDifusa(
        "DF07",
        "Cumplimiento medio con merma alta: riesgo alto",
        {"cumplimiento_esperado": "medio", "merma": "alta"},
        {"nivel_riesgo_incumplimiento": "alto", "urgencia_accion": "media"},
    ),
    ReglaDifusa(
        "DF08",
        "Cumplimiento medio con afluencia baja: riesgo alto",
        {"cumplimiento_esperado": "medio", "afluencia": "baja"},
        {"nivel_riesgo_incumplimiento": "alto", "urgencia_accion": "media"},
    ),
    ReglaDifusa(
        "DF09",
        "Cumplimiento medio sin promoción: riesgo medio",
        {"cumplimiento_esperado": "medio", "intensidad_promocion": "ninguna"},
        {"nivel_riesgo_incumplimiento": "medio", "urgencia_accion": "media"},
    ),
    ReglaDifusa(
        "DF10",
        "Cumplimiento medio con excedente de stock: riesgo medio",
        {"cumplimiento_esperado": "medio", "nivel_stock": "excesivo"},
        {"nivel_riesgo_incumplimiento": "medio", "urgencia_accion": "baja"},
    ),
    ReglaDifusa(
        "DF11",
        "Cumplimiento alto pero stock crítico: riesgo medio",
        {"cumplimiento_esperado": "alto", "nivel_stock": "crítico"},
        {"nivel_riesgo_incumplimiento": "medio", "urgencia_accion": "media"},
    ),
    ReglaDifusa(
        "DF12",
        "Cumplimiento alto con merma alta: riesgo medio",
        {"cumplimiento_esperado": "alto", "merma": "alta"},
        {"nivel_riesgo_incumplimiento": "medio", "urgencia_accion": "baja"},
    ),
    ReglaDifusa(
        "DF13",
        "Cumplimiento alto y afluencia alta: riesgo bajo",
        {"cumplimiento_esperado": "alto", "afluencia": "alta"},
        {"nivel_riesgo_incumplimiento": "bajo", "urgencia_accion": "baja"},
    ),
    ReglaDifusa(
        "DF14",
        "Cumplimiento alto con promoción fuerte: riesgo bajo",
        {"cumplimiento_esperado": "alto", "intensidad_promocion": "fuerte"},
        {"nivel_riesgo_incumplimiento": "bajo", "urgencia_accion": "ninguna"},
    ),
    ReglaDifusa(
        "DF15",
        "Cumplimiento alto con stock adecuado: riesgo bajo",
        {"cumplimiento_esperado": "alto", "nivel_stock": "adecuado"},
        {"nivel_riesgo_incumplimiento": "bajo", "urgencia_accion": "ninguna"},
    ),
    ReglaDifusa(
        "DF16",
        "Stock crítico y merma alta: riesgo crítico",
        {"nivel_stock": "crítico", "merma": "alta"},
        {"nivel_riesgo_incumplimiento": "crítico", "urgencia_accion": "alta"},
    ),
    ReglaDifusa(
        "DF17",
        "Afluencia baja sin promoción: riesgo alto",
        {"afluencia": "baja", "intensidad_promocion": "ninguna"},
        {"nivel_riesgo_incumplimiento": "alto", "urgencia_accion": "media"},
    ),
    ReglaDifusa(
        "DF18",
        "Escenario ideal: riesgo bajo y sin urgencia",
        {"nivel_stock": "excesivo", "merma": "baja", "cumplimiento_esperado": "alto"},
        {"nivel_riesgo_incumplimiento": "bajo", "urgencia_accion": "ninguna"},
    ),
    ReglaDifusa(
        "DF19",
        "Cumplimiento bajo con promoción fuerte: riesgo alto atenuado",
        {"cumplimiento_esperado": "bajo", "intensidad_promocion": "fuerte"},
        {"nivel_riesgo_incumplimiento": "alto", "urgencia_accion": "media"},
    ),
    ReglaDifusa(
        "DF20",
        "Afluencia alta con merma media: riesgo medio",
        {"afluencia": "alta", "merma": "media"},
        {"nivel_riesgo_incumplimiento": "medio", "urgencia_accion": "baja"},
    ),
    ReglaDifusa(
        "DF21",
        "Cumplimiento medio con operación estable: riesgo medio",
        {"cumplimiento_esperado": "medio", "afluencia": "normal", "nivel_stock": "adecuado"},
        {"nivel_riesgo_incumplimiento": "medio", "urgencia_accion": "baja"},
    ),
    ReglaDifusa(
        "DF22",
        "Cumplimiento bajo con sobrestock: riesgo medio",
        {"cumplimiento_esperado": "bajo", "nivel_stock": "excesivo"},
        {"nivel_riesgo_incumplimiento": "medio", "urgencia_accion": "media"},
    ),
)

# Un hecho numérico se convierte enhechos simbólicos de su variable lingüística.
MAPEO_DIFUSO_HECHOS: Final[dict[str, str]] = {
    "cumplimiento_esperado_pct": "cumplimiento_esperado",
    "stock_cobertura": "nivel_stock",
    "merma_pct": "merma",
    "afluencia_rel": "afluencia",
    "descuento_pct": "intensidad_promocion",
}
ATRIBUTO_RIESGO_DIFUSO: Final[str] = "nivel_riesgo_difuso"
ATRIBUTO_URGENCIA: Final[str] = "urgencia_accion"

# Variables lingüísticas de salida -> atributo de la memoria del sistema experto.
# El riesgo se registra aparte del riesgo crisp para no mezclar ambas evidencias.
MAPEO_SALIDAS_DIFUSAS: Final[dict[str, str]] = {
    "nivel_riesgo_incumplimiento": ATRIBUTO_RIESGO_DIFUSO,
    "urgencia_accion": ATRIBUTO_URGENCIA,
}

# Grado mínimo de pertenencia para convertir un valor numérico en hecho simbólico.
UMBRAL_PERTENENCIA_DIFUSA: Final[float] = 0.10
