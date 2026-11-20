"""Pruebas del motor de inferencia en ambos sentidos y de sus trazas."""

from __future__ import annotations

import pytest

from expert_system.base_conocimientos import BaseConocimientos
from expert_system.memoria_trabajo import MemoriaTrabajo
from expert_system.motor_inferencia import (
    MotorInferencia,
    PasoInferencia,
    Pregunta,
    TrazaInferencia,
)


def atom(atributo: str, operador: str, valor: object) -> dict:
    """Construye una condición atómica declarativa."""
    return {"atributo": atributo, "operador": operador, "valor": valor}


def grupo(*condiciones: dict, operador: str = "and") -> dict:
    """Agrupa condiciones bajo ``and`` u ``or``."""
    return {"operador": operador, "condiciones": list(condiciones)}


def regla(
    identificador: str,
    condiciones: dict,
    atributo: str = "resultado",
    valor: object = "si",
    fc: float = 0.8,
    prioridad: int = 5,
    categoria: str = "prueba",
) -> dict:
    """Construye una regla declarativa de prueba."""
    return {
        "id": identificador,
        "descripcion": f"Regla {identificador}",
        "categoria": categoria,
        "prioridad": prioridad,
        "fc": fc,
        "condiciones": condiciones,
        "conclusion": {"atributo": atributo, "valor": valor},
    }


def base_con(reglas: list[dict]) -> BaseConocimientos:
    """Crea una base de conocimientos con las reglas indicadas."""
    return BaseConocimientos.desde_dict({"version": "test", "reglas": reglas})


def grupo_objeto(condiciones: dict):
    """Parsea un grupo declarativo con la base para obtener su objeto tipado."""
    return base_con([regla("TMP", condiciones)]).reglas[0].condiciones


@pytest.mark.parametrize(
    ("operador", "esperado", "valor", "resultado"),
    [
        ("igual", 3, 3, True),
        ("igual", 3, 4, False),
        ("distinto", 3, 4, True),
        ("mayor_que", 3, 4, True),
        ("menor_que", 3, 2, True),
        ("mayor_o_igual", 3, 3, True),
        ("menor_o_igual", 3, 2, True),
        ("en", (1, 2), 2, True),
        ("no_en", (1, 2), 5, True),
        ("verdadero", True, True, True),
        ("falso", False, False, True),
        ("falso", False, True, False),
        ("mayor_que", 3, "mucho", False),
        ("en", 5, 5, False),
    ],
)
def test_comparadores(operador: str, esperado: object, valor: object, resultado: bool) -> None:
    """Todos los operadores declarativos comparan como se espera."""
    assert MotorInferencia._comparar(valor, operador, esperado) is resultado


def test_evaluar_grupos_y_contradiccion() -> None:
    """AND toma el mínimo, OR el máximo y una condición falsa invierte el FC."""
    base = base_con([regla("X", grupo(atom("a", "igual", 1)))])
    memoria = MemoriaTrabajo()
    memoria.actualizar("a", 5, 0.6, "sensor")
    memoria.actualizar("b", 7, 0.3, "sensor")
    motor = MotorInferencia(base, memoria)

    and_group = grupo(atom("a", "mayor_que", 1), atom("b", "menor_que", 10))
    or_group = grupo(atom("a", "mayor_que", 10), atom("b", "menor_que", 10), operador="or")
    anidado = grupo(and_group, atom("desconocido", "igual", 1), operador="or")

    assert motor.evaluar_condiciones(grupo_objeto(and_group)) == pytest.approx(0.3)
    assert motor.evaluar_condiciones(grupo_objeto(or_group)) == pytest.approx(0.3)
    assert motor.evaluar_condiciones(grupo_objeto(anidado)) == pytest.approx(0.3)
    contradiccion = grupo(atom("a", "mayor_que", 10))
    assert motor.evaluar_condiciones(grupo_objeto(contradiccion)) == pytest.approx(-0.6)
    ausente = grupo(atom("falta", "igual", 1))
    assert motor.evaluar_condiciones(grupo_objeto(ausente)) == 0.0
    with pytest.raises(TypeError):
        motor.evaluar_condiciones(atom("a", "igual", 5))  # type: ignore[arg-type]


def test_encadenamiento_adelante_resuelve_conflictos() -> None:
    """Las reglas se disparan por prioridad, especificidad y finally id."""
    reglas = [
        regla(
            "A",
            grupo(
                atom("semilla", "igual", 1),
                atom("semilla", "mayor_que", 0),
                atom("semilla", "menor_que", 2),
            ),
            prioridad=5,
        ),
        regla("Z", grupo(atom("semilla", "igual", 1)), prioridad=9),
        regla(
            "B", grupo(atom("semilla", "igual", 1), atom("semilla", "mayor_que", 0)), prioridad=5
        ),
    ]
    motor = MotorInferencia(base_con(reglas))
    motor.memoria.actualizar("semilla", 1, 1.0, "sensor")
    traza = motor.encadenar_adelante()

    assert traza.modo == "adelante"
    assert traza.reglas_usadas() == ("Z", "A", "B")
    assert len(traza) == 3
    assert [paso.orden for paso in traza.pasos] == [1, 2, 3]
    assert "Z" in traza.reglas_disparadas


def test_encadenamiento_adelante_no_repite_reglas_en_ciclo() -> None:
    """Un ciclo de reglas se detiene porque cada regla se dispara una sola vez."""
    reglas = [
        regla("A", grupo(atom("x", "igual", 1)), atributo="y", valor=1),
        regla("B", grupo(atom("y", "igual", 1)), atributo="x", valor=1),
    ]
    motor = MotorInferencia(base_con(reglas))
    motor.memoria.actualizar("x", 1, 1.0, "sensor")
    traza = motor.encadenar_adelante()
    assert traza.reglas_usadas() == ("A", "B")


def test_umbral_de_disparo() -> None:
    """Una premisa débil no dispara la regla salvo que se baje el umbral."""
    base = base_con([regla("U", grupo(atom("hecho", "igual", 1)))])
    memoria = MemoriaTrabajo()
    memoria.actualizar("hecho", 1, 0.1, "sensor")
    assert len(MotorInferencia(base, memoria).encadenar_adelante()) == 0
    assert len(MotorInferencia(base, memoria, umbral=0.05).encadenar_adelante()) == 1


def test_combinacion_de_evidencia_en_el_motor() -> None:
    """Varias reglas sobre la misma conclusión combinan sus FC con MYCIN."""
    reglas = [
        regla("P1", grupo(atom("a", "igual", 1)), "causa", "x", fc=0.6),
        regla("P2", grupo(atom("b", "igual", 1)), "causa", "x", fc=0.6),
        regla("N1", grupo(atom("c", "igual", 1)), "causa", "x", fc=-0.4),
    ]
    motor = MotorInferencia(base_con(reglas))
    for nombre in ("a", "b", "c"):
        motor.memoria.actualizar(nombre, 1, 1.0, "sensor")
    traza = motor.encadenar_adelante()
    assert len(traza) == 3
    assert motor.memoria.consultar("causa", "x").fc == pytest.approx(0.733333, abs=1e-4)  # type: ignore[union-attr]
    assert "Evidencia de" not in traza.objetivo


def test_hecho_derivado_registra_origen_y_calculo() -> None:
    """El hecho derivado conserva la regla y los factores intermedios."""
    base = base_con([regla("D", grupo(atom("a", "igual", 1)), "causa", "stock", fc=0.9)])
    motor = MotorInferencia(base)
    motor.memoria.actualizar("a", 1, 0.8, "sensor")
    motor.encadenar_adelante()
    hecho = motor.memoria.consultar("causa", "stock")
    assert hecho is not None
    assert hecho.origen == "regla:D"
    assert "FC premisa 0.800" in hecho.detalle
    assert hecho.fc == pytest.approx(0.72)


def test_verificar_hecho_directo() -> None:
    """Un hecho conocido se verifica sin disparar reglas."""
    motor = MotorInferencia(base_con([regla("X", grupo(atom("a", "igual", 1)))]))
    motor.memoria.actualizar("causa", "stock", 0.9, "sensor")
    resultado = motor.verificar("causa", "stock")
    assert resultado
    assert resultado.fc == pytest.approx(0.9)
    assert resultado.traza.pasos == []
    assert bool(resultado)


def test_verificar_con_subobjetos_recursivos() -> None:
    """El encadenamiento hacia atrás demuestra primero los subobjetos simbólicos."""
    reglas = [
        regla("D", grupo(atom("a", "igual", 1)), "causa", "stock", fc=0.8),
        regla("R", grupo(atom("causa", "igual", "stock")), "nivel", "alto", fc=0.9),
    ]
    motor = MotorInferencia(base_con(reglas))
    motor.memoria.actualizar("a", 1, 1.0, "sensor")
    resultado = motor.verificar("nivel", "alto")
    assert resultado
    assert resultado.fc == pytest.approx(0.72)
    assert resultado.traza.reglas_usadas() == ("D", "R")
    assert resultado.descripcion == "nivel=alto (FC +0.72)"
    assert resultado.traza.modo == "atras"


def test_verificar_agrupa_reglas_y_combina() -> None:
    """Dos reglas que respaldan la misma hipótesis se combinan."""
    reglas = [
        regla("P1", grupo(atom("a", "igual", 1)), "causa", "x", fc=0.6),
        regla("P2", grupo(atom("b", "igual", 1)), "causa", "x", fc=0.6),
    ]
    motor = MotorInferencia(base_con(reglas))
    motor.memoria.actualizar("a", 1, 1.0, "sensor")
    motor.memoria.actualizar("b", 1, 1.0, "sensor")
    resultado = motor.verificar("causa", "x")
    assert resultado.fc == pytest.approx(0.84)
    assert len(resultado.traza) == 2


def test_verificar_hace_preguntas_al_proveedor() -> None:
    """Los datos desconocidos se preguntan y se registran en la traza."""
    reglas = [
        regla(
            "D",
            grupo(atom("en_promocion", "falso", False), atom("caida", "mayor_que", 10)),
            "causa",
            "sin_promo",
            fc=0.8,
        )
    ]
    respuestas = {"en_promocion": (False, 0.8)}

    def proveedor(atributo: str, esperado: object) -> object | None:
        return respuestas.get(atributo)

    motor = MotorInferencia(base_con(reglas), proveedor=proveedor)
    motor.memoria.actualizar("caida", 20, 1.0, "sensor")
    resultado = motor.verificar("causa", "sin_promo")

    assert resultado
    assert resultado.fc == pytest.approx(0.64)
    assert len(resultado.traza.preguntas) == 1
    pregunta = resultado.traza.preguntas[0]
    assert pregunta.atributo == "en_promocion"
    assert pregunta.valor_esperado is False
    assert pregunta.regla_id == "D"
    assert pregunta.objetivo == "causa=sin_promo"
    assert motor.memoria.consultar("en_promocion").origen == "usuario"


def test_proveedor_sin_respuesta_no_dispara() -> None:
    """Si el proveedor no sabe, la hipótesis queda sin confirmar."""
    base = base_con([regla("D", grupo(atom("dato", "igual", 1)))])

    def proveedor(atributo: str, esperado: object) -> None:
        return None

    motor = MotorInferencia(base, proveedor=proveedor)
    resultado = motor.verificar("resultado", "si")
    assert not resultado
    assert resultado.fc == 0.0


def test_verificar_ciclo_termina() -> None:
    """Un par de reglas circulares no produce recursión infinita."""
    reglas = [
        regla("A", grupo(atom("b", "igual", 1)), "a", 1),
        regla("B", grupo(atom("a", "igual", 1)), "b", 1),
    ]
    motor = MotorInferencia(base_con(reglas))
    resultado = motor.verificar("a", 1)
    assert not resultado
    assert len(resultado.traza) == 0


def test_verificar_valor_en_y_hecho_debajo_del_umbral() -> None:
    """La condición 'en' explora alternativas y un FC bajo no basta."""
    reglas = [
        regla("D", grupo(atom("causa", "en", ["x", "y"])), "nivel", "alto", fc=0.8),
        regla("X", grupo(atom("a", "igual", 1)), "causa", "x", fc=0.9),
    ]
    motor = MotorInferencia(base_con(reglas))
    motor.memoria.actualizar("a", 1, 0.1, "sensor")
    assert not motor.verificar("nivel", "alto")

    motor.memoria.actualizar("a", 1, 1.0, "sensor")
    assert motor.verificar("nivel", "alto").fc == pytest.approx(0.72)


def test_validaciones_del_motor() -> None:
    """El motor valida sus dependencias y parámetros."""
    base = base_con([regla("X", grupo(atom("a", "igual", 1)))])
    with pytest.raises(TypeError):
        MotorInferencia("no es base")
    with pytest.raises(TypeError):
        MotorInferencia(base, memoria="no es memoria")
    with pytest.raises(TypeError):
        MotorInferencia(base, proveedor="no es funcion")
    with pytest.raises(ValueError):
        MotorInferencia(base, umbral=-0.1)
    with pytest.raises(ValueError):
        MotorInferencia(base, umbral=1.5)
    motor = MotorInferencia(base)
    with pytest.raises(TypeError):
        motor.encadenar_adelante(memoria="no es memoria")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        motor.verificar("a", ["no hashable"])
    with pytest.raises(TypeError):
        motor.verificar("a", 1, memoria="no es memoria")  # type: ignore[arg-type]


def test_traza_registra_pasos_y_preguntas() -> None:
    """La traza expone sus reglas, pasos y preguntas."""
    traza = TrazaInferencia(modo="atras", objetivo="objetivo")
    paso = PasoInferencia(
        orden=1,
        regla_id="R",
        descripcion="desc",
        categoria="prueba",
        premisa="(a es 1)",
        cf_premisa=1.0,
        fc_regla=0.8,
        cf_conclusion=0.8,
        conclusion_atributo="resultado",
        conclusion_valor="si",
        momento="2026-01-01T00:00:00+00:00",
    )
    traza.registrar_disparo(paso)
    traza.registrar_pregunta(Pregunta("a", 1, "R", "objetivo", "2026-01-01T00:00:00+00:00"))
    assert traza.reglas_usadas() == ("R",)
    assert len(traza) == 1
    assert traza.pasos[0].conclusion == "resultado=si"
    assert traza.preguntas[0].atributo == "a"
    assert traza.inicio
