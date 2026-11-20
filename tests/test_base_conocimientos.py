"""Pruebas de carga, validación y consulta de la base de conocimientos."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from config import ARCHIVO_REGLAS_EXPERTO
from expert_system.base_conocimientos import (
    BaseConocimientos,
    Condicion,
    Consecuente,
    GrupoCondiciones,
    Regla,
)


def regla_valida() -> dict:
    """Devuelve una regla mínima válida en formato declarativo."""
    return {
        "id": "T01",
        "descripcion": "Regla de prueba",
        "categoria": "diagnostico",
        "prioridad": 5,
        "fc": 0.8,
        "condiciones": {
            "operador": "and",
            "condiciones": [{"atributo": "valor", "operador": "mayor_que", "valor": 10}],
        },
        "conclusion": {"atributo": "resultado", "valor": "alto"},
    }


def base_desde(reglas: list[dict]) -> BaseConocimientos:
    """Construye una base a partir de reglas declarativas."""
    return BaseConocimientos.desde_dict({"version": "test", "reglas": reglas})


def test_base_json_real(base_reglas: BaseConocimientos) -> None:
    """La base retail cargada cumple el tamaño y las categorías exigidas."""
    assert len(base_reglas.reglas) >= 25
    assert base_reglas.version == "3.0.0"
    categorias = base_reglas.categorias()
    assert {"diagnostico", "riesgo", "recomendacion"} <= set(categorias)
    assert len(base_reglas.por_categoria("diagnostico")) >= 6
    assert len(base_reglas.por_categoria("riesgo")) >= 5
    assert len(base_reglas.por_categoria("recomendacion")) >= 5
    assert base_reglas.por_id("D01").id == "D01"
    assert base_reglas.para_conclusion("nivel_riesgo", "alto")
    reglas = base_reglas.para_conclusion("nivel_riesgo")
    prioridades = [regla.prioridad for regla in reglas]
    assert prioridades == sorted(prioridades, reverse=True)


def test_ruta_por_defecto(base_reglas: BaseConocimientos) -> None:
    """La ruta configurada apunta al JSON de reglas."""
    assert ARCHIVO_REGLAS_EXPERTO.is_file()
    assert base_reglas.version == "3.0.0"


def test_desde_objetos() -> None:
    """También se acepta una lista de objetos Regla ya instanciados."""
    regla = Regla(
        id="P01",
        descripcion="Hecho directo",
        condiciones=GrupoCondiciones("and", (Condicion("x", "verdadero", True),)),
        conclusion=Consecuente("y", True),
        fc=0.9,
        prioridad=1,
        categoria="prueba",
    )
    base = BaseConocimientos.desde_objetos([regla], "x")
    assert base.reglas == (regla,)
    assert regla.especificidad == 1
    assert "x es sí" in regla.texto
    assert base.por_id("P01") is regla
    with pytest.raises(KeyError):
        base.por_id("inexistente")


def test_grupos_anidados_y_texto() -> None:
    """Los grupos anidados cuentan su especificidad y se imprimen con paréntesis."""
    grupo = GrupoCondiciones(
        "or",
        (
            Condicion("a", "igual", "x"),
            GrupoCondiciones("and", (Condicion("b", "menor_que", 3), Condicion("c", "en", (1, 2)))),
        ),
    )
    assert grupo.especificidad == 3
    assert " Y " in grupo.texto and " O " in grupo.texto
    with pytest.raises(TypeError):
        GrupoCondiciones("and", ("no es condición",))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Condicion("a", "en", 5)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Condicion("a", "en", ())
    with pytest.raises(TypeError):
        Condicion("a", "verdadero", "sí")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Condicion("a", "mayor_que", "mucho")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Condicion("", "igual", 1)
    with pytest.raises(ValueError):
        Condicion("a", "desconocido", 1)
    with pytest.raises(ValueError):
        GrupoCondiciones("xor", (Condicion("a", "igual", 1),))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        GrupoCondiciones("and", ())  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Consecuente("", 1)
    with pytest.raises(TypeError):
        Consecuente("a", [1])


def test_regla_valida_campos() -> None:
    """Una regla bien formada expone sus propiedades derivadas."""
    base = base_desde([regla_valida()])
    regla = base.reglas[0]
    assert regla.especificidad == 1
    assert "FC +0.80" in regla.texto
    assert base.para_conclusion("resultado", "otro") == ()


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("id", ""),
        ("descripcion", ""),
        ("fc", 0.0),
        ("fc", 2.0),
        ("fc", "alto"),
        ("prioridad", -1),
        ("prioridad", 1.5),
        ("prioridad", True),
        ("categoria", ""),
    ],
)
def test_campos_de_regla_mal_formados(campo: str, valor: object) -> None:
    """Los campos escalares de una regla se validan al cargar."""
    datos = regla_valida()
    datos[campo] = valor
    with pytest.raises(ValueError):
        base_desde([datos])


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("conclusion", {"atributo": "x"}),
        ("conclusion", {"atributo": "", "valor": 1}),
        ("condiciones", []),
        (
            "condiciones",
            {"operador": "no", "condiciones": [{"atributo": "a", "operador": "igual", "valor": 1}]},
        ),
        ("condiciones", {"operador": "and", "condiciones": []}),
        ("condiciones", {"operador": "and", "condiciones": [{"atributo": "a"}]}),
        (
            "condiciones",
            {"operador": "and", "condiciones": [{"atributo": "a", "operador": "x", "valor": 1}]},
        ),
        ("condiciones", {"operador": "and", "extra": 1, "condiciones": []}),
        (
            "condiciones",
            {
                "operador": "and",
                "condiciones": [{"atributo": "a", "operador": "mayor_que", "valor": "x"}],
            },
        ),
    ],
)
def test_estructura_de_regla_mal_formada(campo: str, valor: object) -> None:
    """Las conclusiones y condiciones mal formadas se rechazan."""
    datos = regla_valida()
    datos[campo] = valor
    with pytest.raises(ValueError, match="inválida"):
        base_desde([datos])


def test_base_mal_formada() -> None:
    """La estructura general de la base también se valida."""
    with pytest.raises(ValueError, match="objeto JSON"):
        BaseConocimientos.desde_dict([])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="desconocidas"):
        BaseConocimientos.desde_dict({"version": "x", "reglas": [], "extra": 1})
    with pytest.raises(ValueError, match="'reglas'"):
        BaseConocimientos.desde_dict({"version": "x"})
    with pytest.raises(ValueError, match="lista 'reglas'"):
        BaseConocimientos.desde_dict({"reglas": {}})
    with pytest.raises(ValueError, match="versión"):
        BaseConocimientos.desde_dict({"reglas": [], "version": 3})
    with pytest.raises(ValueError, match="al menos una regla"):
        base_desde([])
    with pytest.raises(ValueError, match="repetido"):
        base_desde([regla_valida(), regla_valida()])
    with pytest.raises(ValueError, match="objeto JSON"):
        base_desde(["no es objeto"])  # type: ignore[list-item]


def test_campos_desconocidos_y_faltantes_en_regla() -> None:
    """No se toleran erratas en los nombres de campos de una regla."""
    datos = regla_valida()
    datos["extra"] = 1
    with pytest.raises(ValueError, match="campos desconocidos"):
        base_desde([deepcopy(datos)])

    del datos["extra"]
    del datos["fc"]
    with pytest.raises(ValueError, match="falta campos"):
        base_desde([datos])


def test_desde_json_inexistente_e_invalido(tmp_path: Path) -> None:
    """Un archivo ausente o con JSON roto produce un error claro."""
    with pytest.raises(FileNotFoundError):
        BaseConocimientos.desde_json(tmp_path / "no_existe.json")
    archivo = tmp_path / "malo.json"
    archivo.write_text("{ no es json", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON inválido"):
        BaseConocimientos.desde_json(archivo)
