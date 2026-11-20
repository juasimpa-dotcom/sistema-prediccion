"""Fixtures compartidas por las pruebas de la Fase 2."""

from __future__ import annotations

import pandas as pd
import pytest

from config import ARCHIVO_VENTAS_CRUDO, CARACTERISTICAS_CATEGORICAS, CARACTERISTICAS_NUMERICAS
from ml.preprocesamiento import construir_dataset_supervisado


@pytest.fixture(scope="session")
def crudo() -> pd.DataFrame:
    """Dataset crudo generado en la Fase 1."""
    return pd.read_csv(ARCHIVO_VENTAS_CRUDO, parse_dates=["fecha_semana"])


@pytest.fixture(scope="session")
def supervisado(crudo: pd.DataFrame) -> pd.DataFrame:
    """Tabla supervisada construida a partir del dataset crudo."""
    return construir_dataset_supervisado(crudo)


@pytest.fixture(scope="session")
def columnas() -> list[str]:
    """Columnas de características usadas por los modelos."""
    return [*CARACTERISTICAS_NUMERICAS, *CARACTERISTICAS_CATEGORICAS]
