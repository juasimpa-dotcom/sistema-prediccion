"""Crea la estructura base del proyecto de IA."""

from pathlib import Path

RAIZ = Path(__file__).parent

CARPETAS = [
    "data/raw",
    "data/processed",
    "ml",
    "models",
    "expert_system",
    "search",
    "api",
    "app",
    "tests",
    "docs",
    "notebooks",
]

# Carpetas que serán paquetes de Python
PAQUETES = ["ml", "expert_system", "search", "api", "tests"]

ARCHIVOS = {
    # Datos
    "data/generar_dataset.py": '"""Generador del dataset simulado de ventas."""\n',
    # Machine Learning
    "ml/preprocesamiento.py": '"""Limpieza e ingeniería de características."""\n',
    "ml/entrenamiento.py": '"""Entrenamiento y comparación de modelos."""\n',
    "ml/evaluacion.py": '"""Métricas: MAE, RMSE, R2."""\n',
    "ml/explicabilidad.py": '"""Explicación de predicciones con SHAP."""\n',
    # Sistema experto
    "expert_system/memoria_trabajo.py": '"""Memoria de trabajo: hechos."""\n',
    "expert_system/base_conocimientos.py": '"""Base de conocimientos: reglas con factores de certeza."""\n',
    "expert_system/motor_inferencia.py": '"""Motor de inferencia: encadenamiento hacia adelante y atrás."""\n',
    "expert_system/logica_difusa.py": '"""Variables y reglas difusas."""\n',
    "expert_system/explicacion.py": '"""Módulo de explicación: por qué y cómo."""\n',
    # Búsqueda
    "search/espacio_estados.py": '"""Representación del problema como espacio de estados."""\n',
    "search/no_informada.py": '"""BFS, DFS y Backtracking."""\n',
    "search/informada.py": '"""Greedy y A*."""\n',
    "search/minimax.py": '"""Minimax (decisión adversarial, opcional)."""\n',
    # API / App
    "api/main.py": '"""API FastAPI."""\n',
    "app/dashboard.py": '"""Dashboard Streamlit."""\n',
    # Docs
    "docs/commonkads.md": "# Ingeniería del conocimiento (CommonKADS simplificado)\n",
    "docs/informe.md": "# Informe del proyecto\n",
    # Raíz
    "README.md": "# Sistema inteligente de predicción del rendimiento de ventas\n",
    ".gitignore": "venv/\n__pycache__/\n*.pyc\n.ipynb_checkpoints/\n.env\nmodels/*.joblib\n.vscode/\n",
}


def main():
    for carpeta in CARPETAS:
        (RAIZ / carpeta).mkdir(parents=True, exist_ok=True)
        (RAIZ / carpeta / ".gitkeep").touch()

    for paquete in PAQUETES:
        (RAIZ / paquete / "__init__.py").touch()

    for ruta, contenido in ARCHIVOS.items():
        archivo = RAIZ / ruta
        if not archivo.exists():
            archivo.write_text(contenido, encoding="utf-8")

    print("Estructura creada correctamente.")


if __name__ == "__main__":
    main()
