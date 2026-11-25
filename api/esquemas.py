"""Modelos Pydantic de entrada y salida de la API REST.

Los esquemas de petición son estrictos: rechazan campos desconocidos, espacios
sobrantes en cadenas y conversiones implícitas entre tipos. Los esquemas de
respuesta son proyecciones explícitas de :class:`core.resultado.ResultadoSistema`;
la API no calcula lógica de negocio, solo la presenta.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Sucursal = Literal[
    "Sopocachi",
    "El Alto",
    "Miraflores",
    "Calacoto",
    "Obrajes",
    "San Pedro",
]
"""Sucursales permitidas, espejo de ``config.SUCURSALES``."""

Categoria = Literal["pollo", "cerdo", "embutidos", "congelados"]
"""Categorías permitidas, espejo de ``config.CATEGORIAS``."""

Temporada = Literal["alta", "media", "baja"]
"""Temporadas permitidas, espejo de ``config.TEMPORADAS``."""

FECHA_ISO = r"^\d{4}-\d{2}-\d{2}$"
"""Patrón de fechas AAAA-MM-DD aceptadas por la API."""


class SemanaHistorial(BaseModel):
    """Una semana cruda del historial, con el esquema del dataset de la Fase 1."""

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    fecha_semana: str = Field(
        pattern=FECHA_ISO, description="Lunes que inicia la semana (AAAA-MM-DD)"
    )
    ventas_bs: float = Field(ge=0, description="Ventas observadas en bolivianos")
    unidades_vendidas: int = Field(ge=0, description="Unidades efectivamente vendidas")
    precio_promedio: float = Field(ge=0, description="Precio unitario realizado")
    en_promocion: bool = Field(description="Si la semana tuvo promoción")
    descuento_pct: float = Field(ge=0, le=100, description="Descuento aplicado en porcentaje")
    stock_inicial: float = Field(ge=0, description="Unidades disponibles al inicio de la semana")
    merma_pct: float = Field(ge=0, le=100, description="Porcentaje de stock perdido por merma")
    temporada: Temporada = Field(description="Temporada de la semana")
    es_feriado_semana: bool = Field(description="Si la semana contiene feriado")
    temperatura_media: float = Field(description="Temperatura media semanal en grados Celsius")
    afluencia_clientes: float = Field(ge=0, description="Clientes que ingresaron a la sucursal")
    personal_asignado: int = Field(ge=0, description="Personas asignadas a la categoría")
    meta_ventas_bs: float = Field(gt=0, description="Meta semanal fijada antes de vender")
    cumplimiento_meta_pct: float = Field(ge=0, description="Ventas sobre meta, en porcentaje")


class SolicitudAnalisis(BaseModel):
    """Petición común a los cuatro endpoint de análisis.

    Opcionalmente se puede enviar un ``historial`` explícito; si no se envía, la
    API lee el dataset crudo configurado. El resto de campos son escenarios que
    sobrescriben los datos observados de la última semana cerrada.
    """

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    sucursal: Sucursal = Field(description="Sucursal analizada")
    categoria: Categoria = Field(description="Categoría analizada")
    fecha_corte: str | None = Field(
        default=None,
        pattern=FECHA_ISO,
        description="Última semana cerrada permitida; por defecto todas",
    )
    fecha_objetivo: str | None = Field(
        default=None,
        pattern=FECHA_ISO,
        description="Semana a predecir; por defecto se deriva del historial",
    )
    semanas: int = Field(default=8, ge=8, le=104, description="Semanas consecutivas de historial")
    historial: list[SemanaHistorial] | None = Field(
        default=None,
        description="Historial explícito; si se omite se usa el dataset crudo",
    )
    meta_bs: float | None = Field(default=None, gt=0, description="Meta explícita en bolivianos")
    factor_meta: float = Field(default=1.0, gt=0, le=10, description="Ajuste de la meta histórica")
    presupuesto_bs: float = Field(
        default=9000.0, ge=0, le=1_000_000_000.0, description="Fondo máximo para el plan"
    )
    stock_inicial: float | None = Field(default=None, ge=0, description="Stock de la semana t")
    merma_inicial: float | None = Field(
        default=None, ge=0, le=100, description="Merma en porcentaje"
    )
    personal_inicial: float | None = Field(default=None, ge=0, description="Dotación de personal")
    afluencia: float | None = Field(default=None, ge=0, description="Clientes de la semana t")
    stock_cobertura: float | None = Field(
        default=None, ge=0, le=100, description="Unidades disponibles por unidad vendida"
    )
    afluencia_rel: float | None = Field(
        default=None, ge=0, le=100, description="Afluencia relativa a la media histórica"
    )
    personal_rel: float | None = Field(
        default=None, ge=0, le=100, description="Dotación relativa a la base de la categoría"
    )
    descuento_pct: float | None = Field(default=None, ge=0, le=100, description="Descuento vigente")
    temperatura_media: float | None = Field(
        default=None, description="Temperatura media de la semana en grados Celsius"
    )
    precio_vs_competencia: float = Field(
        default=1.0, gt=0, le=10, description="Ratio de precio propio frente al competidor"
    )
    es_perecible: bool = Field(default=True, description="Si la categoría es perecible")
    en_promocion: bool | None = Field(default=None, description="Si la semana t tuvo promoción")
    es_feriado: bool | None = Field(default=None, description="Si la semana t contiene feriado")
    hay_excedente_en_otra_sucursal: bool = Field(
        default=False, description="Si hay excedente para reasignar"
    )
    reabastecimiento_tardia: bool = Field(
        default=False, description="Si el proveedor tarda en reponer"
    )

    def para_contexto(self) -> dict[str, object]:
        """Devuelve solo los campos que :class:`core.contexto.ContextoNegocio` acepta."""
        excluidos = {"sucursal", "categoria", "fecha_corte", "semanas", "historial"}
        return self.model_dump(exclude=excluidos, exclude_none=True)


class PuntoHistorico(BaseModel):
    """Semana cerrada lista para graficar histórico versus proyección."""

    model_config = ConfigDict(extra="forbid")

    fecha: str = Field(description="Lunes de la semana en formato AAAA-MM-DD")
    ventas_bs: float = Field(description="Ventas observadas")
    meta_bs: float = Field(description="Meta observada")


class Proyeccion(BaseModel):
    """Punto proyectado de la semana objetivo."""

    model_config = ConfigDict(extra="forbid")

    fecha: str = Field(description="Semana proyectada en formato AAAA-MM-DD")
    valor_predicho_bs: float = Field(description="Ventas estimadas")
    meta_bs: float = Field(description="Meta efectiva de la semana proyectada")
    cumplimiento_pct: float = Field(description="Porcentaje de cumplimiento esperado")


class PrediccionDTO(BaseModel):
    """Predicción, confianza y factores SHAP devueltos por el modelo."""

    model_config = ConfigDict(extra="forbid")

    valor_predicho_bs: float = Field(description="Ventas estimadas para la semana siguiente")
    cumplimiento_esperado_pct: float = Field(description="Cumplimiento esperado de la meta")
    confianza: float = Field(description="Factor de certeza calibrado en el rango [0, 1]")
    principales_factores: list[str] = Field(description="Factores SHAP en texto legible")


class CausaDTO(BaseModel):
    """Causa diagnosticada con su factor de certeza combinado."""

    model_config = ConfigDict(extra="forbid")

    causa: str = Field(description="Valor del atributo causa_ventas_bajas")
    cf: float = Field(description="Factor de certeza final")
    descripcion: str = Field(description="Intuición de negocio de la regla que respalda la causa")
    reglas: list[str] = Field(description="Identificadores de reglas que concluyeron la causa")


class ReglaAplicadaDTO(BaseModel):
    """Regla realmente aplicada en una ejecución, con su información completa."""

    model_config = ConfigDict(extra="forbid")

    orden: int | None = Field(description="Orden real de disparo; vacío en reglas difusas")
    regla_id: str = Field(description="Código de la regla")
    descripcion: str = Field(description="Nombre legible de la regla")
    categoria: str = Field(description="Categoría declarada de la regla")
    premisa: str = Field(description="Condición SI evaluada")
    cf_premisa: float = Field(description="Certeza de la premisa antes de propagar")
    fc_regla: float = Field(description="Certeza declarada o fuerza de activación de la regla")
    cf_conclusion: float = Field(description="Certeza de la conclusión derivada")
    conclusion: str = Field(description="Conclusión ENTONCES")
    conclusion_atributo: str = Field(description="Variable o variables concluidas")
    conclusion_valor: str = Field(description="Valor o valores concluidos")
    momento: str = Field(description="Instante ISO 8601 del disparo, si aplica")
    prioridad: int | None = Field(description="Prioridad declarada; vacío en reglas difusas")
    tipo: Literal["experta", "difusa"] = Field(description="Origen de la regla")


class ReglaSistemaDTO(BaseModel):
    """Regla declarativa del catálogo, lista para mostrar en lenguaje natural."""

    model_config = ConfigDict(extra="forbid")

    tipo: Literal["experta", "difusa"] = Field(description="Origen de la regla")
    id: str = Field(description="Código de la regla")
    descripcion: str = Field(description="Nombre legible de la regla")
    categoria: str = Field(description="Categoría declarada de la regla")
    si: str = Field(description="Condición SI en el texto de la base")
    entonces: str = Field(description="Conclusión ENTONCES en el texto de la base")
    certeza: float | None = Field(description="FC declarado; vacío en reglas difusas")
    prioridad: int | None = Field(description="Prioridad declarada; vacío en reglas difusas")
    antecedentes: list[str] = Field(description="Condiciones atómicas o pares lingüísticos del SI")
    consecuentes: list[str] = Field(description="Conclusiones atómicas o pares lingüísticos")


class RiesgoDTO(BaseModel):
    """Riesgo difuso defuzzificado, con su semáforo visual."""

    model_config = ConfigDict(extra="forbid")

    etiqueta: str = Field(description="Etiqueta lingüística dominante")
    valor: float = Field(description="Centroide numérico del riesgo")
    grado: float = Field(description="Grado de pertenencia de la etiqueta dominante")
    urgencia: str = Field(description="Urgencia de acción dominante")
    reglas_activadas: list[str] = Field(description="Reglas difusas con fuerza positiva")
    descripcion: str = Field(description="Resumen legible del resultado difuso")
    semaforo: str = Field(description="Color del semáforo: verde, amarillo, naranja o rojo")


class NodoBusquedaDTO(BaseModel):
    """Estado visitado por A*, listo para dibujar en el dashboard."""

    model_config = ConfigDict(extra="forbid")

    id: int = Field(description="Identificador del nodo dentro de la búsqueda")
    padre_id: int | None = Field(description="Nodo que generó este estado")
    estado: str = Field(description="Resumen legible del estado")
    accion: str = Field(description="Acción aplicada para llegar al estado")
    profundidad: int = Field(description="Acciones acumuladas desde el inicio")
    costo_bs: float = Field(description="Costo acumulado hasta el estado")
    heuristica: float | None = Field(description="Estimación restante, si aplica")
    f: float | None = Field(description="Costo estimado total g + h, si aplica")
    expandido: bool = Field(description="Si el estado fue evaluado")
    es_meta: bool = Field(description="Si el estado alcanza la meta")
    descartado: bool = Field(description="Si se descartó por repetido o por costo")
    orden_expansion: int | None = Field(description="Orden en que se expandió")


class PlanDTO(BaseModel):
    """Plan de acciones devuelto por A*."""

    model_config = ConfigDict(extra="forbid")

    acciones: list[str] = Field(description="Operadores en orden de ejecución")
    descripcion: str = Field(description="Plan en texto legible")
    costo_bs: float = Field(description="Costo total estimado del plan")
    encontrado: bool = Field(description="Si A* alcanzó la meta dentro del presupuesto")
    nodos_expandidos: int = Field(description="Estados evaluados por la búsqueda")
    restricciones: list[str] = Field(description="Operadores excluidos por el diagnóstico")
    justificacion: str = Field(description="Por qué el diagnóstico conduce a este plan")
    nodos_generados: int = Field(description="Estados creados durante la búsqueda")
    profundidad: int = Field(description="Cantidad de acciones del plan")
    nodos: list[NodoBusquedaDTO] = Field(description="Trazas de estados visitados por A*")


class ComparativaDTO(BaseModel):
    """Comparativa entre IA simbólica y no simbólica para esta ejecución."""

    model_config = ConfigDict(extra="forbid")

    aporte_ml: str = Field(description="Qué aporta el componente de Machine Learning")
    aporte_experto: str = Field(description="Qué aportan reglas, factores de certeza y difuso")
    complementariedad: str = Field(description="Por qué la unión supera a cada parte por separado")
    evidencia: str = Field(description="Huella dejada por ambos componentes en esta ejecución")


class RespuestaBase(BaseModel):
    """Campos comunes a todas las respuestas de análisis."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Identificador UUID del análisis guardado")
    sucursal: str = Field(description="Sucursal analizada")
    categoria: str = Field(description="Categoría analizada")
    fecha_objetivo: str = Field(description="Semana proyectada en formato AAAA-MM-DD")


class RespuestaPrediccion(RespuestaBase):
    """Respuesta de ``POST /predecir``."""

    prediccion: PrediccionDTO
    cumplimiento_pct: float
    historial: list[PuntoHistorico]
    proyeccion: Proyeccion


class RespuestaDiagnostico(RespuestaBase):
    """Respuesta de ``POST /diagnosticar``."""

    causas: list[CausaDTO]
    riesgo: RiesgoDTO
    reglas_disparadas: list[str]
    reglas_aplicadas: list[ReglaAplicadaDTO]


class RespuestaPlan(RespuestaBase):
    """Respuesta de ``POST /planificar``."""

    plan: PlanDTO
    causas_consideradas: list[str]


class RespuestaCompleta(RespuestaBase):
    """Respuesta de ``POST /analisis-completo`` con el resultado integral."""

    prediccion: PrediccionDTO
    cumplimiento_pct: float
    historial: list[PuntoHistorico]
    proyeccion: Proyeccion
    causas: list[CausaDTO]
    riesgo: RiesgoDTO
    plan: PlanDTO
    explicacion: str
    comparativa: ComparativaDTO
    reglas_disparadas: list[str]
    reglas_aplicadas: list[ReglaAplicadaDTO]


class RespuestaExplicacion(BaseModel):
    """Respuesta de ``GET /explicar/{id}`` con la explicación y su evidencia."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Identificador UUID del análisis")
    texto: str = Field(description="Explicación unificada en español")
    factores_shap: list[str] = Field(description="Factores SHAP de la predicción")
    causas: list[CausaDTO]
    riesgo: RiesgoDTO
    plan: PlanDTO
    reglas_disparadas: list[str]
    reglas_aplicadas: list[ReglaAplicadaDTO]
    comparativa: ComparativaDTO


class RespuestaSalud(BaseModel):
    """Estado del servicio y de los artefactos que necesita."""

    model_config = ConfigDict(extra="forbid")

    estado: str = Field(description="saludable o no_disponible")
    version: str = Field(description="Versión de la API")
    mensaje: str = Field(description="Detalle legible del estado")
    artefactos: dict[str, bool] = Field(description="Disponibilidad de cada artefacto requerido")


class RespuestaCatalogos(BaseModel):
    """Catálogos que el dashboard usa para poblar sus selectores."""

    model_config = ConfigDict(extra="forbid")

    sucursales: list[str]
    categorias: list[str]
    temporadas: list[str]


class FilaBenchmark(BaseModel):
    """Una fila del benchmark de algoritmos de búsqueda de la Fase 5."""

    model_config = ConfigDict(extra="forbid")

    algoritmo: str
    escenario: str
    encontrado: bool
    costo: float
    nodos_expandidos: int
    nodos_generados: int
    profundidad: int
    tiempo: float


class RespuestaBenchmark(BaseModel):
    """Resultados del benchmark listos para la pestaña comparativa."""

    model_config = ConfigDict(extra="forbid")

    escenarios: list[str]
    filas: list[FilaBenchmark]


class RespuestaReglas(BaseModel):
    """Catálogo completo de reglas expertas y difusas del sistema."""

    model_config = ConfigDict(extra="forbid")

    total: int = Field(description="Cantidad total de reglas declaradas")
    expertas: int = Field(description="Reglas crisp de la base de conocimientos")
    difusas: int = Field(description="Reglas difusas de Mamdani")
    reglas: list[ReglaSistemaDTO] = Field(description="Definiciones completas en orden declarado")
