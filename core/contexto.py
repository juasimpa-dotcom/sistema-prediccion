"""Contexto de negocio de una sucursal/categoría y su traducción a hechos.

El contexto es el único argumento de :meth:`core.sistema.SistemaInteligente.ejecutar`.
Contiene el historial crudo necesario para el modelo y los datos observados que
alimentan al sistema experto y a lógica difusa. Las funciones de este módulo son
puras: no construyen dependencias ni acceden a archivos.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

import pandas as pd

from config import (
    AFLUENCIA_BASE_SUCURSAL,
    CATEGORIAS,
    PERSONAL_BASE_CATEGORIA,
    PRESUPUESTO_PREDETERMINADO_BS,
    SUCURSALES,
)


def _como_float(valor: object, defecto: float = 0.0) -> float:
    """Convierte un valor csv/dataframe a float sin propagar NaN."""
    try:
        resultado = float(valor)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return defecto
    return resultado if pd.notna(resultado) else defecto


def _como_bool(valor: object, defecto: bool = False) -> bool:
    """Interpreta booleanos de pandas, CSV y texto en español."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return defecto
    if isinstance(valor, str):
        return valor.strip().lower() in {"true", "1", "sí", "si", "yes", "verdadero"}
    return bool(valor)


@dataclass(frozen=True, slots=True)
class ContextoNegocio:
    """Situación cerrada de una sucursal y categoría sobre la que razonar.

    Attributes:
        sucursal: Nombre del catálogo configurado.
        categoria: Categoría del catálogo configurado.
        historial: Semanas crudas ordenadas, con la semana ``t`` al final.
        fecha_objetivo: Semana ``t + 1`` a predecir; por defecto se deriva del historial.
        meta_bs: Meta explícita. Si se omite, se usa la meta histórica por ``factor_meta``.
        factor_meta: Ajuste de la meta histórica, útil para escenarios de estrés.
        presupuesto_bs: Fondo máximo disponible para el plan de acciones.
        stock_inicial: Stock de la semana ``t``; se toma del historial si se omite.
        merma_inicial: Merma de la semana ``t``; se toma del historial si se omite.
        personal_inicial: Dotación de la semana ``t``; se toma del historial si se omite.
        afluencia: Clientes de la semana ``t``; se toma del historial si se omite.
        stock_cobertura: Unidades disponibles por unidad vendida; se deriva si se omite.
        afluencia_rel: Afluencia relativa a la media del historial; se deriva si se omite.
        personal_rel: Dotación relativa a la base de la categoría; se deriva si se omite.
        descuento_pct: Descuento vigente; se toma del historial si se omite.
        temperatura_media: Temperatura de la semana; se toma del historial si se omite.
        precio_vs_competencia: Ratio de precio propio frente al de la competencia.
        es_perecible: Si la categoría es perecible.
        en_promocion: Si la semana ``t`` tuvo promoción; se toma del historial si se omite.
        es_feriado: Si la semana ``t`` contiene feriado; se toma del historial si se omite.
        hay_excedente_en_otra_sucursal: Excedente disponible para reasignar.
        reabastecimiento_tardia: Si el proveedor tarda en reponer.
    """

    sucursal: str
    categoria: str
    historial: tuple[Mapping[str, object], ...]
    fecha_objetivo: date | str | None = None
    meta_bs: float | None = None
    factor_meta: float = 1.0
    presupuesto_bs: float = PRESUPUESTO_PREDETERMINADO_BS
    stock_inicial: float | None = None
    merma_inicial: float | None = None
    personal_inicial: float | None = None
    afluencia: float | None = None
    stock_cobertura: float | None = None
    afluencia_rel: float | None = None
    personal_rel: float | None = None
    descuento_pct: float | None = None
    temperatura_media: float | None = None
    precio_vs_competencia: float = 1.0
    es_perecible: bool = True
    en_promocion: bool | None = None
    es_feriado: bool | None = None
    hay_excedente_en_otra_sucursal: bool = False
    reabastecimiento_tardia: bool = False

    def __post_init__(self) -> None:
        """Valida catálogos, historial y parámetros numéricos básicos."""
        if self.sucursal not in SUCURSALES:
            raise ValueError(f"Sucursal desconocida: {self.sucursal}")
        if self.categoria not in CATEGORIAS:
            raise ValueError(f"Categoría desconocida: {self.categoria}")
        if not self.historial:
            raise ValueError("El contexto requiere al menos una semana de historial")
        if self.factor_meta <= 0:
            raise ValueError("factor_meta debe ser positivo")
        if self.presupuesto_bs < 0:
            raise ValueError("presupuesto_bs no puede ser negativo")

    @property
    def ultima_fila(self) -> Mapping[str, object]:
        """Devuelve la última semana cerrada del historial."""
        return self.historial[-1]

    def entrada_prediccion(self) -> dict[str, object]:
        """Devuelve la entrada que consume :class:`ml.predictor.PredictorVentas`."""
        return {
            "historial": [dict(fila) for fila in self.historial],
            "fecha_objetivo": self.fecha_objetivo,
        }

    def meta_efectiva(self) -> float:
        """Devuelve la meta semanal vigente, con el ajuste del escenario."""
        if self.meta_bs is not None:
            return float(self.meta_bs)
        historica = _como_float(self.ultima_fila.get("meta_ventas_bs"))
        if historica <= 0:
            historica = AFLUENCIA_BASE_SUCURSAL[self.sucursal]
        return historica * self.factor_meta

    def datos_observados(self) -> dict[str, object]:
        """Resuelve los hechos numéricos y simbólicos del contexto.

        Returns:
            Mapping con los hechos que el motor experto y el sistema difuso
            necesitan. Los valores ausentes se derivan del historial.
        """
        fila = self.ultima_fila
        stock = _como_float(self.stock_inicial, _como_float(fila.get("stock_inicial"), 1.0))
        unidades = max(_como_float(fila.get("unidades_vendidas"), 1.0), 1.0)
        cobertura = (
            float(self.stock_cobertura) if self.stock_cobertura is not None else stock / unidades
        )

        afluencia = _como_float(self.afluencia, _como_float(fila.get("afluencia_clientes")))
        series = [_como_float(item.get("afluencia_clientes")) for item in self.historial]
        media_afluencia = sum(series) / len(series) if series else afluencia
        afluencia_rel = (
            float(self.afluencia_rel)
            if self.afluencia_rel is not None
            else afluencia / max(media_afluencia, 1.0)
        )

        personal = _como_float(
            self.personal_inicial, _como_float(fila.get("personal_asignado"), 1.0)
        )
        personal_base = PERSONAL_BASE_CATEGORIA[self.categoria]
        personal_rel = (
            float(self.personal_rel)
            if self.personal_rel is not None
            else personal / max(float(personal_base), 1.0)
        )

        return {
            "stock_inicial": stock,
            "unidades_vendidas": unidades,
            "stock_cobertura": round(cobertura, 4),
            "merma_pct": _como_float(self.merma_inicial, _como_float(fila.get("merma_pct"))),
            "afluencia_clientes": afluencia,
            "afluencia_rel": round(afluencia_rel, 4),
            "personal_asignado": personal,
            "personal_rel": round(personal_rel, 4),
            "descuento_pct": _como_float(
                self.descuento_pct, _como_float(fila.get("descuento_pct"))
            ),
            "temperatura_media": _como_float(
                self.temperatura_media, _como_float(fila.get("temperatura_media"))
            ),
            "temporada": str(fila.get("temporada", "media")),
            "precio_vs_competencia": float(self.precio_vs_competencia),
            "es_perecible": bool(self.es_perecible),
            "en_promocion": _como_bool(self.en_promocion, _como_bool(fila.get("en_promocion"))),
            "es_feriado": _como_bool(self.es_feriado, _como_bool(fila.get("es_feriado_semana"))),
            "hay_excedente_en_otra_sucursal": bool(self.hay_excedente_en_otra_sucursal),
            "reabastecimiento_tardia": bool(self.reabastecimiento_tardia),
        }


def contexto_desde_dataframe(
    crudo: pd.DataFrame,
    sucursal: str,
    categoria: str,
    fecha_corte: str | pd.Timestamp | None = None,
    semanas: int = 8,
    **sobrescribir: object,
) -> ContextoNegocio:
    """Construye un contexto a partir del dataset crudo de la Fase 1.

    Args:
        crudo: Dataset con una fila por semana, sucursal y categoría.
        sucursal: Sucursal seleccionada.
        categoria: Categoría seleccionada.
        fecha_corte: Última semana cerrada permitida; por defecto todas.
        semanas: Cantidad de semanas consecutivas a conservar (mínimo 8).
        **sobrescribir: Campos de :class:`ContextoNegocio` a forzar.

    Returns:
        Contexto listo para ``ejecutar``.

    Raises:
        ValueError: Si no hay suficientes semanas para la serie pedida.
    """
    if semanas < 8:
        raise ValueError("Se requieren al menos 8 semanas para preparar la entrada del modelo")
    serie = crudo.loc[
        (crudo["sucursal"] == sucursal) & (crudo["categoria"] == categoria)
    ].sort_values("fecha_semana")
    if fecha_corte is not None:
        serie = serie.loc[serie["fecha_semana"] <= pd.Timestamp(fecha_corte)]
    serie = serie.tail(semanas)
    if len(serie) < semanas:
        raise ValueError(f"No hay {semanas} semanas para {sucursal}/{categoria}")

    historial = tuple(fila.to_dict() for _, fila in serie.iterrows())
    valores: dict[str, object] = {
        "sucursal": sucursal,
        "categoria": categoria,
        "historial": historial,
    }
    valores.update(sobrescribir)
    return ContextoNegocio(**valores)  # type: ignore[arg-type]
