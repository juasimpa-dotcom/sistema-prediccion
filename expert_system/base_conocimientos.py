"""Base de conocimientos declarativa del sistema experto.

Las reglas no están escritas como ``if`` sueltos: se describen en
``reglas.json`` o se entregan como lista de objetos :class:`Regla`. Ambas vías
pasan por la misma validación, de modo que una regla mal formada se detecta al
cargar la base y no durante una inferencia.

Estructura de una condición atómica en JSON:

.. code-block:: json

    {"atributo": "stock_cobertura", "operador": "menor_que", "valor": 0.35}

Las condiciones atómicas se agrupan con ``{"operador": "and" | "or",
"condiciones": [...]}`` y los grupos pueden anidarse. Los operadores disponibles
son ``igual``, ``distinto``, ``mayor_que``, ``menor_que``, ``mayor_o_igual``,
``menor_o_igual``, ``en``, ``no_en``, ``verdadero`` y ``falso``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Hashable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from config import ARCHIVO_REGLAS_EXPERTO, VERSION_BASE_CONOCIMIENTOS
from expert_system.factores_certeza import validar_fc

LOGGER = logging.getLogger(__name__)

OPERADORES_ATOMICOS: frozenset[str] = frozenset(
    {
        "igual",
        "distinto",
        "mayor_que",
        "menor_que",
        "mayor_o_igual",
        "menor_o_igual",
        "en",
        "no_en",
        "verdadero",
        "falso",
    }
)
OPERADORES_NUMERICOS: frozenset[str] = frozenset(
    {"mayor_que", "menor_que", "mayor_o_igual", "menor_o_igual"}
)
OPERADORES_GRUPO: frozenset[str] = frozenset({"and", "or"})
CLAVES_REGLA: frozenset[str] = frozenset(
    {"id", "descripcion", "categoria", "prioridad", "fc", "condiciones", "conclusion"}
)
CLAVES_CONCLUSION: frozenset[str] = frozenset({"atributo", "valor"})
CLAVES_ATOMO: frozenset[str] = frozenset({"atributo", "operador", "valor"})
CLAVES_GRUPO: frozenset[str] = frozenset({"operador", "condiciones"})

_SIN_VALOR = object()


def _texto(valor: object) -> str:
    """Formatea un valor para las descripciones legibles."""
    if isinstance(valor, bool):
        return "sí" if valor else "no"
    if isinstance(valor, (list, tuple)):
        return "[" + ", ".join(_texto(item) for item in valor) + "]"
    return str(valor)


@dataclass(frozen=True, slots=True)
class Condicion:
    """Condición atómica sobre un hecho de la memoria de trabajo.

    Attributes:
        atributo: Variable a evaluar.
        operador: Comparador declarativo.
        valor: Valor o umbral contra el que se compara.
    """

    atributo: str
    operador: str
    valor: Hashable

    def __post_init__(self) -> None:
        """Valida la condición y el tipo de su valor."""
        if not isinstance(self.atributo, str) or not self.atributo.strip():
            raise ValueError("La condición necesita un atributo no vacío")
        if self.operador not in OPERADORES_ATOMICOS:
            raise ValueError(
                f"Operador desconocido '{self.operador}'; use uno de {sorted(OPERADORES_ATOMICOS)}"
            )
        if not isinstance(self.valor, Hashable):
            raise TypeError("El valor de la condición debe ser hashable")
        if self.operador in OPERADORES_NUMERICOS and (
            isinstance(self.valor, bool) or not isinstance(self.valor, (int, float))
        ):
            raise TypeError(f"El operador '{self.operador}' requiere un valor numérico")
        if self.operador in {"en", "no_en"} and not isinstance(self.valor, (list, tuple)):
            raise TypeError(f"El operador '{self.operador}' requiere una lista de valores")
        if self.operador in {"en", "no_en"} and not self.valor:
            raise ValueError(f"El operador '{self.operador}' requiere una lista no vacía")
        if self.operador in {"verdadero", "falso"} and not isinstance(self.valor, bool):
            raise TypeError(f"El operador '{self.operador}' requiere un valor booleano")

    @property
    def texto(self) -> str:
        """Devuelve la condición en lenguaje natural."""
        nombre = {
            "igual": "es",
            "distinto": "no es",
            "mayor_que": ">",
            "menor_que": "<",
            "mayor_o_igual": ">=",
            "menor_o_igual": "<=",
            "en": "está en",
            "no_en": "no está en",
            "verdadero": "es",
            "falso": "es",
        }[self.operador]
        return f"{self.atributo} {nombre} {_texto(self.valor)}"


@dataclass(frozen=True, slots=True)
class GrupoCondiciones:
    """Conjunción o disyunción recursiva de condiciones.

    Attributes:
        operador: ``and`` o ``or``.
        condiciones: Condiciones atómicas o grupos anidados.
    """

    operador: Literal["and", "or"]
    condiciones: tuple[Condicion | GrupoCondiciones, ...]

    def __post_init__(self) -> None:
        """Valida el operador y comprueba que el grupo no esté vacío."""
        if self.operador not in OPERADORES_GRUPO:
            raise ValueError(f"El operador de grupo debe ser 'and' u 'or', no '{self.operador}'")
        if not self.condiciones:
            raise ValueError("Un grupo de condiciones no puede estar vacío")
        for condicion in self.condiciones:
            if not isinstance(condicion, (Condicion, GrupoCondiciones)):
                raise TypeError("Las condiciones deben ser Condicion o GrupoCondiciones")

    @property
    def especificidad(self) -> int:
        """Cuenta las condiciones atómicas, incluidas las de grupos anidados."""
        return sum(
            1 if isinstance(condicion, Condicion) else condicion.especificidad
            for condicion in self.condiciones
        )

    @property
    def texto(self) -> str:
        """Devuelve el grupo en lenguaje natural con paréntesis."""
        separador = " Y " if self.operador == "and" else " O "
        return "(" + separador.join(condicion.texto for condicion in self.condiciones) + ")"


@dataclass(frozen=True, slots=True)
class Consecuente:
    """Conclusión que una regla aporta a la memoria de trabajo.

    Attributes:
        atributo: Variable concluida.
        valor: Valor concluido.
    """

    atributo: str
    valor: Hashable

    def __post_init__(self) -> None:
        """Valida el consecuente."""
        if not isinstance(self.atributo, str) or not self.atributo.strip():
            raise ValueError("La conclusión necesita un atributo no vacío")
        if not isinstance(self.valor, Hashable):
            raise TypeError("El valor de la conclusión debe ser hashable")

    @property
    def texto(self) -> str:
        """Devuelve la conclusión en lenguaje natural."""
        return f"{self.atributo}={_texto(self.valor)}"


@dataclass(frozen=True, slots=True)
class Regla:
    """Regla de producción con factor de certeza.

    Attributes:
        id: Identificador único.
        descripcion: Explicación legible de la regla.
        condiciones: Premisa agrupada en ``and``/``or``.
        conclusion: Hecho que se deriva al dispararse.
        fc: Factor de certeza de la regla en ``[-1, 1]`` y distinto de cero.
        prioridad: Entero no negativo para la resolución de conflictos.
        categoria: Grupo al que pertenece (diagnóstico, riesgo, recomendación...).
    """

    id: str
    descripcion: str
    condiciones: GrupoCondiciones
    conclusion: Consecuente
    fc: float
    prioridad: int
    categoria: str

    def __post_init__(self) -> None:
        """Valida todos los campos de la regla."""
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("La regla necesita un identificador no vacío")
        if not isinstance(self.descripcion, str) or not self.descripcion.strip():
            raise ValueError(f"La regla {self.id} necesita una descripción")
        if not isinstance(self.condiciones, GrupoCondiciones):
            raise TypeError(f"Las condiciones de la regla {self.id} deben ser un grupo")
        if not isinstance(self.conclusion, Consecuente):
            raise TypeError(f"La conclusión de la regla {self.id} debe ser un consecuente")
        fc = validar_fc(self.fc, f"FC de la regla {self.id}")
        if fc == 0.0:
            raise ValueError(f"La regla {self.id} no puede tener FC cero")
        object.__setattr__(self, "fc", fc)
        if isinstance(self.prioridad, bool) or not isinstance(self.prioridad, int):
            raise TypeError(f"La prioridad de la regla {self.id} debe ser un entero")
        if self.prioridad < 0:
            raise ValueError(f"La prioridad de la regla {self.id} no puede ser negativa")
        if not isinstance(self.categoria, str) or not self.categoria.strip():
            raise ValueError(f"La regla {self.id} necesita una categoría")

    @property
    def especificidad(self) -> int:
        """Número de condiciones atómicas de la premisa."""
        return self.condiciones.especificidad

    @property
    def texto(self) -> str:
        """Devuelve la regla completa en lenguaje natural."""
        return f"SI {self.condiciones.texto} ENTONCES {self.conclusion.texto} (FC {self.fc:+.2f})"


class BaseConocimientos:
    """Colección validada e inmutable de reglas de producción.

    El motor solo depende de esta interfaz, por lo que puede cambiar de base
    sin modificar una sola línea de su código.
    """

    def __init__(self, reglas: Iterable[Regla], version: str = VERSION_BASE_CONOCIMIENTOS) -> None:
        """Construye la base y comprueba que no haya identificadores repetidos.

        Args:
            reglas: Reglas ya validadas.
            version: Versión declarativa de la base.

        Raises:
            ValueError: Si no hay reglas o los identificadores se repiten.
        """
        self.reglas: tuple[Regla, ...] = tuple(reglas)
        if not self.reglas:
            raise ValueError("La base de conocimientos necesita al menos una regla")
        vistos: set[str] = set()
        for regla in self.reglas:
            if not isinstance(regla, Regla):
                raise TypeError("Todos los elementos de la base deben ser Regla")
            if regla.id in vistos:
                raise ValueError(f"Identificador de regla repetido: {regla.id}")
            vistos.add(regla.id)
        if not isinstance(version, str) or not version.strip():
            raise ValueError("La versión de la base no puede estar vacía")
        self.version = version
        LOGGER.info("Base de conocimientos %s cargada con %d reglas", version, len(self.reglas))

    @classmethod
    def desde_objetos(
        cls,
        reglas: Iterable[Regla],
        version: str = VERSION_BASE_CONOCIMIENTOS,
    ) -> BaseConocimientos:
        """Crea una base a partir de una lista de objetos :class:`Regla`.

        Args:
            reglas: Reglas ya instanciadas.
            version: Versión de la base.

        Returns:
            Base validada.
        """
        return cls(reglas, version)

    @classmethod
    def desde_dict(cls, datos: Mapping[str, object]) -> BaseConocimientos:
        """Crea una base a partir de una estructura JSON ya decodificada.

        Args:
            datos: Mapping con claves ``version`` y ``reglas``.

        Returns:
            Base validada.

        Raises:
            ValueError: Si falta información o una regla está mal formada.
        """
        if not isinstance(datos, Mapping):
            raise ValueError("La base debe ser un objeto JSON")
        permitidas = {"version", "reglas"}
        if desconocidas := set(datos) - permitidas:
            raise ValueError(f"Claves desconocidas en la base: {sorted(desconocidas)}")
        if "reglas" not in datos or not isinstance(datos["reglas"], list):
            raise ValueError("La base debe contener una lista 'reglas'")
        version = datos.get("version", VERSION_BASE_CONOCIMIENTOS)
        if not isinstance(version, str):
            raise ValueError("La versión de la base debe ser texto")
        reglas = [
            cls._parsear_regla(regla, indice)
            for indice, regla in enumerate(datos["reglas"], start=1)
        ]
        return cls(reglas, version)

    @classmethod
    def desde_json(cls, ruta: Path | str = ARCHIVO_REGLAS_EXPERTO) -> BaseConocimientos:
        """Carga y valida la base desde un archivo JSON.

        Args:
            ruta: Ruta del archivo.

        Returns:
            Base validada.

        Raises:
            FileNotFoundError: Si el archivo no existe.
            ValueError: Si el JSON es inválido o las reglas fallan la validación.
        """
        archivo = Path(ruta)
        if not archivo.is_file():
            raise FileNotFoundError(f"No existe la base de conocimientos: {archivo}")
        try:
            datos = json.loads(archivo.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"JSON inválido en {archivo}: {error}") from error
        return cls.desde_dict(datos)

    def por_categoria(self, categoria: str) -> tuple[Regla, ...]:
        """Devuelve las reglas de una categoría."""
        return tuple(regla for regla in self.reglas if regla.categoria == categoria)

    def por_id(self, identificador: str) -> Regla:
        """Devuelve una regla por su identificador.

        Raises:
            KeyError: Si no existe.
        """
        for regla in self.reglas:
            if regla.id == identificador:
                return regla
        raise KeyError(f"Regla desconocida: {identificador}")

    def para_conclusion(self, atributo: str, valor: object = _SIN_VALOR) -> tuple[Regla, ...]:
        """Devuelve las reglas que concluyen una hipótesis, ordenadas por prioridad."""
        encontradas = [
            regla
            for regla in self.reglas
            if regla.conclusion.atributo == atributo
            and (valor is _SIN_VALOR or regla.conclusion.valor == valor)
        ]
        return tuple(
            sorted(
                encontradas, key=lambda regla: (-regla.prioridad, -regla.especificidad, regla.id)
            )
        )

    def categorias(self) -> tuple[str, ...]:
        """Devuelve las categorías presentes, sin repetir y en orden de aparición."""
        return tuple(dict.fromkeys(regla.categoria for regla in self.reglas))

    @staticmethod
    def _parsear_regla(datos: object, indice: int) -> Regla:
        """Convierte un objeto JSON en una :class:`Regla` validada."""
        if not isinstance(datos, Mapping):
            raise ValueError(f"La regla {indice} debe ser un objeto JSON")
        faltan = CLAVES_REGLA - set(datos)
        if faltan:
            raise ValueError(f"La regla {indice} falta campos: {sorted(faltan)}")
        if desconocidas := set(datos) - CLAVES_REGLA:
            raise ValueError(f"La regla {indice} tiene campos desconocidos: {sorted(desconocidas)}")

        identificador = datos["id"]
        if not isinstance(identificador, str) or not identificador.strip():
            raise ValueError(f"La regla {indice} necesita un id no vacío")
        try:
            conclusion = BaseConocimientos._parsear_conclusion(datos["conclusion"], identificador)
            condiciones = BaseConocimientos._parsear_condiciones(
                datos["condiciones"], identificador
            )
            if isinstance(condiciones, Condicion):
                condiciones = GrupoCondiciones(operador="and", condiciones=(condiciones,))
            return Regla(
                id=identificador,
                descripcion=BaseConocimientos._texto_obligatorio(
                    datos["descripcion"], "descripcion", identificador
                ),
                condiciones=condiciones,
                conclusion=conclusion,
                fc=BaseConocimientos._numero(datos["fc"], "fc", identificador),
                prioridad=BaseConocimientos._entero(datos["prioridad"], "prioridad", identificador),
                categoria=BaseConocimientos._texto_obligatorio(
                    datos["categoria"], "categoria", identificador
                ),
            )
        except (TypeError, ValueError) as error:
            raise ValueError(f"Regla {identificador} inválida: {error}") from error

    @staticmethod
    def _parsear_conclusion(datos: object, identificador: str) -> Consecuente:
        """Convierte la conclusión de una regla."""
        if not isinstance(datos, Mapping) or set(datos) != CLAVES_CONCLUSION:
            raise ValueError("'conclusion' debe contener exactamente 'atributo' y 'valor'")
        return Consecuente(
            atributo=BaseConocimientos._texto_obligatorio(
                datos["atributo"], "conclusion.atributo", identificador
            ),
            valor=datos["valor"],
        )

    @staticmethod
    def _parsear_condiciones(
        datos: object,
        identificador: str,
    ) -> Condicion | GrupoCondiciones:
        """Convierte una condición o grupo, permitiendo anidamiento."""
        if not isinstance(datos, Mapping):
            raise ValueError("cada condición debe ser un objeto JSON")
        if set(datos) >= CLAVES_GRUPO:
            if set(datos) != CLAVES_GRUPO:
                raise ValueError("un grupo solo admite 'operador' y 'condiciones'")
            operador = datos["operador"]
            if operador not in OPERADORES_GRUPO:
                raise ValueError(f"operador de grupo desconocido: {operador}")
            hijos = datos["condiciones"]
            if not isinstance(hijos, list) or not hijos:
                raise ValueError("'condiciones' debe ser una lista no vacía")
            return GrupoCondiciones(
                operador=operador,
                condiciones=tuple(
                    BaseConocimientos._parsear_condiciones(hijo, identificador) for hijo in hijos
                ),
            )
        if set(datos) == CLAVES_ATOMO:
            return Condicion(
                atributo=BaseConocimientos._texto_obligatorio(
                    datos["atributo"], "condicion.atributo", identificador
                ),
                operador=BaseConocimientos._texto_obligatorio(
                    datos["operador"], "condicion.operador", identificador
                ),
                valor=BaseConocimientos._valor_condicion(datos["operador"], datos["valor"]),
            )
        raise ValueError(
            "una condición necesita 'atributo', 'operador' y 'valor', "
            "o 'operador' y 'condiciones'"
        )

    @staticmethod
    def _valor_condicion(operador: object, valor: object) -> object:
        """Normaliza los valores declarados en las condiciones."""
        if operador in {"en", "no_en"}:
            if not isinstance(valor, list):
                raise TypeError("'en' y 'no_en' requieren una lista")
            return tuple(valor)
        return valor

    @staticmethod
    def _texto_obligatorio(valor: object, campo: str, identificador: str) -> str:
        """Valida un campo de texto obligatorio."""
        if not isinstance(valor, str) or not valor.strip():
            raise ValueError(f"{campo} de la regla {identificador} debe ser texto no vacío")
        return valor

    @staticmethod
    def _numero(valor: object, campo: str, identificador: str) -> float:
        """Valida un campo numérico."""
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise TypeError(f"{campo} de la regla {identificador} debe ser numérico")
        return float(valor)

    @staticmethod
    def _entero(valor: object, campo: str, identificador: str) -> int:
        """Valida un campo entero."""
        if isinstance(valor, bool) or not isinstance(valor, int):
            raise TypeError(f"{campo} de la regla {identificador} debe ser un entero")
        return valor
