"""Dependencias inyectables de la API, sin objetos mutables globales.

Cada petición obtiene el servicio y el repositorio desde ``request.app.state``
mediante ``Depends``. La fábrica del sistema se ejecuta por petición porque la
memoria de trabajo y el motor acumulan estado entre ejecuciones.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias, cast
from uuid import uuid4

import pandas as pd
from fastapi import Request

from api.esquemas import SolicitudAnalisis
from config import ARCHIVO_VENTAS_CRUDO
from core.contexto import ContextoNegocio, contexto_desde_dataframe
from core.fabrica import construir_contexto_desde_csv
from core.resultado import ResultadoSistema
from core.sistema import SistemaInteligente

FabricaSistema: TypeAlias = Callable[[], SistemaInteligente]
"""Fábrica que devuelve una fachada nueva por petición."""

ConstructorContexto: TypeAlias = Callable[..., ContextoNegocio]
"""Constructor de contexto; recibe la solicitud y la ruta del dataset."""


@dataclass(frozen=True, slots=True)
class AnalisisGuardado:
    """Resultado completo de una ejecución, identificado por UUID."""

    id: str
    resultado: ResultadoSistema
    contexto: ContextoNegocio


class RepositorioResultados:
    """Almacén en memoria de los análisis recientes de la API."""

    def __init__(self) -> None:
        """Inicializa un repositorio vacío y seguro para hilos."""
        self._registros: dict[str, AnalisisGuardado] = {}
        self._cerrojo = threading.Lock()

    def guardar(self, resultado: ResultadoSistema, contexto: ContextoNegocio) -> AnalisisGuardado:
        """Guarda un análisis con un identificador ``uuid4`` y lo devuelve."""
        registro = AnalisisGuardado(
            id=str(uuid4()),
            resultado=resultado,
            contexto=contexto,
        )
        with self._cerrojo:
            self._registros[registro.id] = registro
        return registro

    def obtener(self, identificador: str) -> AnalisisGuardado | None:
        """Devuelve el análisis solicitado o ``None`` si no existe."""
        with self._cerrojo:
            return self._registros.get(identificador)


def contexto_desde_solicitud(
    solicitud: SolicitudAnalisis,
    ruta_csv: Path | str = ARCHIVO_VENTAS_CRUDO,
) -> ContextoNegocio:
    """Construye el contexto de negocio a partir de una petición validada."""
    sobrescribir = solicitud.para_contexto()
    if solicitud.historial is not None:
        crudo = pd.DataFrame([semana.model_dump() for semana in solicitud.historial])
        return contexto_desde_dataframe(
            crudo,
            solicitud.sucursal,
            solicitud.categoria,
            fecha_corte=solicitud.fecha_corte,
            semanas=solicitud.semanas,
            **sobrescribir,
        )
    return construir_contexto_desde_csv(
        solicitud.sucursal,
        solicitud.categoria,
        ruta_csv=ruta_csv,
        fecha_corte=solicitud.fecha_corte,
        semanas=solicitud.semanas,
        **sobrescribir,
    )


class ServicioAnalisis:
    """Orquesta la ejecución de la fachada y el guardado del resultado."""

    def __init__(
        self,
        fabrica: FabricaSistema,
        constructor_contexto: ConstructorContexto = contexto_desde_solicitud,
        repositorio: RepositorioResultados | None = None,
        ruta_csv: Path | str = ARCHIVO_VENTAS_CRUDO,
    ) -> None:
        """Recibe todas las colaboraciones; no crea dependencias por su cuenta."""
        self.fabrica = fabrica
        self.constructor_contexto = constructor_contexto
        self.repositorio = repositorio or RepositorioResultados()
        self.ruta_csv = ruta_csv

    def ejecutar(self, solicitud: SolicitudAnalisis) -> AnalisisGuardado:
        """Ejecuta ``SistemaInteligente.ejecutar`` y persiste el resultado."""
        contexto = self.constructor_contexto(
            solicitud,
            ruta_csv=self.ruta_csv,
        )
        sistema = self.fabrica()
        resultado = sistema.ejecutar(contexto)
        return self.repositorio.guardar(resultado, contexto)


def obtener_servicio(request: Request) -> ServicioAnalisis:
    """Dependencia que expone el servicio configurado en la aplicación."""
    return cast(ServicioAnalisis, request.app.state.servicio)


def obtener_repositorio(request: Request) -> RepositorioResultados:
    """Dependencia que expone el repositorio configurado en la aplicación."""
    return cast(RepositorioResultados, request.app.state.repositorio)


def estado_artefactos(request: Request) -> dict[str, bool]:
    """Dependencia que informa si los artefactos requeridos están disponibles."""
    rutas: tuple[Path, ...] = cast(tuple[Path, ...], request.app.state.rutas_artefactos)
    return {ruta.name: ruta.is_file() for ruta in rutas}
