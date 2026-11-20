"""Razonamiento difuso (Mamdani) e interfaz de fuzzificación del sistema experto.

Este módulo modela conceptos graduales con :mod:`scikit-fuzzy`: «stock crítico»,
«merma alta» o «cumplimiento medio» no tienen una frontera nítida, sino un
**grado de pertenencia** entre 0 y 1. El sistema se defuzzifica por centroide
para obtener un número interpretable en las variables de salida.

Diferencia entre lógica difusa y factores de certeza
----------------------------------------------------

* La **lógica difusa** representa **imprecisión** (vaguedad del concepto): el
  valor numérico se conoce, pero la etiqueta «bajo/alto» es borrosa. Un stock
  de 0.40 pertenece un poco a «crítico» y un poco a «adecuado»; ambas
  pertenencias suman información en lugar de competir.
* Los **factores de certeza** (MYCIN, ver :mod:`expert_system.factores_certeza`)
  representan **incertidumbre** (duda sobre el dato o sobre la regla): «creo con
  CF 0.8 que el stock es crítico». Aquí la etiqueta es nítida; lo dudoso es que
  sea cierta.

Se usan juntos de forma complementaria: la fuzzificación convierte cada dato
numérico en hechos simbólicos cuyo **CF es el grado de pertenencia**, y el motor
de inferencia aplica después su aritmética MYCIN. Así la imprecisión se traduce
a certeza y el motor sigue siendo genérico e independiente del dominio.

Uso:

.. code-block:: powershell

    python -m expert_system.logica_difusa
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol, runtime_checkable

import numpy as np
import skfuzzy as fuzz
import skfuzzy.control as ctrl
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from config import (
    ATRIBUTO_RIESGO_DIFUSO,
    ATRIBUTO_URGENCIA,
    DIR_FIGURAS_DIFUSAS,
    MAPEO_DIFUSO_HECHOS,
    MAPEO_SALIDAS_DIFUSAS,
    REGLAS_DIFUSAS,
    SALIDAS_DIFUSAS,
    UMBRAL_PERTENENCIA_DIFUSA,
    VARIABLES_DIFUSAS,
    RegionDifusa,
    ReglaDifusa,
    VariableDifusa,
)

LOGGER = logging.getLogger(__name__)

NOMBRES_REGIONES: Final[frozenset[str]] = frozenset({"triangular", "trapezoidal"})
CANTIDAD_PUNTOS: Final[dict[str, int]] = {"triangular": 3, "trapezoidal": 4}


@dataclass(frozen=True, slots=True)
class HechoDifuso:
    """Hecho simbólico obtenido de fuzzificar un valor numérico.

    Attributes:
        atributo: Variable lingüística; se registra en la memoria con ese nombre
            para no colisionar con el hecho numérico de origen.
        valor: Etiqueta lingüística asignada.
        fc: Grado de pertenencia, usado como factor de certeza por el motor.
        variable: Variable lingüística declarada en configuración.
        hecho_origen: Nombre del hecho numérico que se fuzzificó; vacío en las
            salidas defuzzificadas.
        origen: Procedencia del hecho, para la trazabilidad del motor.
        detalle: Información adicional (centroide, reglas activadas, etc.).
    """

    atributo: str
    valor: str
    fc: float
    variable: str
    hecho_origen: str = ""
    origen: str = "fuzzificacion"
    detalle: str = ""

    @property
    def descripcion(self) -> str:
        """Devuelve el hecho difuso en texto legible."""
        origen = f" desde {self.hecho_origen}" if self.hecho_origen else ""
        return f"{self.atributo}={self.valor} (grado {self.fc:.3f}{origen})"


@dataclass(frozen=True, slots=True)
class ResultadoDifuso:
    """Resultado de una inferencia difusa con defuzzificación por centroide.

    Attributes:
        entradas: Valores numéricos de entrada efectivamente utilizados.
        valores: Valor centroide de cada variable de salida.
        etiquetas: Etiqueta dominante en el centroide de cada salida.
        grados: Grado de pertenencia de cada etiqueta en el centroide.
        fuerzas: Fuerza de activación (min de antecedentes) de cada regla.
        hechos: Hechos simbólicos de entrada generados por la fuzzificación.
        hechos_salida: Hechos simbólicos de salida ya traducidos a atributos de
            la memoria del experto, con su CF y su trazabilidad. El motor solo
            los registra, sin conocer variables difusas ni nombres de dominio.
    """

    entradas: dict[str, float]
    valores: dict[str, float]
    etiquetas: dict[str, str]
    grados: dict[str, dict[str, float]]
    fuerzas: dict[str, float]
    hechos: tuple[HechoDifuso, ...]
    hechos_salida: tuple[HechoDifuso, ...] = ()

    @property
    def reglas_activadas(self) -> tuple[str, ...]:
        """Identificadores de las reglas con activación positiva, en orden."""
        return tuple(
            identificador for identificador, fuerza in self.fuerzas.items() if fuerza > 0.0
        )

    def descripcion(self) -> str:
        """Devuelve un resumen legible de las salidas difusas."""
        return "; ".join(
            f"{salida}={self.valores[salida]:.1f} ({self.etiquetas[salida]})"
            for salida in SALIDAS_DIFUSAS
            if salida in self.valores
        )


@runtime_checkable
class Fuzzificador(Protocol):
    """Contrato mínimo que el motor de inferencia usa sin conocer scikit-fuzzy.

    Cualquier objeto que implemente estos métodos puede sustituir a
    :class:`SistemaDifuso` en el motor. Las etiquetas y los grados de
    pertenencia son la única interfaz entre el mundo numérico y el simbólico.
    El ``ResultadoDifuso`` devuelto por :meth:`calcular` debe incluir sus
    ``hechos_salida``: son la única forma en que el motor inyecta conclusiones
    difusas en su memoria sin conocer el dominio.
    """

    def variables(self) -> tuple[str, ...]:
        """Devuelve las variables lingüísticas de entrada disponibles."""
        ...

    def etiquetas(self, variable: str) -> tuple[str, ...]:
        """Devuelve las etiquetas de una variable lingüística."""
        ...

    def pertenencia(self, variable: str, etiqueta: str, valor: float) -> float:
        """Devuelve el grado de pertenencia de ``valor`` a ``etiqueta``."""
        ...

    def fuzzificar(self, valores: Mapping[str, float]) -> tuple[HechoDifuso, ...]:
        """Convierte hechos numéricos en hechos simbólicos con CF gradual."""
        ...

    def calcular(self, valores: Mapping[str, float]) -> ResultadoDifuso:
        """Ejecuta la inferencia difusa y defuzzifica las salidas."""
        ...


class SistemaDifuso:
    """Sistema Mamdani declarado en ``config.py`` y ejecutado con scikit-fuzzy.

    Las variables, sus funciones de pertenencia y la base de reglas no se
    codifican aquí: se leen de configuración y se validan al construir el
    objeto. El sistema usa conectivos ``min``/``max`` y agregación ``max``, con
    defuzzificación por centroide.
    """

    def __init__(
        self,
        variables: Mapping[str, VariableDifusa] = VARIABLES_DIFUSAS,
        reglas: Sequence[ReglaDifusa] = REGLAS_DIFUSAS,
        mapeo: Mapping[str, str] = MAPEO_DIFUSO_HECHOS,
        umbral: float = UMBRAL_PERTENENCIA_DIFUSA,
    ) -> None:
        """Construye y valida el sistema difuso.

        Args:
            variables: Variables lingüísticas (entradas y salidas).
            reglas: Base de reglas difusas declarativas.
            mapeo: Correspondencia entre nombres de hechos numéricos y
                variables lingüísticas.
            umbral: Grado mínimo de pertenencia para generar un hecho simbólico.

        Raises:
            TypeError: Si las estructuras declaradas no tienen el tipo esperado.
            ValueError: Si hay configuración inválida, discrepante o duplicada.
        """
        if not isinstance(variables, Mapping):
            raise TypeError("Las variables difusas deben estar en un Mapping")
        if not variables:
            raise ValueError("Debe declarar al menos una variable difusa")
        if isinstance(reglas, (str, bytes)) or not isinstance(reglas, Sequence) or not reglas:
            raise ValueError("Debe declarar al menos una regla difusa")
        if not isinstance(mapeo, Mapping):
            raise TypeError("El mapeo de hechos debe ser un Mapping")
        if (
            not isinstance(umbral, (int, float))
            or isinstance(umbral, bool)
            or not 0.0 <= umbral <= 1.0
        ):
            raise ValueError("El umbral de pertenencia debe estar en [0, 1]")

        self._umbral = float(umbral)
        self._variables = dict(variables)
        self._reglas = tuple(reglas)
        self._mapeo = dict(mapeo)
        self._universos: dict[str, np.ndarray] = {}
        self._funciones: dict[str, dict[str, np.ndarray]] = {}
        self._antecedentes: dict[str, ctrl.Antecedent] = {}
        self._consecuentes: dict[str, ctrl.Consequent] = {}
        self._fuerzas: dict[str, float] = {}

        salidas = set(SALIDAS_DIFUSAS)
        for nombre, variable in self._variables.items():
            self._validar_variable(nombre, variable)
            universo = np.arange(
                variable.universo[0],
                variable.universo[1] + variable.universo[2] / 2,
                variable.universo[2],
            )
            self._universos[nombre] = universo
            self._funciones[nombre] = {}
            for etiqueta, region in variable.etiquetas.items():
                puntos = np.asarray(region.puntos, dtype=float)
                funcion = (
                    fuzz.trimf(universo, puntos)
                    if region.tipo == "triangular"
                    else fuzz.trapmf(universo, puntos)
                )
                self._funciones[nombre][etiqueta] = funcion
                if nombre in salidas:
                    consecuente = self._consecuentes.setdefault(
                        nombre, ctrl.Consequent(universo, nombre)
                    )
                    consecuente[etiqueta] = funcion
                else:
                    antecedente = self._antecedentes.setdefault(
                        nombre, ctrl.Antecedent(universo, nombre)
                    )
                    antecedente[etiqueta] = funcion

        if not salidas <= self._variables.keys():
            raise ValueError(
                f"Faltan variables de salida: {sorted(salidas - self._variables.keys())}"
            )
        for variable in self._mapeo.values():
            if variable not in self._antecedentes:
                raise ValueError(
                    f"El mapeo apunta a una variable de entrada desconocida: {variable}"
                )

        identificadores: set[str] = set()
        objetos_regla: list[ctrl.Rule] = []
        for regla in self._reglas:
            if not isinstance(regla, ReglaDifusa):
                raise TypeError("Todas las reglas difusas deben ser ReglaDifusa")
            if regla.id in identificadores:
                raise ValueError(f"Identificador de regla difusa repetido: {regla.id}")
            identificadores.add(regla.id)
            if not regla.si or not regla.entonces:
                raise ValueError(f"La regla {regla.id} necesita antecedentes y consecuentes")
            antecedentes: list[object] = []
            for variable, etiqueta in regla.si.items():
                if variable not in self._antecedentes:
                    raise ValueError(f"La regla {regla.id} usa una entrada desconocida: {variable}")
                if etiqueta not in self._funciones[variable]:
                    raise ValueError(
                        f"La regla {regla.id} usa una etiqueta desconocida: {variable}={etiqueta}"
                    )
                antecedentes.append(self._antecedentes[variable][etiqueta])
                self._fuerzas[regla.id] = 0.0
            consecuentes: list[object] = []
            for variable, etiqueta in regla.entonces.items():
                if variable not in self._consecuentes:
                    raise ValueError(f"La regla {regla.id} usa una salida desconocida: {variable}")
                if etiqueta not in self._funciones[variable]:
                    raise ValueError(
                        f"La regla {regla.id} usa una etiqueta desconocida: {variable}={etiqueta}"
                    )
                consecuentes.append(self._consecuentes[variable][etiqueta])
            premisa = antecedentes[0]
            for termino in antecedentes[1:]:
                premisa = premisa & termino  # type: ignore[attr-defined]
            objetos_regla.append(ctrl.Rule(premisa, tuple(consecuentes)))

        self._sistema = ctrl.ControlSystem(objetos_regla)
        LOGGER.info(
            "Sistema difuso construido: %d variables, %d reglas, umbral %.2f",
            len(self._variables),
            len(self._reglas),
            self._umbral,
        )

    @staticmethod
    def _validar_variable(nombre: str, variable: VariableDifusa) -> None:
        """Valida una variable lingüística declarada en configuración."""
        if not isinstance(nombre, str) or not nombre.strip():
            raise ValueError("El nombre de la variable difusa no puede estar vacío")
        if not isinstance(variable, VariableDifusa):
            raise TypeError(f"La variable {nombre} debe ser VariableDifusa")
        if len(variable.universo) != 3:
            raise ValueError(f"El universo de {nombre} debe tener (mínimo, máximo, paso)")
        minimo, maximo, paso = variable.universo
        if any(
            isinstance(valor, bool) or not isinstance(valor, (int, float))
            for valor in variable.universo
        ):
            raise TypeError(f"El universo de {nombre} debe ser numérico")
        if paso <= 0 or minimo >= maximo:
            raise ValueError(
                f"Universo inválido en {nombre}: se requiere mínimo < máximo y paso > 0"
            )
        if not variable.etiquetas:
            raise ValueError(f"La variable {nombre} necesita al menos una etiqueta")
        for etiqueta, region in variable.etiquetas.items():
            if not isinstance(etiqueta, str) or not etiqueta.strip():
                raise ValueError(f"{nombre} tiene una etiqueta vacía")
            if not isinstance(region, RegionDifusa):
                raise TypeError(f"La región {nombre}={etiqueta} debe ser RegionDifusa")
            if region.tipo not in NOMBRES_REGIONES:
                raise ValueError(
                    f"Tipo de región desconocido en {nombre}={etiqueta}: {region.tipo}"
                )
            if len(region.puntos) != CANTIDAD_PUNTOS[region.tipo]:
                raise ValueError(
                    f"{nombre}={etiqueta} requiere {CANTIDAD_PUNTOS[region.tipo]} puntos"
                )
            if any(
                isinstance(punto, bool) or not isinstance(punto, (int, float))
                for punto in region.puntos
            ):
                raise TypeError(f"Los puntos de {nombre}={etiqueta} deben ser numéricos")
            puntos = region.puntos
            if any(puntos[i] > puntos[i + 1] for i in range(len(puntos) - 1)):
                raise ValueError(f"Los puntos de {nombre}={etiqueta} deben estar ordenados")
            if puntos[0] < minimo or puntos[-1] > maximo:
                raise ValueError(
                    f"Los puntos de {nombre}={etiqueta} exceden el universo de {nombre}"
                )

    def variables(self) -> tuple[str, ...]:
        """Devuelve las variables lingüísticas de entrada, en orden declarado."""
        return tuple(nombre for nombre in self._variables if nombre in self._antecedentes)

    def variables_salida(self) -> tuple[str, ...]:
        """Devuelve las variables lingüísticas de salida."""
        return tuple(nombre for nombre in self._variables if nombre in self._consecuentes)

    def etiquetas(self, variable: str) -> tuple[str, ...]:
        """Devuelve las etiquetas declaradas de una variable.

        Raises:
            ValueError: Si la variable no existe.
        """
        self._validar_variable_nombre(variable)
        return tuple(self._funciones[variable])

    def pertenencia(self, variable: str, etiqueta: str, valor: float) -> float:
        """Calcula el grado de pertenencia de un valor a una etiqueta.

        Args:
            variable: Variable lingüística declarada.
            etiqueta: Etiqueta de la variable.
            valor: Valor numérico (se recorta al universo declarado).

        Returns:
            Grado de pertenencia en ``[0, 1]``.

        Raises:
            ValueError: Si la variable o la etiqueta no existen.
            TypeError: Si el valor no es numérico.
        """
        self._validar_variable_nombre(variable)
        if etiqueta not in self._funciones[variable]:
            raise ValueError(f"Etiqueta desconocida en {variable}: {etiqueta}")
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise TypeError(f"El valor de {variable} debe ser numérico")
        return float(
            fuzz.interp_membership(
                self._universos[variable],
                self._funciones[variable][etiqueta],
                float(valor),
            )
        )

    def fuzzificar(self, valores: Mapping[str, float]) -> tuple[HechoDifuso, ...]:
        """Convierte hechos numéricos en hechos simbólicos con CF gradual.

        Los nombres de hecho se traducen con ``MAPEO_DIFUSO_HECHOS``; también se
        aceptan nombres de variables lingüísticas. Se conservan solo las
        etiquetas cuyo grado supera el umbral configurado.

        Args:
            valores: Mapping de nombre de hecho o variable a valor numérico.

        Returns:
            Hechos simbólicos ordenados por grado de pertenencia descendente.
        """
        if not isinstance(valores, Mapping):
            raise TypeError("Los valores a fuzzificar deben estar en un Mapping")
        hechos: list[HechoDifuso] = []
        for nombre, valor in valores.items():
            variable = self._mapeo.get(nombre, nombre)
            if variable not in self._antecedentes:
                LOGGER.debug("Ignorando hecho no difuso: %s", nombre)
                continue
            if isinstance(valor, bool) or not isinstance(valor, (int, float)):
                raise TypeError(f"El valor de {nombre} debe ser numérico")
            for etiqueta in self.etiquetas(variable):
                grado = self.pertenencia(variable, etiqueta, float(valor))
                if grado >= self._umbral:
                    hechos.append(HechoDifuso(variable, etiqueta, grado, variable, nombre))
        return tuple(sorted(hechos, key=lambda hecho: (-hecho.fc, hecho.atributo, hecho.valor)))

    def calcular(self, valores: Mapping[str, float]) -> ResultadoDifuso:
        """Ejecuta la inferencia Mamdani y defuzzifica las salidas por centroide.

        Args:
            valores: Mapping de hechos numéricos o variables lingüísticas.

        Returns:
            Resultado con centroides, etiquetas dominantes, grados, fuerzas de
            activación de reglas, hechos simbólicos de entrada y salida.

        Raises:
            TypeError: Si ``valores`` no es un Mapping o un valor no es numérico.
            ValueError: Si falta el mapeo de alguna variable de salida o no se
                puede defuzzificar.
        """
        if not isinstance(valores, Mapping):
            raise TypeError("Los valores de entrada deben estar en un Mapping")
        entradas = self._resolver_entradas(valores)
        hechos = self.fuzzificar(valores)

        simulacion = ctrl.ControlSystemSimulation(self._sistema)
        for variable, valor in entradas.items():
            simulacion.input[variable] = valor
        simulacion.compute()

        self._fuerzas = {regla.id: self._fuerza_regla(regla, entradas) for regla in self._reglas}
        salidas: dict[str, float] = {}
        etiquetas: dict[str, str] = {}
        grados: dict[str, dict[str, float]] = {}
        hechos_salida: list[HechoDifuso] = []
        reglas_activadas = (
            ", ".join(
                identificador for identificador, fuerza in self._fuerzas.items() if fuerza > 0.0
            )
            or "ninguna"
        )
        for variable in self.variables_salida():
            centroide = float(simulacion.output[variable])
            if not np.isfinite(centroide):
                raise ValueError(
                    f"No se pudo defuzzificar {variable}: ninguna regla produjo salida"
                )
            salidas[variable] = centroide
            miembros = {
                etiqueta: self.pertenencia(variable, etiqueta, centroide)
                for etiqueta in self.etiquetas(variable)
            }
            grados[variable] = miembros
            etiqueta_dominante = max(miembros, key=lambda etiqueta: miembros[etiqueta])
            etiquetas[variable] = etiqueta_dominante
            if variable not in MAPEO_SALIDAS_DIFUSAS:
                raise ValueError(f"Falta el mapeo del atributo de memoria para {variable}")
            grado = miembros[etiqueta_dominante]
            hechos_salida.append(
                HechoDifuso(
                    atributo=MAPEO_SALIDAS_DIFUSAS[variable],
                    valor=etiqueta_dominante,
                    fc=grado,
                    variable=variable,
                    origen="sistema_difuso",
                    detalle=(
                        f"centroide {centroide:.1f}; pertenencia {grado:.3f}; "
                        f"reglas activadas: {reglas_activadas}"
                    ),
                )
            )
        return ResultadoDifuso(
            entradas,
            salidas,
            etiquetas,
            grados,
            dict(self._fuerzas),
            hechos,
            tuple(hechos_salida),
        )

    def guardar_graficos(
        self,
        directorio: Path = DIR_FIGURAS_DIFUSAS,
    ) -> tuple[Path, ...]:
        """Guarda un PNG con las funciones de pertenencia de cada variable.

        Args:
            directorio: Carpeta destino, ``docs/figuras`` por defecto.

        Returns:
            Rutas de los archivos generados, en orden declarado.
        """
        destino = Path(directorio)
        destino.mkdir(parents=True, exist_ok=True)
        rutas: list[Path] = []
        for variable, universo in self._universos.items():
            figura = Figure(figsize=(8, 4))
            FigureCanvasAgg(figura)
            ejes = figura.add_subplot(111)
            for etiqueta, funcion in self._funciones[variable].items():
                ejes.plot(universo, funcion, linewidth=2, label=etiqueta)
            ejes.set_title(f"Funciones de pertenencia: {variable}")
            ejes.set_xlabel(variable)
            ejes.set_ylabel("Grado de pertenencia")
            ejes.set_ylim(0.0, 1.05)
            ejes.grid(alpha=0.3)
            ejes.legend(loc="upper right")
            figura.tight_layout()
            ruta = destino / f"pertenencia_{variable}.png"
            figura.savefig(ruta)
            rutas.append(ruta)
        LOGGER.info("Gráficos difusos guardados en %s", destino)
        return tuple(rutas)

    def _resolver_entradas(self, valores: Mapping[str, float]) -> dict[str, float]:
        """Traduce hechos a variables de entrada y completa las ausentes."""
        resueltos: dict[str, float] = {}
        for nombre, valor in valores.items():
            variable = self._mapeo.get(nombre, nombre)
            if variable not in self._antecedentes:
                continue
            if isinstance(valor, bool) or not isinstance(valor, (int, float)):
                raise TypeError(f"El valor de {nombre} debe ser numérico")
            resueltos[variable] = float(valor)
        for variable in self.variables():
            if variable not in resueltos:
                minimo, maximo, paso = self._variables[variable].universo
                neutro = round((minimo + maximo) / 2 / paso) * paso
                LOGGER.warning(
                    "Falta la entrada difusa %s; se usa el valor neutro %.2f", variable, neutro
                )
                resueltos[variable] = float(neutro)
        return resueltos

    def _fuerza_regla(self, regla: ReglaDifusa, entradas: Mapping[str, float]) -> float:
        """Calcula la fuerza de activación de una regla como mínimo de antecedentes."""
        return min(
            self.pertenencia(variable, etiqueta, entradas[variable])
            for variable, etiqueta in regla.si.items()
        )

    def _validar_variable_nombre(self, variable: str) -> None:
        """Comprueba que una variable exista en el sistema."""
        if variable not in self._funciones:
            raise ValueError(f"Variable difusa desconocida: {variable}")


def main() -> None:
    """Muestra un cálculo difuso, sus hechos simbólicos y guarda los gráficos."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s | %(message)s")
    sistema = SistemaDifuso()
    caso = {
        "cumplimiento_esperado_pct": 82.0,
        "stock_cobertura": 0.12,
        "merma_pct": 14.5,
        "afluencia_rel": 0.72,
        "descuento_pct": 0.0,
    }
    resultado = sistema.calcular(caso)
    print("=== Sistema difuso: caso Sucursal El Alto / pollo ===")
    print(f"Variables de entrada: {', '.join(sistema.variables())}")
    print(f"Reglas declaradas: {len(REGLAS_DIFUSAS)}")
    print(f"Salida: {resultado.descripcion()}")
    print(f"Reglas activadas: {', '.join(resultado.reglas_activadas)}")
    print("Hechos simbólicos:")
    for hecho in resultado.hechos:
        print(f"  - {hecho.descripcion}")
    rutas = sistema.guardar_graficos()
    print(f"Gráficos guardados en {rutas[0].parent} ({len(rutas)} archivos)")
    print(f"Riesgo para el motor: {ATRIBUTO_RIESGO_DIFUSO}; urgencia: {ATRIBUTO_URGENCIA}")


if __name__ == "__main__":
    main()
