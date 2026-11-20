"""Motor de inferencia genérico con factores de certeza estilo MYCIN.

No contiene ningún concepto de retail: solo sabe evaluar reglas de una
:class:`~expert_system.base_conocimientos.BaseConocimientos` contra una
:class:`~expert_system.memoria_trabajo.MemoriaTrabajo`.

Fórmulas aplicadas (implementadas en :mod:`expert_system.factores_certeza`):

* Condiciones conjuntas (``and``): ``CF = min(CF_i)``.
* Condiciones disyuntivas (``or``): ``CF = max(CF_i)``.
* Propagación de una regla: ``CF_conclusión = CF_regla × CF_premisa``.
* Evidencia de varias reglas sobre la misma conclusión:

  .. code-block:: text

      ambos positivos:  CF = CF1 + CF2 · (1 - CF1)
      ambos negativos:  CF = CF1 + CF2 · (1 + CF1)
      signos opuestos:  CF = (CF1 + CF2) / (1 - min(|CF1|, |CF2|))

Una condición que coincide con el hecho aporta ``+FC``; una condición que lo
contradice aporta ``-FC``. Una regla solo se dispara si la certeza **positiva**
de su premisa alcanza ``umbral`` (0.2 por defecto), de modo que la contradicción
se registra como evidencia en contra sin provocar conclusiones espurias.

La resolución de conflictos elige, en cada iteración, una sola regla entre las
disparables y la ordena por ``prioridad`` descendente,``especificidad``
descendente e ``id`` ascendente (desempate determinista). Eso equivale a
"reglas más específicas y prioritarias primero".
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Hashable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from config import UMBRAL_CF_EXPERTO
from expert_system.base_conocimientos import BaseConocimientos, Condicion, GrupoCondiciones, Regla
from expert_system.factores_certeza import (
    cf_conjuncion,
    cf_disjuncion,
    combinar_fc,
    propagar_fc,
    supera_umbral,
    validar_fc,
)
from expert_system.logica_difusa import Fuzzificador, HechoDifuso, ResultadoDifuso
from expert_system.memoria_trabajo import Hecho, MemoriaTrabajo

LOGGER = logging.getLogger(__name__)

# El proveedor devuelve None si no sabe, un valor concreto, o (valor, FC).
Proveedor = Callable[[str, object], object | None]


def _ahora() -> str:
    """Devuelve la hora actual en ISO 8601 y UTC."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def _texto(valor: object) -> str:
    """Formatea un valor para las trazas."""
    if isinstance(valor, bool):
        return "sí" if valor else "no"
    if isinstance(valor, (list, tuple)):
        return "[" + ", ".join(_texto(item) for item in valor) + "]"
    return str(valor)


@dataclass(frozen=True, slots=True)
class PasoInferencia:
    """Registro de una regla disparada durante una inferencia.

    Attributes:
        orden: Posición del paso dentro de la traza.
        regla_id: Identificador de la regla.
        descripcion: Descripción declarativa de la regla.
        categoria: Categoría de la regla.
        premisa: Texto de las condiciones evaluadas.
        cf_premisa: Certeza de la premisa antes de propagar.
        fc_regla: Certeza declarada de la regla.
        cf_conclusion: Certeza de la conclusión derivada.
        conclusion_atributo: Variable concluida.
        conclusion_valor: Valor concluido.
        momento: Instante ISO 8601 del disparo.
    """

    orden: int
    regla_id: str
    descripcion: str
    categoria: str
    premisa: str
    cf_premisa: float
    fc_regla: float
    cf_conclusion: float
    conclusion_atributo: str
    conclusion_valor: Hashable
    momento: str

    @property
    def conclusion(self) -> str:
        """Devuelve la conclusión en texto legible."""
        return f"{self.conclusion_atributo}={_texto(self.conclusion_valor)}"


@dataclass(frozen=True, slots=True)
class Pregunta:
    """Dato solicitado al proveedor durante el encadenamiento hacia atrás.

    Attributes:
        atributo: Variable preguntada.
        valor_esperado: Valor o umbral que se intentaba confirmar.
        regla_id: Regla que motivó la pregunta.
        objetivo: Hipótesis general que se está verificando.
        momento: Instante ISO 8601 de la pregunta.
    """

    atributo: str
    valor_esperado: object
    regla_id: str
    objetivo: str
    momento: str


@dataclass(slots=True)
class TrazaInferencia:
    """Traza cronológica de una inferencia.

    Attributes:
        modo: ``adelante`` o ``atras``.
        objetivo: Hipótesis perseguida en encadenamiento hacia atrás.
        pasos: Reglas disparadas, en orden.
        preguntas: Datos solicitados al proveedor.
        reglas_disparadas: Identificadores ya utilizados, para evitar ciclos.
        inicio: Instante ISO 8601 de inicio.
    """

    modo: str
    objetivo: str = ""
    pasos: list[PasoInferencia] = field(default_factory=list)
    preguntas: list[Pregunta] = field(default_factory=list)
    reglas_disparadas: set[str] = field(default_factory=set)
    inicio: str = field(default_factory=_ahora)

    def registrar_disparo(self, paso: PasoInferencia) -> None:
        """Agrega un paso a la traza y marca la regla como usada."""
        self.pasos.append(paso)
        self.reglas_disparadas.add(paso.regla_id)

    def registrar_pregunta(self, pregunta: Pregunta) -> None:
        """Agrega una pregunta a la traza."""
        self.preguntas.append(pregunta)

    def reglas_usadas(self) -> tuple[str, ...]:
        """Devuelve los identificadores de reglas disparadas, en orden."""
        return tuple(paso.regla_id for paso in self.pasos)

    def __len__(self) -> int:
        """Devuelve la cantidad de reglas disparadas."""
        return len(self.pasos)


@dataclass(frozen=True, slots=True)
class ResultadoObjetivo:
    """Resultado de verificar una hipótesis.

    Attributes:
        atributo: Variable verificada.
        valor: Valor de la hipótesis.
        fc: Certeza final combinada.
        cumplido: Si la certeza supera el umbral.
        traza: Traza de la inferencia que condujo al resultado.
    """

    atributo: str
    valor: object
    fc: float
    cumplido: bool
    traza: TrazaInferencia

    def __bool__(self) -> bool:
        """Permite usar el resultado en condiciones ``if``."""
        return self.cumplido

    @property
    def descripcion(self) -> str:
        """Devuelve el resultado en texto legible."""
        return f"{self.atributo}={_texto(self.valor)} (FC {self.fc:+.2f})"


class MotorInferencia:
    """Motor independiente del dominio, configurable con cualquier base de reglas."""

    def __init__(
        self,
        base: BaseConocimientos,
        memoria: MemoriaTrabajo | None = None,
        umbral: float = UMBRAL_CF_EXPERTO,
        proveedor: Proveedor | None = None,
        fuzzificador: Fuzzificador | None = None,
    ) -> None:
        """Inicializa el motor.

        Args:
            base: Base de conocimientos validada.
            memoria: Memoria de trabajo; se crea una vacía si se omite.
            umbral: Certeza mínima positiva para disparar una regla.
            proveedor: Función que responde datos desconocidos durante el
                encadenamiento hacia atrás. Devuelve ``None`` si no sabe, un
                valor concreto, o ``(valor, FC)`` para certezas parciales.
            fuzzificador: Implementación opcional de :class:`Fuzzificador`. El
                motor solo usa su interfaz: desconoce scikit-fuzzy y el dominio.

        Raises:
            TypeError: Si la base, la memoria o el proveedor tienen tipo inválido.
            ValueError: Si el umbral está fuera de ``[0, 1]``.
        """
        if not isinstance(base, BaseConocimientos):
            raise TypeError("El motor requiere una BaseConocimientos")
        if memoria is not None and not isinstance(memoria, MemoriaTrabajo):
            raise TypeError("La memoria debe ser una MemoriaTrabajo")
        if proveedor is not None and not callable(proveedor):
            raise TypeError("El proveedor debe ser invocable")
        if fuzzificador is not None and not isinstance(fuzzificador, Fuzzificador):
            raise TypeError("El fuzzificador debe implementar el protocolo Fuzzificador")
        validar_fc(umbral, "umbral")
        if umbral < 0.0:
            raise ValueError("El umbral no puede ser negativo")
        self.base = base
        self.memoria = memoria if memoria is not None else MemoriaTrabajo()
        self.umbral = umbral
        self.proveedor = proveedor
        self.fuzzificador = fuzzificador
        self.ultimo_resultado_difuso: ResultadoDifuso | None = None
        self._difuso_aplicado = False
        self._hechos_fuzzificados: set[tuple[str, Hashable]] = set()

    def fuzzificar(self, memoria: MemoriaTrabajo | None = None) -> tuple[HechoDifuso, ...]:
        """Convierte los hechos numéricos de la memoria en hechos simbólicos.

        El factor de certeza de cada hecho simbólico es el grado de pertenencia
        calculado por el fuzzificador. Los hechos ya registrados no se vuelven a
        insertar para no inflar su certeza al combinar evidencia duplicada.

        Args:
            memoria: Memoria a usar; por defecto la del motor.

        Returns:
            Hechos simbólicos recién registrados. Sin fuzzificador, tupla vacía.
        """
        if self.fuzzificador is None:
            return ()
        destino = memoria if memoria is not None else self.memoria
        if not isinstance(destino, MemoriaTrabajo):
            raise TypeError("La memoria debe ser una MemoriaTrabajo")
        generados = self.fuzzificador.fuzzificar(self._hechos_numericos(destino))
        nuevos: list[HechoDifuso] = []
        for hecho in generados:
            clave = (hecho.atributo, hecho.valor)
            if clave in self._hechos_fuzzificados:
                continue
            destino.registrar(
                Hecho(
                    atributo=hecho.atributo,
                    valor=hecho.valor,
                    fc=hecho.fc,
                    origen=hecho.origen,
                    detalle=(
                        f"grado de pertenencia {hecho.fc:.3f} desde "
                        f"{hecho.hecho_origen or hecho.variable}"
                    ),
                )
            )
            self._hechos_fuzzificados.add(clave)
            nuevos.append(hecho)
        return tuple(nuevos)

    def aplicar_difuso(self, memoria: MemoriaTrabajo | None = None) -> ResultadoDifuso | None:
        """Calcula las salidas difusas y las inyecta como hechos simbólicos.

        El fuzzificador entrega los hechos de salida ya traducidos a atributos
        de la memoria, con su factor de certeza y su trazabilidad. El motor los
        registra sin conocer variables difusas, centroides ni nombres de dominio.
        Solo se aplica una vez por memoria.

        Args:
            memoria: Memoria a usar; por defecto la del motor.

        Returns:
            Resultado difuso, o ``None`` si no hay fuzzificador o ya se aplicó.
        """
        destino = memoria if memoria is not None else self.memoria
        if not isinstance(destino, MemoriaTrabajo):
            raise TypeError("La memoria debe ser una MemoriaTrabajo")
        if self.fuzzificador is None or self._difuso_aplicado:
            return self.ultimo_resultado_difuso
        resultado = self.fuzzificador.calcular(self._hechos_numericos(destino))
        for salida in resultado.hechos_salida:
            if destino.contiene(salida.atributo, salida.valor):
                continue
            destino.registrar(
                Hecho(
                    atributo=salida.atributo,
                    valor=salida.valor,
                    fc=salida.fc,
                    origen=salida.origen,
                    detalle=salida.detalle,
                )
            )
        self.ultimo_resultado_difuso = resultado
        self._difuso_aplicado = True
        LOGGER.info("Salida difusa inyectada en la memoria: %s", resultado.descripcion())
        return resultado

    def _preparar_difuso(self, memoria: MemoriaTrabajo) -> None:
        """Fuzzifica entradas y aplica salidas difusas una sola vez."""
        if self.fuzzificador is None or self._difuso_aplicado:
            return
        self.fuzzificar(memoria)
        self.aplicar_difuso(memoria)

    @staticmethod
    def _hechos_numericos(memoria: MemoriaTrabajo) -> dict[str, float]:
        """Extrae los hechos numéricos vigentes de la memoria de trabajo."""
        valores: dict[str, float] = {}
        for hecho in memoria.historial():
            if isinstance(hecho.valor, (int, float)) and not isinstance(hecho.valor, bool):
                valores[hecho.atributo] = float(hecho.valor)
        return valores

    def encadenar_adelante(self, memoria: MemoriaTrabajo | None = None) -> TrazaInferencia:
        """Deriva todas las conclusiones alcanzables a partir de los hechos conocidos.

        Args:
            memoria: Memoria a usar; por defecto la del motor.

        Returns:
            Traza con el orden exacto de disparo de las reglas.
        """
        destino = memoria if memoria is not None else self.memoria
        if not isinstance(destino, MemoriaTrabajo):
            raise TypeError("La memoria debe ser una MemoriaTrabajo")
        self._preparar_difuso(destino)
        traza = TrazaInferencia(modo="adelante", objetivo="todas las conclusiones")
        while True:
            disparables: list[tuple[Regla, float]] = []
            for regla in self.base.reglas:
                if regla.id in traza.reglas_disparadas:
                    continue
                cf = self.evaluar_condiciones(regla.condiciones, memoria=destino)
                if supera_umbral(cf, self.umbral):
                    disparables.append((regla, cf))
            if not disparables:
                break
            disparables.sort(
                key=lambda item: (-item[0].prioridad, -item[0].especificidad, item[0].id)
            )
            regla, cf_premisa = disparables[0]
            self._disparar(regla, cf_premisa, destino, traza)
        LOGGER.info("Encadenamiento hacia adelante: %d reglas disparadas", len(traza))
        return traza

    def verificar(
        self,
        objetivo: str,
        valor: object = True,
        memoria: MemoriaTrabajo | None = None,
        traza: TrazaInferencia | None = None,
        visitados: set[tuple[str, Hashable]] | None = None,
    ) -> ResultadoObjetivo:
        """Verifica una hipótesis mediante encadenamiento hacia atrás.

        Primero consulta la memoria; después intenta demostrarla con reglas cuyo
        consecuente coincida, resolviendo subobjetivos simbólicos de forma
        recursiva; por último pregunta al proveedor por los datos numéricos que
        falten. Los resultados de varias reglas se combinan con MYCIN.

        Args:
            objetivo: Atributo de la hipótesis.
            valor: Valor de la hipótesis.
            memoria: Memoria a usar; por defecto la del motor.
            traza: Traza compartida en llamadas recursivas.
            visitados: Objetivos ya visitados, para cortar ciclos.

        Returns:
            Resultado con la certeza final y la traza completa.
        """
        destino = memoria if memoria is not None else self.memoria
        if not isinstance(destino, MemoriaTrabajo):
            raise TypeError("La memoria debe ser una MemoriaTrabajo")
        if traza is None:
            self._preparar_difuso(destino)
            traza = TrazaInferencia(modo="atras", objetivo=f"{objetivo}={_texto(valor)}")
        if visitados is None:
            visitados = set()
        if not isinstance(valor, Hashable):
            raise TypeError("El valor de la hipótesis debe ser hashable")

        clave = (objetivo, valor)
        hecho = destino.consultar(objetivo, valor)
        if hecho is not None and abs(hecho.fc) >= self.umbral:
            return ResultadoObjetivo(objetivo, valor, hecho.fc, hecho.fc >= self.umbral, traza)
        if clave in visitados:
            return ResultadoObjetivo(objetivo, valor, 0.0, False, traza)
        visitados.add(clave)

        evidencias: list[float] = []
        for regla in self.base.para_conclusion(objetivo, valor):
            if regla.id in traza.reglas_disparadas:
                continue
            cf_premisa = self.evaluar_condiciones(
                regla.condiciones,
                memoria=destino,
                objetivo=traza.objetivo,
                traza=traza,
                regla_id=regla.id,
                visitados=visitados,
            )
            if supera_umbral(cf_premisa, self.umbral):
                evidencias.append(self._disparar(regla, cf_premisa, destino, traza))

        previo = hecho.fc if hecho is not None else 0.0
        fc = combinar_fc(previo, *evidencias) if (previo or evidencias) else 0.0
        return ResultadoObjetivo(objetivo, valor, fc, supera_umbral(fc, self.umbral), traza)

    def evaluar_condiciones(
        self,
        condiciones: GrupoCondiciones,
        memoria: MemoriaTrabajo | None = None,
        objetivo: str = "",
        traza: TrazaInferencia | None = None,
        regla_id: str = "",
        visitados: set[tuple[str, Hashable]] | None = None,
    ) -> float:
        """Evalúa un grupo de condiciones aplicando ``min`` o ``max``.

        Args:
            condiciones: Grupo declarativo en ``and`` o ``or``.
            memoria: Memoria a consultar.
            objetivo: Hipótesis perseguida, para contextualizar preguntas.
            traza: Traza donde registrar preguntas.
            regla_id: Regla que evalúa el grupo.
            visitados: Objetivos visitados en encadenamiento hacia atrás.

        Returns:
            Factor de certeza de la premisa.

        Raises:
            TypeError: Si el grupo no es un :class:`GrupoCondiciones`.
        """
        if not isinstance(condiciones, GrupoCondiciones):
            raise TypeError("Las condiciones deben ser un GrupoCondiciones")
        destino = memoria if memoria is not None else self.memoria
        cfs: list[float] = []
        for condicion in condiciones.condiciones:
            if isinstance(condicion, Condicion):
                cfs.append(
                    self._evaluar_condicion(
                        condicion, destino, objetivo, traza, regla_id, visitados
                    )
                )
            else:
                cfs.append(
                    self.evaluar_condiciones(
                        condicion, destino, objetivo, traza, regla_id, visitados
                    )
                )
        return cf_conjuncion(cfs) if condiciones.operador == "and" else cf_disjuncion(cfs)

    def _evaluar_condicion(
        self,
        condicion: Condicion,
        memoria: MemoriaTrabajo,
        objetivo: str,
        traza: TrazaInferencia | None,
        regla_id: str,
        visitados: set[tuple[str, Hashable]] | None,
    ) -> float:
        """Evalúa una condición atómica contra la memoria o el proveedor."""
        hecho = memoria.consultar(condicion.atributo)
        if hecho is None and traza is not None and visitados is not None:
            hecho = self._demostrar_subobjetivo(condicion, memoria, traza, visitados)
        if hecho is None and traza is not None and self.proveedor is not None:
            self._preguntar(condicion, traza, regla_id, objetivo, memoria)
            hecho = memoria.consultar(condicion.atributo)
        if hecho is None:
            return 0.0
        coincide = self._comparar(hecho.valor, condicion.operador, condicion.valor)
        return hecho.fc if coincide else -hecho.fc

    def _demostrar_subobjetivo(
        self,
        condicion: Condicion,
        memoria: MemoriaTrabajo,
        traza: TrazaInferencia,
        visitados: set[tuple[str, Hashable]],
    ) -> Hecho | None:
        """Intenta probar una condición simbólica con las reglas de la base."""
        if condicion.operador == "en":
            mejores = [
                self.verificar(condicion.atributo, opcion, memoria, traza, visitados)
                for opcion in condicion.valor
            ]
            ganador = max(mejores, key=lambda resultado: resultado.fc, default=None)
            if ganador is not None and supera_umbral(ganador.fc, self.umbral):
                return memoria.consultar(condicion.atributo, ganador.valor)
            return None
        if condicion.operador in {"igual", "verdadero", "falso"}:
            resultado = self.verificar(
                condicion.atributo, condicion.valor, memoria, traza, visitados
            )
            if supera_umbral(resultado.fc, self.umbral):
                return memoria.consultar(condicion.atributo, condicion.valor)
        return None

    def _preguntar(
        self,
        condicion: Condicion,
        traza: TrazaInferencia,
        regla_id: str,
        objetivo: str,
        memoria: MemoriaTrabajo,
    ) -> None:
        """Solicita un dato al proveedor y lo registra como hecho del usuario."""
        esperado = condicion.valor
        if condicion.operador == "verdadero":
            esperado = True
        elif condicion.operador == "falso":
            esperado = False
        respuesta = self.proveedor(condicion.atributo, esperado) if self.proveedor else None
        if respuesta is None:
            return
        if isinstance(respuesta, tuple) and len(respuesta) == 2:
            valor, fc = respuesta
        else:
            valor, fc = respuesta, 1.0
        traza.registrar_pregunta(
            Pregunta(
                atributo=condicion.atributo,
                valor_esperado=esperado,
                regla_id=regla_id,
                objetivo=objetivo,
                momento=_ahora(),
            )
        )
        memoria.actualizar(
            condicion.atributo,
            valor,
            fc,
            origen="usuario",
            detalle=f"respuesta a la pregunta sobre {condicion.texto}",
        )

    def _disparar(
        self,
        regla: Regla,
        cf_premisa: float,
        memoria: MemoriaTrabajo,
        traza: TrazaInferencia,
    ) -> float:
        """Aplica una regla, registra el hecho y documenta el paso en la traza."""
        cf_conclusion = propagar_fc(regla.fc, cf_premisa)
        memoria.registrar(
            Hecho(
                atributo=regla.conclusion.atributo,
                valor=regla.conclusion.valor,
                fc=cf_conclusion,
                origen=f"regla:{regla.id}",
                detalle=f"FC premisa {cf_premisa:.3f} × FC regla {regla.fc:.3f}",
            )
        )
        traza.registrar_disparo(
            PasoInferencia(
                orden=len(traza) + 1,
                regla_id=regla.id,
                descripcion=regla.descripcion,
                categoria=regla.categoria,
                premisa=regla.condiciones.texto,
                cf_premisa=cf_premisa,
                fc_regla=regla.fc,
                cf_conclusion=cf_conclusion,
                conclusion_atributo=regla.conclusion.atributo,
                conclusion_valor=regla.conclusion.valor,
                momento=_ahora(),
            )
        )
        return cf_conclusion

    @staticmethod
    def _comparar(valor: object, operador: str, esperado: object) -> bool:
        """Compara el valor de un hecho con el operador declarativo de la regla."""
        if operador == "igual":
            return valor == esperado
        if operador == "distinto":
            return valor != esperado
        if operador in {"en", "no_en"}:
            try:
                pertenece = valor in esperado  # type: ignore[operator]
            except TypeError:
                return False
            return pertenece if operador == "en" else not pertenece
        if operador == "verdadero":
            return bool(valor) is True
        if operador == "falso":
            return bool(valor) is False
        try:
            izquierda = float(valor)  # type: ignore[arg-type]
            derecha = float(esperado)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return False
        if operador == "mayor_que":
            return izquierda > derecha
        if operador == "menor_que":
            return izquierda < derecha
        if operador == "mayor_o_igual":
            return izquierda >= derecha
        return izquierda <= derecha
