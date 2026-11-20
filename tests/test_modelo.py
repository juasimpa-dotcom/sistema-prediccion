"""Pruebas de métricas, artefactos, confianza y fachada de predicción."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import Ridge

from config import ARCHIVO_MODELO, COLUMNA_OBJETIVO
from ml.entrenamiento import (
    cargar_artefacto,
    estimar_confianza,
    guardar_artefacto,
)
from ml.evaluacion import calcular_metricas, construir_tabla
from ml.explicabilidad import transformar_entrada
from ml.predictor import PrediccionVentas, PredictorVentas
from ml.preprocesamiento import construir_pipeline, dividir_temporal


@pytest.fixture(scope="module")
def ruta_modelo(
    tmp_path_factory: pytest.TempPathFactory,
    supervisado: pd.DataFrame,
    columnas: list[str],
):
    """Entrena un modelo pequeño y lo guarda como artefacto temporal."""
    entrenamiento, prueba = dividir_temporal(supervisado)
    pipeline = construir_pipeline(Ridge(alpha=10.0))
    pipeline.fit(entrenamiento.loc[:, columnas], entrenamiento[COLUMNA_OBJETIVO])
    fondo = transformar_entrada(pipeline, prueba.loc[:, columnas].iloc[:30])
    metadatos = {
        "version": "2.0.0-test",
        "nombre_modelo": "Ridge",
        "metricas": {"mae": 100.0, "rmse": 120.0, "r2": 0.8, "mape": 10.0},
        "calibracion": {
            "desvio_residuos_relativos": 0.2,
            "mape_prueba": 10.0,
            "meta_promedio": 14000.0,
        },
    }
    ruta = tmp_path_factory.mktemp("modelos") / "modelo.joblib"
    guardar_artefacto(pipeline, metadatos, ruta=ruta, fondo=fondo)
    return ruta


def test_cargar_artefacto(ruta_modelo) -> None:
    """El artefacto joblib conserva pipeline, metadatos y fondo SHAP."""
    artefacto = cargar_artefacto(ruta_modelo)
    assert "pipeline" in artefacto
    assert artefacto["metadatos"]["nombre_modelo"] == "Ridge"
    assert artefacto["fondo"].shape[1] > 0


def test_cargar_artefacto_inexistente(tmp_path) -> None:
    """Se informa claramente si el modelo no existe."""
    with pytest.raises(FileNotFoundError):
        cargar_artefacto(tmp_path / "no_existe.joblib")


def test_fachada_prediccion(ruta_modelo, supervisado: pd.DataFrame) -> None:
    """La fachada devuelve la dataclass con tipos y rangos válidos."""
    predictor = PredictorVentas(ruta_modelo)
    fila = supervisado.iloc[10]
    resultado = predictor.predecir(fila)

    assert isinstance(resultado, PrediccionVentas)
    assert isinstance(resultado.valor_predicho, float)
    assert resultado.valor_predicho > 0
    assert 0 <= resultado.confianza <= 1
    assert resultado.cumplimiento_esperado_pct > 0
    assert len(resultado.principales_factores) > 0
    assert all(isinstance(item, str) for item in resultado.principales_factores)


def test_fachada_con_historial(ruta_modelo, crudo: pd.DataFrame) -> None:
    """La fachada acepta un historial crudo y calcula los lags automáticamente."""
    predictor = PredictorVentas(ruta_modelo, incluir_explicacion=False)
    serie = crudo[(crudo["sucursal"] == "Sopocachi") & (crudo["categoria"] == "pollo")].head(12)
    resultado = predictor.predecir({"historial": serie})
    assert resultado.valor_predicho > 0
    assert len(resultado.principales_factores) == 1


def test_fachada_valida_columnas(ruta_modelo) -> None:
    """Se rechaza una entrada sin las columnas necesarias."""
    predictor = PredictorVentas(ruta_modelo, incluir_explicacion=False)
    with pytest.raises(ValueError, match="Faltan columnas"):
        predictor.predecir({"ventas_lag_1": 100.0})


def test_metricas_perfectas() -> None:
    """Una predicción exacta tiene error cero y R2 igual a uno."""
    real = np.array([100.0, 200.0, 300.0])
    metricas = calcular_metricas(real, real)
    assert metricas.mae == pytest.approx(0.0)
    assert metricas.rmse == pytest.approx(0.0)
    assert metricas.r2 == pytest.approx(1.0)
    assert metricas.mape == pytest.approx(0.0)


def test_metricas_conocidas() -> None:
    """Las métricas coinciden con cálculos manuales sencillos."""
    real = np.array([100.0, 200.0])
    predicho = np.array([110.0, 180.0])
    metricas = calcular_metricas(real, predicho)
    assert metricas.mae == pytest.approx(15.0)
    assert metricas.rmse == pytest.approx(np.sqrt(250.0))
    assert metricas.mape == pytest.approx(10.0)


def test_tabla_comparativa_ordena_y_mide_mejora() -> None:
    """La tabla ordena por MAE y calcula la mejora sobre el baseline."""
    de = calcular_metricas([1, 2], [1.5, 2.5])
    bueno = calcular_metricas([1, 2], [1.1, 2.1])
    tabla = construir_tabla({"Baseline (semana anterior)": de, "Modelo": bueno})
    assert tabla.index[0] == "Modelo"
    assert tabla.loc["Modelo", "mejora_vs_baseline_pct"] > 0


def test_confianza_acotada_y_monotona() -> None:
    """La confianza está en [0, 1] y baja al crecer la incertidumbre."""
    alta = estimar_confianza(15000.0, 15000.0, 0.2, 10.0)
    baja = estimar_confianza(15000.0, 12000.0, 0.2, 10.0)
    assert 0 <= baja <= alta <= 1
    assert estimar_confianza(15000.0, 1000.0, 0.01, 60.0) >= 0.0


def test_artefacto_real_si_existe() -> None:
    """Si el entrenamiento ya guardó el artefacto real, también debe cargar."""
    if not ARCHIVO_MODELO.exists():
        pytest.skip("El modelo real aún no fue entrenado")
    predictor = PredictorVentas(ARCHIVO_MODELO, incluir_explicacion=False)
    assert predictor.metadatos["version"].startswith("2.")
