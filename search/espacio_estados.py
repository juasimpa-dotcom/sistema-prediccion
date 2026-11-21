"""Representación formal del problema de planificación como espacio de estados.

Un :class:`Problema` es una interfaz mínima e independiente del dominio: define
el estado inicial, la prueba de meta, los operadores disponibles, el estado
sucesor y el costo de cada paso. Los algoritmos de búsqueda solo conocen esa
interfaz, de modo que pueden resolverse otros problemas sin modificarse.

:class:`ProblemaPlanComercial` instancia esa interfaz para el retail boliviano.
Sus efectos y costos se leen de ``config.py`` y reproducen las relaciones del
generador de la Fase 1: la promoción eleva tráfico y conversión pero reduce el
precio, la merma merma calidad y unidades disponibles, el stock limita las
ventas y el personal mejora la conversión.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Hashable
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Generic, TypeVar

from config import (
    AFLUENCIA_BASE_SUCURSAL,
    CATEGORIAS,
    COSTO_PERSONAL_ADICIONAL_BS,
    COSTO_PROMOCION_FIJO_BS,
    COSTO_PROMOCION_POR_PUNTO_BS,
    COSTO_REASIGNACION_POR_UNIDAD_BS,
    COSTO_REDUCCION_MERMA_POR_PP_BS,
    COSTO_REPOSICION_POR_UNIDAD_BS,
    ELASTICIDAD_PERSONAL_VENTAS,
    FACTOR_PRECIO_SUCURSAL,
    INCREMENTO_PERSONAL,
    MERMA_MAXIMA_PCT,
    MERMA_MINIMA_PCT,
    NIVELES_PROMOCION,
    PARAMETROS_GENERACION,
    PENALIDAD_DEMANDA_MERMA,
    PERSONAL_BASE_CATEGORIA,
    PERSONAL_MAXIMO,
    PERSONAL_MINIMO,
    PRECIO_BASE_CATEGORIA,
    REASIGNACION_UNIDADES,
    REDUCCION_MERMA_PP,
    REPOSICION_UNIDADES,
    STOCK_MAXIMO_UNIDADES,
    SUCURSALES,
    TASA_CONVERSION_CATEGORIA,
    ParametrosGeneracion,
)

EstadoT = TypeVar("EstadoT", bound=Hashable)
AccionT = TypeVar("AccionT", bound=Hashable)


class Problema(ABC, Generic[EstadoT, AccionT]):
    """Contrato abstracto de un problema de búsqueda en espacio de estados."""

    @abstractmethod
    def estado_inicial(self) -> EstadoT:
        """Devuelve el estado desde el que comienza la búsqueda."""

    @abstractmethod
    def es_meta(self, estado: EstadoT) -> bool:
        """Indica si ``estado`` satisface el objetivo."""

    @abstractmethod
    def acciones(self, estado: EstadoT) -> tuple[AccionT, ...]:
        """Devuelve los operadores aplicables en ``estado``."""

    @abstractmethod
    def resultado(self, estado: EstadoT, accion: AccionT) -> EstadoT:
        """Devuelve el estado sucesor de aplicar ``accion`` en ``estado``."""

    @abstractmethod
    def costo_paso(self, estado: EstadoT, accion: AccionT) -> float:
        """Devuelve el costo no negativo de aplicar ``accion``."""


class TipoAccion(StrEnum):
    """Operadores comerciales disponibles en el plan."""

    PROMOCION = "promocion"
    REPONER_STOCK = "reponer_stock"
    REFORZAR_PERSONAL = "reforzar_personal"
    REDUCIR_MERMA = "reducir_merma"
    REASIGNAR_INVENTARIO = "reasignar_inventario"


@dataclass(frozen=True, slots=True)
class Accion:
    """Operador comercial con su parámetro principal.

    Attributes:
        tipo: Familia del operador.
        nivel: Descuento porcentual para promociones; se ignora en los demás.
    """

    tipo: TipoAccion
    nivel: float = 0.0

    @property
    def descripcion(self) -> str:
        """Devuelve el operador en texto legible para el plan."""
        if self.tipo == TipoAccion.PROMOCION:
            return f"promocion({self.nivel:.0f}%)"
        if self.tipo == TipoAccion.REPONER_STOCK:
            return f"reponer_stock(+{REPOSICION_UNIDADES}u)"
        if self.tipo == TipoAccion.REASIGNAR_INVENTARIO:
            return f"reasignar_inventario(+{REASIGNACION_UNIDADES}u)"
        if self.tipo == TipoAccion.REFORZAR_PERSONAL:
            return f"reforzar_personal(+{INCREMENTO_PERSONAL})"
        return f"reducir_merma(-{REDUCCION_MERMA_PP:g}pp)"

    @property
    def etiqueta(self) -> str:
        """Devuelve el operador con etiquetas en español para la interfaz."""
        if self.tipo == TipoAccion.PROMOCION:
            return f"Promoción {self.nivel:.0f} %"
        if self.tipo == TipoAccion.REPONER_STOCK:
            return f"Reponer stock (+{REPOSICION_UNIDADES} u)"
        if self.tipo == TipoAccion.REASIGNAR_INVENTARIO:
            return f"Reasignar inventario (+{REASIGNACION_UNIDADES} u)"
        if self.tipo == TipoAccion.REFORZAR_PERSONAL:
            return f"Reforzar personal (+{INCREMENTO_PERSONAL})"
        return f"Reducir merma (−{REDUCCION_MERMA_PP:g} pp)"

    def __str__(self) -> str:
        """Usa la descripción legible al imprimir el plan."""
        return self.descripcion


@dataclass(frozen=True, slots=True)
class EstadoPlan:
    """Situación inmutable y hashable de una sucursal/categoría.

    Attributes:
        stock: Unidades disponibles al inicio de la semana.
        descuento_pct: Nivel de promoción vigente, en porcentaje.
        personal: Personas asignadas a la categoría.
        merma_pct: Merma esperada, en puntos porcentuales.
        ventas_proyectadas: Ventas estimadas para la semana, en bolivianos.
        presupuesto_restante: Presupuesto aún disponible para nuevas acciones.
    """

    stock: int
    descuento_pct: float
    personal: int
    merma_pct: float
    ventas_proyectadas: float
    presupuesto_restante: float

    @property
    def etiqueta(self) -> str:
        """Resume el estado con magnitudes comprensibles para una persona."""
        return (
            f"Stock {self.stock} u · descuento {self.descuento_pct:g} % · "
            f"personal {self.personal} · merma {self.merma_pct:g} % · "
            f"Bs {self.ventas_proyectadas:,.0f}"
        )

    @property
    def detalle(self) -> str:
        """Añade el presupuesto disponible al resumen del estado."""
        return f"{self.etiqueta} · presupuesto libre Bs {self.presupuesto_restante:,.0f}"

    def __str__(self) -> str:
        """Muestra el estado legible en la traza de nodos."""
        return self.etiqueta


class ProblemaPlanComercial(Problema[EstadoPlan, Accion]):
    """Plan de acciones comerciales que alcanza la meta al menor costo.

    El estado acumula las palancas de decisión y el presupuesto restante; las
    ventas proyectadas se recalculan de forma determinista con el mismo modelo
    del simulador de la Fase 1. Los operadores son finitos y el presupuesto es
    monótonamente decreciente, por lo que el espacio de estados es finito.

    Attributes:
        sucursal: Nombre de la sucursal.
        categoria: Categoría de producto.
        meta_bs: Ventas mínimas requeridas.
        presupuesto_bs: Presupuesto total de la campaña.
        stock_inicial: Unidades disponibles antes de planear.
        merma_inicial: Merma esperada sin intervención.
        personal_inicial: Dotación inicial.
        stock_maximo: Tope de unidades por reabastecimiento y reasignación.
        personal_maximo: Tope de personas asignadas.
    """

    def __init__(
        self,
        sucursal: str = "El Alto",
        categoria: str = "pollo",
        meta_bs: float = 24_000.0,
        presupuesto_bs: float = 9_000.0,
        stock_inicial: int = 400,
        merma_inicial: float = 12.0,
        personal_inicial: int | None = None,
        afluencia: float | None = None,
        stock_maximo: int = STOCK_MAXIMO_UNIDADES,
        personal_maximo: int = PERSONAL_MAXIMO,
        niveles_promocion: tuple[float, ...] = NIVELES_PROMOCION,
        parametros: ParametrosGeneracion = PARAMETROS_GENERACION,
        permitir_reasignacion: bool = True,
        permitir_reducir_merma: bool = True,
    ) -> None:
        """Construye y valida una instancia del problema de planificación.

        Args:
            sucursal: Sucursal del catálogo configurado.
            categoria: Categoría del catálogo configurado.
            meta_bs: Objetivo de ventas semanales en bolivianos.
            presupuesto_bs: Fondo máximo a invertir.
            stock_inicial: Unidades disponibles al inicio.
            merma_inicial: Merma porcentual inicial.
            personal_inicial: Dotación inicial; por defecto la base de categoría.
            afluencia: Clientes esperados; por defecto los de la sucursal.
            stock_maximo: Tope de stock alcanzable con los operadores.
            personal_maximo: Tope de dotación alcanzable.
            niveles_promocion: Descuentos permitidos, incluido el 0.
            parametros: Elasticidades del generador de datos.
            permitir_reasignacion: Si se ofrece el operador de reasignación.
            permitir_reducir_merma: Si se ofrece el operador de reducción de merma.

        Raises:
            TypeError: Si ``parametros`` no es del tipo esperado.
            ValueError: Si algún valor está fuera de rangos válidos.
        """
        if sucursal not in SUCURSALES:
            raise ValueError(f"Sucursal desconocida: {sucursal}")
        if categoria not in CATEGORIAS:
            raise ValueError(f"Categoría desconocida: {categoria}")
        if not isinstance(parametros, ParametrosGeneracion):
            raise TypeError("parametros debe ser ParametrosGeneracion")
        if meta_bs <= 0 or presupuesto_bs < 0:
            raise ValueError("La meta debe ser positiva y el presupuesto no negativo")
        if stock_inicial < 0 or stock_maximo <= stock_inicial:
            raise ValueError("Se requiere 0 <= stock_inicial < stock_maximo")
        if not MERMA_MINIMA_PCT <= merma_inicial <= MERMA_MAXIMA_PCT:
            raise ValueError("La merma inicial está fuera del rango permitido")
        if not niveles_promocion or niveles_promocion[0] != 0.0:
            raise ValueError("Los niveles de promoción deben empezar en 0")
        if any(a < 0 or a >= 100 for a in niveles_promocion):
            raise ValueError("Los descuentos deben estar en [0, 100)")
        if any(b <= a for a, b in zip(niveles_promocion, niveles_promocion[1:], strict=False)):
            raise ValueError("Los niveles de promoción deben estar ordenados")
        personal_referencia = PERSONAL_BASE_CATEGORIA[categoria]
        personal_inicial = personal_inicial or personal_referencia
        if not PERSONAL_MINIMO <= personal_inicial <= personal_maximo:
            raise ValueError("La dotación inicial debe estar entre el mínimo y el máximo")
        afluencia = afluencia if afluencia is not None else AFLUENCIA_BASE_SUCURSAL[sucursal]
        if afluencia <= 0:
            raise ValueError("La afluencia debe ser positiva")

        self.sucursal = sucursal
        self.categoria = categoria
        self.meta_bs = float(meta_bs)
        self.presupuesto_bs = float(presupuesto_bs)
        self.stock_inicial = int(stock_inicial)
        self.merma_inicial = float(merma_inicial)
        self.personal_inicial = int(personal_inicial)
        self.afluencia = float(afluencia)
        self.stock_maximo = int(stock_maximo)
        self.personal_maximo = int(personal_maximo)
        self.niveles_promocion = tuple(niveles_promocion)
        self.parametros = parametros
        self.permitir_reasignacion = bool(permitir_reasignacion)
        self.permitir_reducir_merma = bool(permitir_reducir_merma)

        self.personal_referencia = personal_referencia
        self.demanda_base = self.afluencia * TASA_CONVERSION_CATEGORIA[categoria]
        self.precio_base = PRECIO_BASE_CATEGORIA[categoria] * FACTOR_PRECIO_SUCURSAL[sucursal]
        self._calcular_cotas()

    def _calcular_cotas(self) -> None:
        """Deriva cotas superiores de ganancia y eficiencia de un solo paso.

        Se usan los peores valores posibles de las demás palancas para que las
        cotas sean válidas para cualquier estado alcanzable. Así la heurística
        resultante es admisible y consistente por construcción.
        """
        descuento_max = max(self.niveles_promocion)
        trafico_max = 1.0 + self.parametros.elasticidad_trafico_promocion * descuento_max / 100.0
        demanda_promo_max = 1.0 + self.parametros.elasticidad_promocion * descuento_max / 100.0
        factor_personal_max = (
            1.0
            + ELASTICIDAD_PERSONAL_VENTAS
            * (self.personal_maximo - self.personal_referencia)
            / self.personal_referencia
        )
        demanda_max = self.demanda_base * trafico_max * demanda_promo_max * factor_personal_max
        delta_merma = REDUCCION_MERMA_PP / 100.0

        ganancia_repo = REPOSICION_UNIDADES * self.precio_base
        ganancia_reasignacion = REASIGNACION_UNIDADES * self.precio_base
        ganancia_merma = (
            self.stock_maximo * delta_merma + demanda_max * PENALIDAD_DEMANDA_MERMA * delta_merma
        ) * self.precio_base
        # Cota de una promoción: máximo de ventas sobre los descuentos permitidos,
        # con stock, personal y merma en sus peores valores. El factor de precio
        # decreciente se conserva para no sobreestimar los descuentos grandes.
        ganancia_promo = max(
            demanda_max * self.precio_base * (1.0 - descuento / 100.0)
            for descuento in self.niveles_promocion
        )
        ganancia_personal = (
            self.demanda_base
            * trafico_max
            * demanda_promo_max
            * ELASTICIDAD_PERSONAL_VENTAS
            / self.personal_referencia
            * self.precio_base
        )

        costo_repo = REPOSICION_UNIDADES * COSTO_REPOSICION_POR_UNIDAD_BS
        costo_reasignacion = REASIGNACION_UNIDADES * COSTO_REASIGNACION_POR_UNIDAD_BS
        costo_personal = INCREMENTO_PERSONAL * COSTO_PERSONAL_ADICIONAL_BS
        costo_merma = REDUCCION_MERMA_PP * COSTO_REDUCCION_MERMA_POR_PP_BS
        niveles_positivos = [nivel for nivel in self.niveles_promocion if nivel > 0]
        costo_promo = (
            COSTO_PROMOCION_FIJO_BS + COSTO_PROMOCION_POR_PUNTO_BS * min(niveles_positivos)
            if niveles_positivos
            else math.inf
        )

        # Solo cuentan los operadores realmente ofrecidos. Incluir un operador
        # desactivado por el diagnóstico sobreestimaría G o E y rompería la
        # admisibilidad de la heurística.
        pares: list[tuple[float, float]] = [(ganancia_repo, costo_repo)]
        if self.permitir_reasignacion:
            pares.append((ganancia_reasignacion, costo_reasignacion))
        pares.append((ganancia_personal, costo_personal))
        pares.append((ganancia_promo, costo_promo))
        if self.permitir_reducir_merma:
            pares.append((ganancia_merma, costo_merma))

        self._maxima_ganancia = max((ganancia for ganancia, _ in pares), default=1.0)
        self._costo_minimo = min(
            (costo for _, costo in pares if math.isfinite(costo)), default=math.inf
        )
        self._maxima_eficiencia = max(
            (ganancia / costo for ganancia, costo in pares if math.isfinite(costo) and costo > 0),
            default=1.0,
        )

    def estado_inicial(self) -> EstadoPlan:
        """Devuelve el estado sin intervenciones comerciales."""
        inicial = EstadoPlan(
            stock=self.stock_inicial,
            descuento_pct=0.0,
            personal=self.personal_inicial,
            merma_pct=self.merma_inicial,
            ventas_proyectadas=0.0,
            presupuesto_restante=self.presupuesto_bs,
        )
        return replace(inicial, ventas_proyectadas=self.proyectar(inicial))

    def proyectar(self, estado: EstadoPlan) -> float:
        """Recalcula las ventas proyectadas a partir de las palancas del estado.

        Args:
            estado: Estado cuyas variables de decisión se evalúan.

        Returns:
            Ventas semanales estimadas en bolivianos, redondeadas a 2 decimales.
        """
        descuento = estado.descuento_pct / 100.0
        trafico = 1.0 + self.parametros.elasticidad_trafico_promocion * descuento
        demanda_promo = 1.0 + self.parametros.elasticidad_promocion * descuento
        factor_personal = (
            1.0
            + ELASTICIDAD_PERSONAL_VENTAS
            * (estado.personal - self.personal_referencia)
            / self.personal_referencia
        )
        demanda = self.demanda_base * trafico * demanda_promo * factor_personal
        calidad = 1.0 - PENALIDAD_DEMANDA_MERMA * estado.merma_pct / 100.0
        disponible = estado.stock * (1.0 - estado.merma_pct / 100.0)
        unidades = max(0.0, min(demanda * calidad, disponible))
        precio = self.precio_base * (1.0 - descuento)
        return round(unidades * precio, 2)

    def es_meta(self, estado: EstadoPlan) -> bool:
        """Indica si las ventas proyectadas alcanzan la meta."""
        return estado.ventas_proyectadas >= self.meta_bs

    def acciones(self, estado: EstadoPlan) -> tuple[Accion, ...]:
        """Devuelve los operadores aplicables que caben en el presupuesto.

        Args:
            estado: Estado actual.

        Returns:
            Operadores ordenados de forma determinista, sin estados idénticos.
        """
        candidatas: list[Accion] = []
        candidatas.extend(
            Accion(TipoAccion.PROMOCION, nivel)
            for nivel in self.niveles_promocion
            if nivel > estado.descuento_pct
        )
        if estado.stock < self.stock_maximo:
            candidatas.append(Accion(TipoAccion.REPONER_STOCK))
            if self.permitir_reasignacion:
                candidatas.append(Accion(TipoAccion.REASIGNAR_INVENTARIO))
        if estado.personal < self.personal_maximo:
            candidatas.append(Accion(TipoAccion.REFORZAR_PERSONAL))
        if (
            self.permitir_reducir_merma
            and estado.merma_pct - REDUCCION_MERMA_PP >= MERMA_MINIMA_PCT
        ):
            candidatas.append(Accion(TipoAccion.REDUCIR_MERMA))
        return tuple(
            accion
            for accion in sorted(candidatas, key=lambda item: (item.tipo.value, item.nivel))
            if self.costo_paso(estado, accion) <= estado.presupuesto_restante
        )

    def resultado(self, estado: EstadoPlan, accion: Accion) -> EstadoPlan:
        """Aplica un operador y devuelve el estado sucesor.

        Args:
            estado: Estado actual.
            accion: Operador devuelto por :meth:`acciones`.

        Returns:
            Nuevo estado, con ventas recalculadas y presupuesto descontado.

        Raises:
            TypeError: Si ``accion`` no es una :class:`Accion`.
            ValueError: Si el operador no es aplicable en este estado.
        """
        if not isinstance(accion, Accion):
            raise TypeError("La acción debe ser una Accion")
        if accion not in self.acciones(estado):
            raise ValueError(f"Acción no aplicable o fuera de presupuesto: {accion}")

        stock = estado.stock
        descuento = estado.descuento_pct
        personal = estado.personal
        merma = estado.merma_pct
        if accion.tipo == TipoAccion.PROMOCION:
            descuento = accion.nivel
        elif accion.tipo == TipoAccion.REPONER_STOCK:
            stock = min(self.stock_maximo, stock + REPOSICION_UNIDADES)
        elif accion.tipo == TipoAccion.REASIGNAR_INVENTARIO:
            stock = min(self.stock_maximo, stock + REASIGNACION_UNIDADES)
        elif accion.tipo == TipoAccion.REFORZAR_PERSONAL:
            personal = min(self.personal_maximo, personal + INCREMENTO_PERSONAL)
        else:
            merma = round(max(MERMA_MINIMA_PCT, merma - REDUCCION_MERMA_PP), 2)

        sucesor = EstadoPlan(
            stock=stock,
            descuento_pct=descuento,
            personal=personal,
            merma_pct=merma,
            ventas_proyectadas=0.0,
            presupuesto_restante=round(
                estado.presupuesto_restante - self.costo_paso(estado, accion), 2
            ),
        )
        return replace(sucesor, ventas_proyectadas=self.proyectar(sucesor))

    def costo_paso(self, estado: EstadoPlan, accion: Accion) -> float:
        """Devuelve el costo en bolivianos de un operador.

        Args:
            estado: Estado actual (no altera el costo de la promoción).
            accion: Operador a tasar.

        Returns:
            Costo no negativo en bolivianos.

        Raises:
            TypeError: Si ``accion`` no es una :class:`Accion`.
            ValueError: Si el tipo de operador es desconocido.
        """
        if not isinstance(accion, Accion):
            raise TypeError("La acción debe ser una Accion")
        if accion.tipo == TipoAccion.PROMOCION:
            return round(COSTO_PROMOCION_FIJO_BS + COSTO_PROMOCION_POR_PUNTO_BS * accion.nivel, 2)
        if accion.tipo == TipoAccion.REPONER_STOCK:
            return round(REPOSICION_UNIDADES * COSTO_REPOSICION_POR_UNIDAD_BS, 2)
        if accion.tipo == TipoAccion.REASIGNAR_INVENTARIO:
            return round(REASIGNACION_UNIDADES * COSTO_REASIGNACION_POR_UNIDAD_BS, 2)
        if accion.tipo == TipoAccion.REFORZAR_PERSONAL:
            return round(INCREMENTO_PERSONAL * COSTO_PERSONAL_ADICIONAL_BS, 2)
        if accion.tipo == TipoAccion.REDUCIR_MERMA:
            return round(REDUCCION_MERMA_PP * COSTO_REDUCCION_MERMA_POR_PP_BS, 2)
        raise ValueError(f"Tipo de acción desconocido: {accion.tipo}")

    def heuristica(self, estado: EstadoPlan) -> float:
        """Estima por lo bajo el costo restante hasta la meta.

        Dos relajaciones independientes, ambas válidas porque cada operador
        cuesta al menos ``c_min`` y aumenta las ventas a lo sumo ``G``:

        1. Hacen falta al menos ``ceil(déficit / G)`` acciones, luego
           ``h1 = c_min · ceil(déficit / G)``.
        2. Con eficiencia máxima ``E`` (Bs de venta por Bs invertido), hacen
           falta al menos ``déficit / E`` bolivianos: ``h2 = déficit / E``.

        El máximo de dos estimaciones admisibles sigue siendo admisible. Para
        consistencia, sea ``c >= c_min`` el costo de cualquier operador y ``g``
        la ganancia real, con ``g <= G`` y ``c >= g / E``:

        ``h1(s) - h1(s') <= c_min <= c`` y ``h2(s) - h2(s') = g / E <= c``.

        Por tanto ``h(s) <= c + h(s')`` para todo sucesor ``s'``; la heurística
        es admisible (nunca sobreestima) y consistente, así que A* con cierre de
        estados es óptimo sin reabrir nodos.

        Args:
            estado: Estado cuya distancia residual se estima.

        Returns:
            Cota inferior del costo restante, o infinito si no queda presupuesto
            para ningún operador.
        """
        if self.es_meta(estado):
            return 0.0
        if estado.presupuesto_restante < self._costo_minimo:
            return math.inf
        deficit = self.meta_bs - estado.ventas_proyectadas
        h1 = self._costo_minimo * math.ceil(deficit / self._maxima_ganancia)
        h2 = deficit / self._maxima_eficiencia
        return max(h1, h2)

    @property
    def descripcion(self) -> str:
        """Devuelve un resumen legible del escenario."""
        return (
            f"{self.sucursal}/{self.categoria}: meta {self.meta_bs:,.0f} Bs, "
            f"presupuesto {self.presupuesto_bs:,.0f} Bs"
        )
