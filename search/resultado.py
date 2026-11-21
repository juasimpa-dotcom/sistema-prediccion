"""Estructura de resultado y traza de nodos compartida por todos los algoritmos."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass, replace

METRICAS_RESULTADO: tuple[str, ...] = (
    "algoritmo",
    "escenario",
    "encontrado",
    "costo",
    "nodos_expandidos",
    "nodos_generados",
    "profundidad",
    "tiempo",
)


@dataclass(frozen=True, slots=True)
class NodoBusqueda:
    """Estado visitado por un algoritmo, listo para visualizar.

    Attributes:
        id: Identificador secuencial del nodo dentro de una búsqueda.
        padre_id: Identificador del nodo que lo generó; ``None`` en el inicio.
        estado: Representación legible del estado.
        accion: Operador aplicado para llegar desde el padre.
        profundidad: Cantidad de acciones desde el estado inicial.
        costo_g: Costo acumulado hasta este estado.
        heuristica_h: Estimación restante, cuando el algoritmo la calcula.
        f: Valor ``g + h`` usado para ordenar la frontera, si aplica.
        expandido: Si el nodo fue retirado de la frontera y evaluado.
        es_meta: Si este estado satisface el objetivo.
        descartado: Si se descartó por repetido o por costo superior.
        orden_expansion: Posición en que se expandió; ``None`` si no se expandió.
    """

    id: int
    padre_id: int | None
    estado: str
    accion: str
    profundidad: int
    costo_g: float
    heuristica_h: float | None = None
    f: float | None = None
    expandido: bool = False
    es_meta: bool = False
    descartado: bool = False
    orden_expansion: int | None = None

    @property
    def etiqueta(self) -> str:
        """Devuelve una etiqueta corta para el gráfico."""
        if self.id == 0:
            return "Inicio"
        if self.es_meta:
            return "Meta"
        return self.accion or f"Estado {self.id}"


class RegistroNodos:
    """Registra los estados que un algoritmo descubre, expande o descarta."""

    def __init__(self) -> None:
        """Inicializa el registro vacío."""
        self._ids: dict[Hashable, int] = {}
        self._nodos: list[NodoBusqueda] = []

    def registrar(
        self,
        estado: Hashable,
        *,
        padre_id: int | None = None,
        accion: str = "",
        profundidad: int = 0,
        costo_g: float | None = None,
        heuristica_h: float | None = None,
        f: float | None = None,
        expandido: bool = False,
        es_meta: bool = False,
        descartado: bool = False,
        orden_expansion: int | None = None,
    ) -> int:
        """Registra un estado y devuelve su identificador estable."""
        if estado not in self._ids:
            identificador = len(self._nodos)
            self._ids[estado] = identificador
            self._nodos.append(
                NodoBusqueda(
                    id=identificador,
                    padre_id=padre_id,
                    estado=str(estado),
                    accion=accion,
                    profundidad=profundidad,
                    costo_g=round(costo_g or 0.0, 2),
                    heuristica_h=heuristica_h,
                    f=f,
                    expandido=expandido,
                    es_meta=es_meta,
                    descartado=descartado,
                    orden_expansion=orden_expansion,
                )
            )
            return identificador

        identificador = self._ids[estado]
        actual = self._nodos[identificador]
        cambios: dict[str, object] = {}
        if expandido and not actual.expandido:
            cambios["expandido"] = True
            cambios["orden_expansion"] = orden_expansion
        if es_meta and not actual.es_meta:
            cambios["es_meta"] = True
        if descartado and not actual.descartado:
            cambios["descartado"] = True
        if heuristica_h is not None:
            cambios["heuristica_h"] = heuristica_h
        if f is not None:
            cambios["f"] = f
        if costo_g is not None and costo_g + 1e-9 < actual.costo_g:
            cambios.update(
                {
                    "padre_id": padre_id,
                    "accion": accion,
                    "profundidad": profundidad,
                    "costo_g": round(costo_g, 2),
                    "heuristica_h": heuristica_h,
                    "f": f,
                }
            )
        if cambios:
            self._nodos[identificador] = replace(actual, **cambios)  # type: ignore[arg-type]
        return identificador

    def nodos(self) -> tuple[NodoBusqueda, ...]:
        """Devuelve una copia inmutable de los nodos registrados."""
        return tuple(self._nodos)


@dataclass(frozen=True, slots=True)
class Resultado:
    """Trazabilidad y métricas de una búsqueda, sea informada o no.

    Attributes:
        plan: Secuencia de operadores desde el estado inicial hasta la meta.
        costo: Suma de ``costo_paso`` a lo largo del plan (0 si no hay solución).
        nodos_expandidos: Estados retirados de la frontera y evaluados.
        nodos_generados: Sucesores creados durante la búsqueda.
        profundidad: Longitud del plan; si falla, profundidad máxima explorada.
        tiempo: Segundos transcurridos, medidos con ``time.perf_counter``.
        encontrado: ``False`` cuando se agotó la frontera o el límite de profundidad.
        algoritmo: Nombre del algoritmo, para las tablas comparativas.
        escenario: Nombre del escenario, para las tablas comparativas.
        nodos: Estados visitados, con su relación padre-hijo y sus métricas.
    """

    plan: tuple[object, ...]
    costo: float
    nodos_expandidos: int
    nodos_generados: int
    profundidad: int
    tiempo: float
    encontrado: bool = True
    algoritmo: str = ""
    escenario: str = ""
    nodos: tuple[NodoBusqueda, ...] = ()

    @property
    def descripcion_plan(self) -> str:
        """Devuelve el plan en texto legible, o ``sin solución`` si no hay plan."""
        if not self.encontrado:
            return "sin solución"
        if not self.plan:
            return "sin acciones (meta inicial)"
        return " => ".join(str(accion) for accion in self.plan)

    def a_fila(self) -> dict[str, object]:
        """Convierte el resultado en una fila plana para el benchmark."""
        return {
            "algoritmo": self.algoritmo,
            "escenario": self.escenario,
            "encontrado": self.encontrado,
            "costo": round(self.costo, 2),
            "nodos_expandidos": self.nodos_expandidos,
            "nodos_generados": self.nodos_generados,
            "profundidad": self.profundidad,
            "tiempo": round(self.tiempo, 6),
        }
