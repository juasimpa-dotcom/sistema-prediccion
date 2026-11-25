Eres un ingeniero de software senior especializado en Python, Machine Learning y Sistemas Basados en Conocimiento. Vas a ayudarme a construir, por FASES, un proyecto universitario de Inteligencia Artificial con calidad de producto profesional.

## PROYECTO
Sistema inteligente híbrido (neuro-simbólico) que predice el rendimiento de ventas y el cumplimiento de metas de una cadena de retail de alimentos en Bolivia (categorías: pollo, cerdo, embutidos y congelados), y que además razona, recomienda acciones y explica sus decisiones.

El proyecto debe demostrar estos temas de la materia:
- Tema 1 - Fundamentos de IA: IA simbólica vs no simbólica, aprendizaje automático, representación del conocimiento, incertidumbre, explicabilidad.
- Tema 2 - Problemas, representación y búsqueda: espacio de estados, búsquedas no informadas (BFS, DFS, Backtracking) e informadas (Greedy, A*), y Minimax opcional (competidor).
- Tema 3 - Ingeniería del conocimiento: Sistema Experto completo (Base de Conocimientos, Motor de Inferencia, Memoria de Trabajo, Módulo de Explicación), factores de certeza (estilo MYCIN), lógica difusa, metodología CommonKADS simplificado.

## ARQUITECTURA (flujo)
Datos -> [Módulo ML] predicción + confianza -> [Memoria de Trabajo] hechos -> [Motor de Inferencia + Base de Conocimientos con CF y lógica difusa] diagnóstico -> [Módulo de Búsqueda] plan de acciones de menor costo -> [Módulo de Explicación] (reglas disparadas + SHAP) -> API FastAPI -> Dashboard Streamlit.

## STACK
Python 3.11/3.12, pandas, numpy, scikit-learn, joblib, shap, scikit-fuzzy, matplotlib, seaborn, plotly, FastAPI, uvicorn, Streamlit, pytest. El motor de inferencia y los algoritmos de búsqueda son implementación PROPIA (no uses librerías que los oculten): el objetivo es demostrar que entiendo la teoría.

## ESTRUCTURA EXISTENTE (no la cambies sin avisarme)
sistema_prediccion/
  data/ (raw, processed, generar_dataset.py)
  ml/ (preprocesamiento.py, entrenamiento.py, evaluacion.py, explicabilidad.py)
  models/
  expert_system/ (memoria_trabajo.py, base_conocimientos.py, motor_inferencia.py, logica_difusa.py, explicacion.py)
  search/ (espacio_estados.py, no_informada.py, informada.py, minimax.py)
  api/ (main.py)
  app/ (dashboard.py)
  tests/
  docs/ (commonkads.md, INFORME_TECNICO.md)
  notebooks/
  requirements.txt, README.md

## REGLAS DE CALIDAD DE CÓDIGO (obligatorias en TODAS las fases)
1. Estilo: PEP 8, formateo con black y lint con ruff (agrega pyproject.toml con su configuración). Líneas de máx. 100 caracteres.
2. Tipado: type hints en todas las funciones y métodos públicos. Usa dataclasses, Enum y Protocol/ABC donde aporte claridad.
3. Documentación: docstrings en español (estilo Google) en módulos, clases y funciones públicas. Comentarios solo para explicar el "por qué", nunca el "qué".
4. Nombres: identificadores descriptivos en español o inglés, pero CONSISTENTES en todo el proyecto (usa español para dominio de negocio y términos de la materia). Sin abreviaturas crípticas.
5. Diseño: principios SOLID, funciones pequeñas con una sola responsabilidad, bajo acoplamiento, alta cohesión, sin código duplicado (DRY), sin clases "Dios". Prefiere composición sobre herencia.
6. Cero números mágicos ni rutas escritas a mano: toda constante, ruta, semilla e hiperparámetro va en un módulo central config.py (o dataclass de configuración).
7. Reproducibilidad: semilla fija en todo proceso aleatorio. Mismo input = mismo output.
8. Manejo de errores: excepciones propias y específicas (nunca except: desnudo), validación de entradas en los límites del sistema, mensajes claros.
9. Logging: usa el módulo logging (no print) en la lógica; print solo en scripts de demostración.
10. Pruebas: pytest con pruebas unitarias para toda lógica relevante (casos normales, bordes y errores). Cobertura objetivo >= 80% en expert_system/ y search/. Las pruebas deben ser deterministas y rápidas.
11. Sin efectos secundarios al importar módulos. Código ejecutable solo bajo if __name__ == "__main__".
12. ML correcto: sin fuga de datos (data leakage), división temporal (no aleatoria) para series de tiempo, pipelines de scikit-learn, métricas reportadas sobre el conjunto de prueba, comparación contra un baseline simple.
13. Dependencias: no agregues librerías fuera del stack sin preguntarme; si es necesario, justifícalo y actualiza requirements.txt.
14. Seguridad básica: sin secretos en el código, .gitignore correcto, validación de entradas en la API (Pydantic).

## FORMA DE TRABAJO (obligatoria)
- Trabaja SOLO la fase que te indique. No adelantes trabajo de fases futuras.
- Antes de escribir código, muestra un plan breve (qué archivos tocarás y qué decisiones de diseño tomarás). Si hay ambigüedad real, pregúntame; si no, decide con criterio y documenta la decisión.
- Implementa de forma incremental y ejecuta lo que construyas (pruebas, scripts) para verificar que funciona. Nunca me digas que algo funciona sin haberlo ejecutado.
- Al terminar cada fase: corre black, ruff y pytest, y entrégame un resumen con: archivos creados/modificados, cómo ejecutarlo, resultados de las pruebas, decisiones importantes y problemas pendientes.
- Haz un commit de git al final de cada fase con mensaje descriptivo (formato: "fase N: descripción").
- DETENTE al finalizar la fase y espera mi aprobación antes de continuar.
- Todo el texto orientado al usuario (interfaz, explicaciones, documentación, docstrings) va en español.

Confirma que entendiste el contexto y las reglas respondiendo SOLO con un resumen de 5 líneas y la pregunta: "¿Empiezo con la Fase 1?". No escribas código todavía.