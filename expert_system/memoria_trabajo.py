"""Memoria de trabajo del sistema experto.

Cada dato se registra como un :class:`Hecho` inmutable con atributo, valor,
factor de certeza, origen y marcas de tiempo. La memoria conserva *todas* las
evidencias recibidas para una misma hipótesis; la consulta devuelve la
combinación MYCIN de esa evidencia, de modo que nunca se pierde el rastro de
qué regla o qué usuario aportó cada certeza.
"""

from __future__ import annotations

import logging
from collections.abc import Hashable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from expert_system.factores_certeza import combinar_fc, validar_fc

LOGGER = logging.getLogger(__name__)

_SIN_VALOR = object()


def _ahora() -> str:
    """Devuelve la hora actual en ISO 8601 y UTC."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def _texto(valor: object) -> str:
    """Formatea un valor para los mensajes y las explicaciones."""
    if isinstance(valor, bool):
        return "sí" if valor else "no"
    return str(valor)


@dataclass(frozen=True, slots=True)
class Hecho:
    """Hecho tipado registrado en la memoria de trabajo.

    Attributes:
        atributo: Nombre de la variable, independiente del dominio.
        valor: Valor observado o concluido; debe ser hashable.
        fc: Factor de certeza en ``[-1, 1]``.
        origen: Quién aportó el hecho: ``usuario``, ``regla:R01``, etc.
        detalle: Cómo se derivó (por ejemplo, factores intermedios).
        paso: Orden de registro asignado por la memoria; ``0`` si aún no se asignó.
        momento: Instante de registro en ISO 8601.
    """

    atributo: str
    valor: Hashable
    fc: float
    origen: str
    detalle: str = ""
    paso: int = 0
    momento: str = field(default_factory=_ahora)

    def __post_init__(self) -> None:
        """Valida los campos y normaliza el factor de certeza."""
        if not isinstance(self.atributo, str) or not self.atributo.strip():
            raise ValueError("El atributo del hecho no puede estar vacío")
        if not isinstance(self.origen, str) or not self.origen.strip():
            raise ValueError("El origen del hecho no puede estar vacío")
        if not isinstance(self.valor, Hashable):
            raise TypeError("El valor del hecho debe ser hashable")
        if isinstance(self.paso, bool) or not isinstance(self.paso, int) or self.paso < 0:
            raise ValueError("El paso debe ser un entero no negativo")
        object.__setattr__(self, "fc", validar_fc(self.fc))

    @property
    def descripcion(self) -> str:
        """Devuelve una descripción legible con certeza, origen y paso."""
        return (
            f"{self.atributo}={_texto(self.valor)} (FC {self.fc:+.2f}; "
            f"origen: {self.origen}; paso {self.paso})"
        )


class MemoriaTrabajo:
    """Almacén de hechos con consulta, actualización y trazabilidad.

    Las evidencias se agrupan por ``(atributo, valor)``. Si dos reglas
    concluyen lo mismo, sus factores se combinan con MYCIN. Si concluyen
    valores distintos para el mismo atributo, :meth:`consultar` sin valor
    devuelve la hipótesis con mayor certeza absoluta.
    """

    def __init__(self) -> None:
        """Inicializa una memoria vacía."""
        self._evidencias: dict[tuple[str, Hashable], list[Hecho]] = {}
        self._contador = 0

    def registrar(self, hecho: Hecho) -> Hecho:
        """Agrega un hecho y devuelve la hipótesis combinada resultante.

        Args:
            hecho: Hecho validado a registrar.

        Returns:
            Hecho representativo de toda la evidencia de esa hipótesis.
        """
        if hecho.paso == 0:
            self._contador += 1
            hecho = replace(hecho, paso=self._contador)
        else:
            self._contador = max(self._contador, hecho.paso)
        clave = (hecho.atributo, hecho.valor)
        self._evidencias.setdefault(clave, []).append(hecho)
        LOGGER.debug("Hecho registrado: %s", hecho.descripcion)
        return self._combinado(clave)

    def actualizar(
        self,
        atributo: str,
        valor: Hashable,
        fc: float,
        origen: str,
        detalle: str = "",
    ) -> Hecho:
        """Crea y registra un hecho sin necesidad de instanciar :class:`Hecho`.

        Args:
            atributo: Nombre de la variable.
            valor: Valor observado o concluido.
            fc: Factor de certeza en ``[-1, 1]``.
            origen: Quién aportó el hecho.
            detalle: Cómo se derivó.

        Returns:
            Hecho combinado resultante.
        """
        return self.registrar(Hecho(atributo, valor, fc, origen, detalle))

    def consultar(
        self,
        atributo: str,
        valor: object = _SIN_VALOR,
    ) -> Hecho | None:
        """Consulta la certeza acumulada sobre un atributo o una hipótesis concreta.

        Args:
            atributo: Variable a consultar.
            valor: Valor concreto. Si se omite, se devuelve la hipótesis más
                cierta entre todos los valores registrados para el atributo.

        Returns:
            Hecho combinado, o ``None`` si no hay evidencia.
        """
        if valor is not _SIN_VALOR:
            if not isinstance(valor, Hashable):
                raise TypeError("El valor consultado debe ser hashable")
            clave = (atributo, valor)
            return self._combinado(clave) if clave in self._evidencias else None

        candidatos = [self._combinado(clave) for clave in self._evidencias if clave[0] == atributo]
        if not candidatos:
            return None
        return max(candidatos, key=lambda hecho: abs(hecho.fc))

    def evidencias(self, atributo: str, valor: object = _SIN_VALOR) -> tuple[Hecho, ...]:
        """Devuelve todas las evidencias crudas de un atributo o hipótesis.

        Args:
            atributo: Variable a consultar.
            valor: Valor concreto opcional.

        Returns:
            Tupla de hechos en orden de registro.
        """
        if valor is not _SIN_VALOR:
            return tuple(self._evidencias.get((atributo, valor), ()))
        return tuple(
            hecho
            for (nombre, _), lista in self._evidencias.items()
            if nombre == atributo
            for hecho in lista
        )

    def historial(self) -> tuple[Hecho, ...]:
        """Devuelve todos los hechos crudos en orden de registro."""
        hechos = (hecho for lista in self._evidencias.values() for hecho in lista)
        return tuple(sorted(hechos, key=lambda hecho: hecho.paso))

    def atributos(self) -> tuple[str, ...]:
        """Devuelve los nombres de atributos con evidencia, sin repetir."""
        return tuple(dict.fromkeys(nombre for nombre, _ in self._evidencias))

    def contiene(self, atributo: str, valor: object = _SIN_VALOR) -> bool:
        """Indica si existe evidencia para el atributo o hipótesis indicada."""
        if valor is _SIN_VALOR:
            return any(nombre == atributo for nombre, _ in self._evidencias)
        return (atributo, valor) in self._evidencias

    def __len__(self) -> int:
        """Devuelve la cantidad de hechos crudos registrados."""
        return sum(len(lista) for lista in self._evidencias.values())

    def _combinado(self, clave: tuple[str, Hashable]) -> Hecho:
        """Combina todas las evidencias de una hipótesis."""
        hechos = self._evidencias[clave]
        referencia = max(hechos, key=lambda hecho: abs(hecho.fc))
        return replace(
            referencia,
            fc=combinar_fc(*(hecho.fc for hecho in hechos)),
            detalle="; ".join(
                f"{hecho.origen}: {hecho.detalle or 'dato directo'}" for hecho in hechos
            ),
        )
