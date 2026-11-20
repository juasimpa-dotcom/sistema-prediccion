"""Aritmética de factores de certeza estilo MYCIN.

El módulo concentra las cuatro operaciones del razonamiento inexacto y deja el
motor de inferencia libre de cálculos numéricos:

* **Conjunción** (``Y``): ``CF(A ∧ B) = min(CF(A), CF(B))``. Es la regla de
  Myers para evidencia conjunta: la certeza no puede superar al eslabón más
  débil.
* **Disyunción** (``O``): ``CF(A ∨ B) = max(CF(A), CF(B))``.
* **Propagación**: ``CF(conclusión) = CF(regla) · CF(premisa)``.
* **Combinación de evidencia independiente** sobre la misma hipótesis:

  .. code-block:: text

      CF1 > 0 y CF2 > 0:  CF = CF1 + CF2 · (1 - CF1)
      CF1 < 0 y CF2 < 0:  CF = CF1 + CF2 · (1 + CF1)
      signos opuestos:    CF = (CF1 + CF2) / (1 - min(|CF1|, |CF2|))

  El denominador del caso mixto se protege con ``EPSILON``: si ambos factores
  tienen magnitud 1 la evidencia se anula y el resultado es 0. La combinación
  es conmutativa y monótona en cada argumento.

Todos los factores están acotados a ``[-1, 1]``: ``+1`` certeza absoluta a
favor, ``-1`` certeza absoluta en contra y ``0`` desconocimiento.
"""

from __future__ import annotations

from collections.abc import Iterable

from config import EPSILON


def validar_fc(valor: float, nombre: str = "factor de certeza") -> float:
    """Valida y normaliza un factor de certeza.

    Args:
        valor: Factor de certeza a comprobar.
        nombre: Etiqueta usada en los mensajes de error.

    Returns:
        El factor convertido a ``float``.

    Raises:
        TypeError: Si el valor no es numérico o es booleano.
        ValueError: Si el valor queda fuera de ``[-1, 1]``.
    """
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise TypeError(f"{nombre} debe ser numérico, se recibió {type(valor).__name__}")
    resultado = float(valor)
    if resultado < -1.0 or resultado > 1.0:
        raise ValueError(f"{nombre} debe estar en [-1, 1], se recibió {resultado}")
    return resultado


def combinar_fc(*factores: float) -> float:
    """Combina factores de certeza independientes sobre una misma hipótesis.

    Args:
        *factores: Factores a combinar en cualquier orden.

    Returns:
        Factor resultante en ``[-1, 1]``. Sin argumentos devuelve ``0.0``.

    Raises:
        TypeError: Si algún factor no es numérico.
        ValueError: Si algún factor queda fuera de ``[-1, 1]``.
    """
    resultado = 0.0
    for factor in factores:
        actual = validar_fc(factor)
        if actual == 0.0:
            continue
        if resultado == 0.0:
            resultado = actual
        elif resultado > 0.0 and actual > 0.0:
            resultado = resultado + actual * (1.0 - resultado)
        elif resultado < 0.0 and actual < 0.0:
            resultado = resultado + actual * (1.0 + resultado)
        else:
            denominador = 1.0 - min(abs(resultado), abs(actual))
            resultado = 0.0 if denominador < EPSILON else (resultado + actual) / denominador
    return max(-1.0, min(1.0, resultado))


def cf_conjuncion(factores: Iterable[float]) -> float:
    """Calcula el factor de una condición conjunta como el mínimo.

    Args:
        factores: Factores de cada condición.

    Returns:
        El menor factor, o ``0.0`` si no hay factores.
    """
    valores = [validar_fc(factor) for factor in factores]
    return min(valores) if valores else 0.0


def cf_disjuncion(factores: Iterable[float]) -> float:
    """Calcula el factor de una condición disyuntiva como el máximo.

    Args:
        factores: Factores de cada condición.

    Returns:
        El mayor factor, o ``0.0`` si no hay factores.
    """
    valores = [validar_fc(factor) for factor in factores]
    return max(valores) if valores else 0.0


def propagar_fc(fc_regla: float, fc_premisa: float) -> float:
    """Propaga la certeza de una regla a través de su premisa.

    Args:
        fc_regla: Factor de certeza asignado a la regla.
        fc_premisa: Factor de certeza de la premisa evaluada.

    Returns:
        Producto de ambos factores, acotado a ``[-1, 1]``.
    """
    return max(-1.0, min(1.0, validar_fc(fc_regla) * validar_fc(fc_premisa, "premisa")))


def supera_umbral(fc: float, umbral: float) -> bool:
    """Indica si una certeza positiva alcanza el umbral de disparo.

    Args:
        fc: Factor de certeza evaluado.
        umbral: Umbral mínimo requerido.

    Returns:
        ``True`` si ``fc >= umbral``.
    """
    return validar_fc(fc) >= validar_fc(umbral, "umbral")
