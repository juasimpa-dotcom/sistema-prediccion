"""API REST FastAPI del sistema inteligente de predicción de ventas.

Todos los endpoint comparten el mismo flujo de negocio
:meth:`core.sistema.SistemaInteligente.ejecutar` y solo proyectan subconjuntos
del resultado. Las colaboraciones se inyectan con ``Depends`` desde
``request.app.state``: no hay objetos mutables globales.
"""

from __future__ import annotations

import csv
import logging
import os
import time
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.dependencias import (
    AnalisisGuardado,
    ConstructorContexto,
    FabricaSistema,
    RepositorioResultados,
    ServicioAnalisis,
    contexto_desde_solicitud,
    estado_artefactos,
    obtener_repositorio,
    obtener_servicio,
)
from api.esquemas import (
    FilaBenchmark,
    RespuestaBenchmark,
    RespuestaCatalogos,
    RespuestaCompleta,
    RespuestaDiagnostico,
    RespuestaExplicacion,
    RespuestaPlan,
    RespuestaPrediccion,
    RespuestaSalud,
    SolicitudAnalisis,
)
from api.mapeado import (
    causas_de,
    comparativa_de,
    fecha_objetivo_de,
    historial_de_contexto,
    plan_de,
    prediccion_de,
    proyeccion_de,
    riesgo_de,
)
from config import (
    API_CORS_ORIGENES,
    API_CORS_ORIGENES_ENV,
    API_DESCRIPCION,
    API_TITULO,
    API_VERSION,
    ARCHIVO_BENCHMARK_CSV,
    ARCHIVO_MODELO,
    ARCHIVO_REGLAS_EXPERTO,
    ARCHIVO_VENTAS_CRUDO,
    CATEGORIAS,
    SUCURSALES,
    TEMPORADAS,
)
from core.fabrica import construir_sistema

LOGGER = logging.getLogger(__name__)

CODIGOS_HTTP: dict[int, str] = {
    400: "peticion_invalida",
    404: "no_encontrado",
    422: "validacion",
    500: "error_interno",
    503: "servicio_no_disponible",
}
"""Códigos aplicados cuando un ``HTTPException`` no trae un código explícito."""

TAGS = [
    {"name": "Análisis", "description": "Predicción, diagnóstico, plan y análisis completo."},
    {"name": "Explicaciones", "description": "Acceso a la explicación de un análisis guardado."},
    {"name": "Operación", "description": "Estado del servicio y catálogos del dominio."},
    {"name": "Datos de apoyo", "description": "Benchmark de algoritmos de búsqueda."},
]


def origenes_cors_desde_entorno(origenes: Sequence[str] | None = None) -> list[str]:
    """Resuelve los orígenes CORS: argumento, variable de entorno o configuración."""
    if origenes is not None:
        return list(origenes)
    valor = os.getenv(API_CORS_ORIGENES_ENV, "").strip()
    if valor:
        return [parte.strip() for parte in valor.split(",") if parte.strip()]
    return list(API_CORS_ORIGENES)


def crear_app(
    fabrica_sistema: FabricaSistema | None = None,
    constructor_contexto: ConstructorContexto | None = None,
    repositorio: RepositorioResultados | None = None,
    rutas_artefactos: Sequence[Path | str] | None = None,
    titulo: str = API_TITULO,
    version: str = API_VERSION,
    origenes_cors: Sequence[str] | None = None,
) -> FastAPI:
    """Construye la aplicación con dependencias explícitas y sin globales.

    Args:
        fabrica_sistema: Crea una fachada nueva por petición.
        constructor_contexto: Convierte la solicitud en ``ContextoNegocio``.
        repositorio: Almacén de resultados para ``GET /explicar/{id}``.
        rutas_artefactos: Archivos verificados por ``GET /salud``.
        titulo: Título mostrado en OpenAPI.
        version: Versión mostrada en OpenAPI.
        origenes_cors: Orígenes permitidos; si se omiten se lee el entorno.

    Returns:
        Aplicación FastAPI lista para ``uvicorn`` o ``TestClient``.
    """
    rutas = tuple(
        Path(ruta)
        for ruta in (
            rutas_artefactos
            if rutas_artefactos is not None
            else (
                ARCHIVO_MODELO,
                ARCHIVO_REGLAS_EXPERTO,
                ARCHIVO_VENTAS_CRUDO,
                ARCHIVO_BENCHMARK_CSV,
            )
        )
    )
    servicio = ServicioAnalisis(
        fabrica=fabrica_sistema or construir_sistema,
        constructor_contexto=constructor_contexto or contexto_desde_solicitud,
        repositorio=repositorio,
        ruta_csv=ARCHIVO_VENTAS_CRUDO,
    )

    app = FastAPI(
        title=titulo,
        description=API_DESCRIPCION,
        version=version,
        openapi_tags=TAGS,
    )
    app.state.servicio = servicio
    app.state.repositorio = servicio.repositorio
    app.state.rutas_artefactos = rutas

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origenes_cors_desde_entorno(origenes_cors),
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def registrar_peticion(
        request: Request,
        llamar_siguiente: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Registra método, ruta, estado y duración de cada petición."""
        inicio = time.perf_counter()
        respuesta = await llamar_siguiente(request)
        duracion = time.perf_counter() - inicio
        LOGGER.info(
            "%s %s -> %s (%.3f s)",
            request.method,
            request.url.path,
            respuesta.status_code,
            duracion,
        )
        return respuesta

    @app.exception_handler(RequestValidationError)
    async def manejar_validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Convierte errores 422 de Pydantic a un cuerpo en español."""
        errores = [
            {
                "campo": ".".join(str(parte) for parte in error.get("loc", [])),
                "mensaje": str(error.get("msg", "")),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "detalle": {
                    "codigo": "validacion",
                    "mensaje": "La petición no cumple el esquema de la API",
                    "errores": errores,
                }
            },
        )

    @app.exception_handler(ValueError)
    async def manejar_valor(request: Request, exc: ValueError) -> JSONResponse:
        """Traduce contextos inválidos a 400."""
        return JSONResponse(
            status_code=400,
            content={
                "detalle": {
                    "codigo": "contexto_invalido",
                    "mensaje": str(exc),
                }
            },
        )

    @app.exception_handler(FileNotFoundError)
    async def manejar_artefacto(request: Request, exc: FileNotFoundError) -> JSONResponse:
        """Traduce artefactos ausentes a 503."""
        return JSONResponse(
            status_code=503,
            content={
                "detalle": {
                    "codigo": "artefacto_no_disponible",
                    "mensaje": str(exc) or "Falta un artefacto requerido",
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def manejar_http(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        """Normaliza los errores HTTP a un cuerpo ``detalle`` en español."""
        contenido = exc.detail
        if not isinstance(contenido, dict):
            contenido = {
                "codigo": CODIGOS_HTTP.get(exc.status_code, "error_http"),
                "mensaje": str(contenido),
            }
        return JSONResponse(
            status_code=exc.status_code,
            content={"detalle": contenido},
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def manejar_error(request: Request, exc: Exception) -> JSONResponse:
        """Evita exponer trazas internas y registra el error."""
        LOGGER.exception("Error no controlado en %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "detalle": {
                    "codigo": "error_interno",
                    "mensaje": "No se pudo completar la petición",
                }
            },
        )

    def datos_base(registro: AnalisisGuardado) -> dict[str, str]:
        """Devuelve los campos comunes de las respuestas de análisis."""
        return {
            "id": registro.id,
            "sucursal": registro.resultado.sucursal,
            "categoria": registro.resultado.categoria,
            "fecha_objetivo": fecha_objetivo_de(registro.contexto),
        }

    @app.post(
        "/predecir",
        response_model=RespuestaPrediccion,
        tags=["Análisis"],
        summary="Predecir ventas de la semana siguiente",
        description=(
            "Ejecuta el flujo completo y devuelve la predicción, la confianza, "
            "los factores SHAP y el histórico junto a la proyección."
        ),
        responses={
            400: {"description": "Contexto inválido"},
            422: {"description": "Petición inválida"},
        },
    )
    def predecir(
        solicitud: SolicitudAnalisis,
        servicio: ServicioAnalisis = Depends(obtener_servicio),
    ) -> RespuestaPrediccion:
        """Proyecta solo la predicción y la serie gráfica del resultado."""
        registro = servicio.ejecutar(solicitud)
        resultado = registro.resultado
        return RespuestaPrediccion(
            **datos_base(registro),
            prediccion=prediccion_de(resultado),
            cumplimiento_pct=resultado.cumplimiento_pct,
            historial=historial_de_contexto(registro.contexto),
            proyeccion=proyeccion_de(registro.contexto, resultado),
        )

    @app.post(
        "/diagnosticar",
        response_model=RespuestaDiagnostico,
        tags=["Análisis"],
        summary="Diagnosticar causas y riesgo",
        description=(
            "Devuelve las causas rankeadas por factor de certeza, el riesgo "
            "difuso con su semáforo y las reglas disparadas."
        ),
        responses={
            400: {"description": "Contexto inválido"},
            422: {"description": "Petición inválida"},
        },
    )
    def diagnosticar(
        solicitud: SolicitudAnalisis,
        servicio: ServicioAnalisis = Depends(obtener_servicio),
    ) -> RespuestaDiagnostico:
        """Proyecta el diagnóstico y el riesgo del resultado."""
        registro = servicio.ejecutar(solicitud)
        resultado = registro.resultado
        return RespuestaDiagnostico(
            **datos_base(registro),
            causas=causas_de(resultado),
            riesgo=riesgo_de(resultado),
            reglas_disparadas=list(resultado.reglas_disparadas),
        )

    @app.post(
        "/planificar",
        response_model=RespuestaPlan,
        tags=["Análisis"],
        summary="Planificar acciones comerciales",
        description=(
            "Devuelve el plan de A* con su costo, estado de búsqueda, "
            "restricciones y justificación."
        ),
        responses={
            400: {"description": "Contexto inválido"},
            422: {"description": "Petición inválida"},
        },
    )
    def planificar(
        solicitud: SolicitudAnalisis,
        servicio: ServicioAnalisis = Depends(obtener_servicio),
    ) -> RespuestaPlan:
        """Proyecta el plan recomendado y las causas que lo restringen."""
        registro = servicio.ejecutar(solicitud)
        resultado = registro.resultado
        return RespuestaPlan(
            **datos_base(registro),
            plan=plan_de(resultado),
            causas_consideradas=[causa.causa for causa in resultado.diagnostico],
        )

    @app.post(
        "/analisis-completo",
        response_model=RespuestaCompleta,
        tags=["Análisis"],
        summary="Ejecutar el análisis integral",
        description=(
            "Devuelve en una sola respuesta predicción, histórico, proyección, "
            "diagnóstico, riesgo, plan, explicación y comparativa. Es el "
            "endpoint que consume el dashboard."
        ),
        responses={
            400: {"description": "Contexto inválido"},
            422: {"description": "Petición inválida"},
        },
    )
    def analisis_completo(
        solicitud: SolicitudAnalisis,
        servicio: ServicioAnalisis = Depends(obtener_servicio),
    ) -> RespuestaCompleta:
        """Proyecta el resultado completo para la interfaz."""
        registro = servicio.ejecutar(solicitud)
        resultado = registro.resultado
        return RespuestaCompleta(
            **datos_base(registro),
            prediccion=prediccion_de(resultado),
            cumplimiento_pct=resultado.cumplimiento_pct,
            historial=historial_de_contexto(registro.contexto),
            proyeccion=proyeccion_de(registro.contexto, resultado),
            causas=causas_de(resultado),
            riesgo=riesgo_de(resultado),
            plan=plan_de(resultado),
            explicacion=resultado.explicacion,
            comparativa=comparativa_de(resultado),
            reglas_disparadas=list(resultado.reglas_disparadas),
        )

    @app.get(
        "/explicar/{id}",
        response_model=RespuestaExplicacion,
        tags=["Explicaciones"],
        summary="Recuperar la explicación de un análisis",
        description="Busca por identificador UUID un análisis ejecutado previamente.",
        responses={404: {"description": "No existe un análisis con ese identificador"}},
    )
    def explicar(
        id: str,
        repositorio: RepositorioResultados = Depends(obtener_repositorio),
    ) -> RespuestaExplicacion:
        """Devuelve la explicación unificada y la evidencia que la respalda."""
        registro = repositorio.obtener(id)
        if registro is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "codigo": "no_encontrado",
                    "mensaje": f"No existe un análisis con identificador '{id}'",
                },
            )
        resultado = registro.resultado
        return RespuestaExplicacion(
            id=registro.id,
            texto=resultado.explicacion,
            factores_shap=list(resultado.prediccion.principales_factores),
            causas=causas_de(resultado),
            riesgo=riesgo_de(resultado),
            plan=plan_de(resultado),
            reglas_disparadas=list(resultado.reglas_disparadas),
            comparativa=comparativa_de(resultado),
        )

    @app.get(
        "/salud",
        response_model=RespuestaSalud,
        tags=["Operación"],
        summary="Verificar el estado del servicio",
        description=(
            "Comprueba que el modelo, las reglas, el dataset y el benchmark " "estén disponibles."
        ),
        responses={503: {"description": "Falta algún artefacto requerido"}},
    )
    def salud(
        artefactos: dict[str, bool] = Depends(estado_artefactos),
    ) -> RespuestaSalud:
        """Informa del estado del servicio y de sus artefactos."""
        faltantes = [nombre for nombre, disponible in artefactos.items() if not disponible]
        if faltantes:
            raise HTTPException(
                status_code=503,
                detail={
                    "codigo": "servicio_no_disponible",
                    "mensaje": f"Artefactos no disponibles: {', '.join(faltantes)}",
                    "artefactos": artefactos,
                },
            )
        return RespuestaSalud(
            estado="saludable",
            version=version,
            mensaje="API y artefactos disponibles",
            artefactos=artefactos,
        )

    @app.get(
        "/catalogos",
        response_model=RespuestaCatalogos,
        tags=["Operación"],
        summary="Obtener catálogos del dominio",
        description=(
            "Devuelve sucursales, categorías y temporadas para los selectores " "del dashboard."
        ),
    )
    def catalogos() -> RespuestaCatalogos:
        """Devuelve los catálogos configurados en ``config.py``."""
        return RespuestaCatalogos(
            sucursales=list(SUCURSALES),
            categorias=list(CATEGORIAS),
            temporadas=list(TEMPORADAS),
        )

    @app.get(
        "/benchmark",
        response_model=RespuestaBenchmark,
        tags=["Datos de apoyo"],
        summary="Obtener el benchmark de búsqueda",
        description=(
            "Lee el CSV generado en la Fase 5 con métricas por algoritmo y "
            "escenario para la pestaña de comparación del dashboard."
        ),
        responses={503: {"description": "El CSV de benchmark no está disponible"}},
    )
    def benchmark() -> RespuestaBenchmark:
        """Expone el benchmark de la Fase 5 sin recalcular los algoritmos."""
        if not ARCHIVO_BENCHMARK_CSV.is_file():
            raise HTTPException(
                status_code=503,
                detail={
                    "codigo": "benchmark_no_disponible",
                    "mensaje": "No se encontró docs/benchmark_busqueda.csv",
                },
            )
        with ARCHIVO_BENCHMARK_CSV.open(encoding="utf-8", newline="") as archivo:
            filas = [
                FilaBenchmark(
                    algoritmo=fila["algoritmo"],
                    escenario=fila["escenario"],
                    encontrado=fila["encontrado"].strip().lower() in {"true", "1", "sí", "si"},
                    costo=float(fila["costo"]),
                    nodos_expandidos=int(fila["nodos_expandidos"]),
                    nodos_generados=int(fila["nodos_generados"]),
                    profundidad=int(fila["profundidad"]),
                    tiempo=float(fila["tiempo"]),
                )
                for fila in csv.DictReader(archivo)
            ]
        escenarios = list(dict.fromkeys(fila.escenario for fila in filas))
        return RespuestaBenchmark(escenarios=escenarios, filas=filas)

    return app


app = crear_app()
"""Aplicación por defecto para ``uvicorn api.main:app``."""
