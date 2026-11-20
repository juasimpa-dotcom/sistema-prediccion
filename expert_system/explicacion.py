"""Explicaciones en español a partir de la traza de inferencia.

Responde a las tres preguntas clásicas de un sistema experto:

* **¿POR QUÉ llegaste a esta conclusión?**: qué reglas la respaldan.
* **¿CÓMO la derivaste?**: en qué orden se dispararon y cómo se combinaron los
  factores de certeza intermedios.
* **¿POR QUÉ me pides este dato?**: qué regla y qué objetivo motivaron la
  pregunta durante el encadenamiento hacia atrás.
"""

from __future__ import annotations

from dataclasses import dataclass

from expert_system.base_conocimientos import BaseConocimientos
from expert_system.factores_certeza import combinar_fc
from expert_system.memoria_trabajo import MemoriaTrabajo
from expert_system.motor_inferencia import Pregunta, ResultadoObjetivo, TrazaInferencia


def _texto(valor: object) -> str:
    """Formatea un valor para las explicaciones."""
    if isinstance(valor, bool):
        return "sí" if valor else "no"
    if isinstance(valor, (list, tuple)):
        return "[" + ", ".join(_texto(item) for item in valor) + "]"
    return str(valor)


@dataclass(frozen=True, slots=True)
class Explicacion:
    """Conjunto de respuestas explicativas sobre una conclusión.

    Attributes:
        objetivo: Hipótesis explicada.
        por_que: Respuesta a «¿por qué?».
        como: Respuesta a «¿cómo?».
        por_que_datos: Respuestas a «¿por qué me pides este dato?».
    """

    objetivo: str
    por_que: str
    como: str
    por_que_datos: tuple[str, ...] = ()

    def a_texto(self) -> str:
        """Devuelve la explicación completa lista para imprimir."""
        partes = [
            f"=== Explicación de {self.objetivo} ===",
            "",
            "¿POR QUÉ?",
            self.por_que,
            "",
            "¿CÓMO?",
            self.como,
        ]
        if self.por_que_datos:
            partes.extend(["", "¿POR QUÉ ME PIDES ESTOS DATOS?", *self.por_que_datos])
        return "\n".join(partes)


def por_que(
    objetivo: str,
    valor: object,
    base: BaseConocimientos,
    traza: TrazaInferencia | None = None,
    memoria: MemoriaTrabajo | None = None,
) -> str:
    """Explica qué reglas respaldan una conclusión.

    Args:
        objetivo: Atributo concluido.
        valor: Valor concluido.
        base: Base de conocimientos consultada.
        traza: Traza de la inferencia, si está disponible.
        memoria: Memoria con evidencia directa adicional.

    Returns:
        Explicación en español.
    """
    destino = f"{objetivo}={_texto(valor)}"
    lineas = [f"Se concluyó «{destino}» por las siguientes razones:"]
    usadas = 0

    if traza is not None:
        for paso in traza.pasos:
            if paso.conclusion_atributo == objetivo and paso.conclusion_valor == valor:
                usadas += 1
                lineas.append(
                    f"  {usadas}. Regla {paso.regla_id}: {paso.descripcion} "
                    f"(FC de la regla {paso.fc_regla:+.2f}, FC de la premisa "
                    f"{paso.cf_premisa:+.2f}, aportó {paso.cf_conclusion:+.2f})."
                )

    if usadas == 0:
        reglas = base.para_conclusion(objetivo, valor)
        if reglas:
            lineas.append("  No se disparó ninguna regla en esta traza; las reglas aplicables son:")
            for regla in reglas:
                lineas.append(f"  - {regla.id}: {regla.descripcion} (FC {regla.fc:+.2f}).")
        else:
            lineas.append("  No hay reglas en la base que concluyan esa hipótesis.")

    if memoria is not None and memoria.contiene(objetivo, valor):
        hecho = memoria.consultar(objetivo, valor)
        if hecho is not None and not hecho.origen.startswith("regla:"):
            detalle = hecho.detalle or "dato inicial"
            lineas.append(f"  Además hay evidencia directa ({hecho.origen}): {detalle}.")

    return "\n".join(lineas)


def como(traza: TrazaInferencia, base: BaseConocimientos | None = None) -> str:
    """Explica el orden y los cálculos realizados durante una inferencia.

    Args:
        traza: Traza a narrar.
        base: Base de conocimientos, usada para enriquecer los títulos.

    Returns:
        Narración cronológica en español.
    """
    if not traza.pasos:
        return "No se disparó ninguna regla: los hechos disponibles no alcanzaron el umbral."

    titulo = (
        "encadenamiento hacia adelante"
        if traza.modo == "adelante"
        else "encadenamiento hacia atrás"
    )
    lineas = [f"Se siguió un {titulo} en {len(traza)} pasos:"]
    for paso in traza.pasos:
        descripcion = paso.descripcion
        if base is not None and not descripcion:
            descripcion = base.por_id(paso.regla_id).descripcion
        lineas.append(
            f"  {paso.orden}. [{paso.categoria}] {paso.regla_id}: {descripcion}\n"
            f"     Condiciones: {paso.premisa} => CF premisa {paso.cf_premisa:+.3f}.\n"
            f"     Se propagó {paso.cf_premisa:+.3f} × {paso.fc_regla:+.3f} = "
            f"{paso.cf_conclusion:+.3f}, por lo que se derivó «{paso.conclusion}»."
        )

    agrupados: dict[tuple[str, object], list[float]] = {}
    for paso in traza.pasos:
        clave = (paso.conclusion_atributo, paso.conclusion_valor)
        agrupados.setdefault(clave, []).append(paso.cf_conclusion)
    for (atributo, valor), factores in agrupados.items():
        if len(factores) > 1:
            lineas.append(
                f"  Evidencia de {len(factores)} reglas sobre «{atributo}={_texto(valor)}» "
                f"combinada con MYCIN: FC final {combinar_fc(*factores):+.3f}."
            )
    return "\n".join(lineas)


def por_que_pregunta(pregunta: Pregunta, base: BaseConocimientos) -> str:
    """Explica por qué el motor solicitó un dato.

    Args:
        pregunta: Pregunta registrada en la traza.
        base: Base de conocimientos con la regla motivadora.

    Returns:
        Explicación en español.
    """
    try:
        regla = base.por_id(pregunta.regla_id)
        motivo = f"la regla {regla.id} ({regla.descripcion})"
    except KeyError:
        motivo = f"la regla {pregunta.regla_id}"
    return (
        f"Te pido «{pregunta.atributo}={_texto(pregunta.valor_esperado)}» porque, "
        f"para comprobar «{pregunta.objetivo}», {motivo} necesita evaluar ese dato. "
        "Sin él no puedo calcular el factor de certeza de la premisa."
    )


def explicar(
    objetivo: str,
    valor: object,
    base: BaseConocimientos,
    traza: TrazaInferencia | None = None,
    memoria: MemoriaTrabajo | None = None,
) -> Explicacion:
    """Construye las tres explicaciones para una conclusión o resultado.

    Args:
        objetivo: Atributo explicado.
        valor: Valor explicado.
        base: Base de conocimientos.
        traza: Traza disponible.
        memoria: Memoria disponible.

    Returns:
        Estructura con todas las respuestas.
    """
    if isinstance(valor, ResultadoObjetivo):
        raise TypeError("Pase resultado.atributo y resultado.valor por separado")
    preguntas = traza.preguntas if traza is not None else ()
    return Explicacion(
        objetivo=f"{objetivo}={_texto(valor)}",
        por_que=por_que(objetivo, valor, base, traza, memoria),
        como=como(traza, base) if traza is not None else "No hay traza disponible.",
        por_que_datos=tuple(por_que_pregunta(pregunta, base) for pregunta in preguntas),
    )
