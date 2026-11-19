"""Comprueba que todas las librerías están instaladas."""

import importlib

LIBRERIAS = [
    "pandas",
    "numpy",
    "sklearn",
    "joblib",
    "shap",
    "skfuzzy",
    "matplotlib",
    "seaborn",
    "fastapi",
    "uvicorn",
    "streamlit",
    "plotly",
    "pytest",
]

errores = 0
for lib in LIBRERIAS:
    try:
        modulo = importlib.import_module(lib)
        version = getattr(modulo, "__version__", "ok")
        print(f"[OK]    {lib:<12} {version}")
    except Exception as e:
        errores += 1
        print(f"[ERROR] {lib:<12} {e}")

print("\nEntorno listo." if errores == 0 else f"\nHay {errores} librería(s) con problemas.")
