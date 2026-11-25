# Guion de demostración en vivo (10 minutos)

Guion para presentar el sistema de extremo a extremo. Está pensado para
ejecutarse desde la raíz del repositorio con el entorno virtual activado y los
artefactos generados (`python -m data.generar_dataset` y
`python -m ml.entrenamiento`).

**Antes de empezar (preparación, no cuenta en los 10 minutos)**

- Terminal A: lista para `python -m core.demo`.
- Terminal B: lista para `uvicorn api.main:app --host 0.0.0.0 --port 8000`.
- Terminal C: lista para `streamlit run app/dashboard.py --server.port 8501`.
- Navegador abierto en <http://localhost:8000/docs> y <http://localhost:8501>.
- Si la conexión a Internet falla, use el modo offline del dashboard o las
  terminales A y B; el núcleo no depende de servicios externos.

---

## 0:00 - 0:45 | Presentación y Pregunta inicial

**Mostrar:** diapositiva o función única del proyecto.

**Decir:**

> "Vamos a responder tres preguntas para una sucursal: ¿cuánto venderemos la
> semana que viene?, ¿por qué no llegaremos a la meta? y ¿qué hacemos al
> respecto? El sistema no solo da el número: deja una traza de por qué lo dice."

**Puntos clave:** enfoque híbrido; tres preguntas; auditable.

---

## 0:45 - 2:00 | Caso 1: sucursal en riesgo (terminal A)

**Comando:**

```powershell
python -m core.demo
```

**Mostrar** la primera sección de salida (El Alto / pollo):

```text
El Alto/pollo: 35,740.90 Bs (67.0% de meta, confianza 0.24)
causas [operacion_critica, merma_alta, stock_critico, baja_afluencia, competencia_precios]
riesgo alto; plan reponer_stock(+400u)
```

**Decir:**

> "La predicción es de 35 740 bolivianos, solo 67 % de la meta. Fíjense en la
> confianza: 0,24. Esa confianza no se queda en el modelo: se convierte en el
> factor de certeza de los hechos que entran al razonamiento simbólico."

---

## 2:00 - 3:15 | Explicación de la predicción (SHAP)

**Mostrar** la sección 1 de la explicación:

```text
- num__ventas_media_8: +3,628 Bs
- num__meta_ventas_bs: +3,543 Bs
- num__afluencia_clientes: -3,360 Bs
```

**Decir:**

> "SHAP responde 'por qué la cifra'. Las medias móviles y la meta empujan hacia
> arriba; la afluencia, hacia abajo. Esto es IA no simbólica: aprendido de los
> datos, no escrito como regla."

**Pregunta al público:** "¿Sabe esto qué acción tomar?" (esperar: no).

---

## 3:15 - 4:45 | Reglas, certezas y traza

**Mostrar** la sección 2:

```text
operacion_critica: FC +0.880 (D10)
merma_alta:        FC +0.850 (D03)
stock_critico:     FC +0.215 (D01)
Reglas disparadas: F04, F02, R01, F08, D10, R02, A09, ...
```

**Decir:**

> "Aquí entra el sistema experto. D10 se dispara con certeza 0,88 porque los
> datos observados —cobertura y merma— tienen certeza 1,0. En cambio
> `stock_critico` hereda la duda del modelo: 0,215. El sistema distingue entre
> 'lo observé' y 'el modelo lo estima'. Cada regla queda en la traza con su CF
> de premisa y su CF propagado."

---

## 4:45 - 5:45 | Riesgo difuso y plan con A*

**Mostrar** las secciones 3 y 4:

```text
Riesgo difuso: alto / urgencia: alta
Plan: reponer_stock(+400u). Costo: 4,400.00 Bs (29 nodos expandidos).
```

**Decir:**

> "La lógica difusa modela la imprecisión: 'alto' no es un corte seco en 85 %.
> Después A* convierte el diagnóstico en restricciones y busca el plan más
> barato. No propone promoción porque el problema es operativo, no comercial."

---

## 5:45 - 6:30 | Caso 2: sucursal normal (sin acciones)

**Mostrar** la segunda sección de `core.demo`:

```text
Sopocachi/cerdo: 21,374.80 Bs (123.1% de meta)
sin causas; riesgo bajo; plan sin acciones (la meta ya se alcanza)
```

**Decir:**

> "Un sistema útil también sabe no hacer nada. No hay causas sobre el umbral y
> el plan cuesta 0 Bs. Evitamos recomendaciones espurias."

---

## 6:30 - 7:15 | Caso 3: exceso de stock (restricción)

**Mostrar** la tercera sección:

```text
Miraflores/embutidos: 17,658.76 Bs (122.9% de meta)
causa exceso_stock (CF +0.331)
plan reducir_merma(-2pp) (220.00 Bs)
```

**Decir:**

> "Aquí el diagnóstico impide traer más inventario de otra sucursal. La causa
> cambia el espacio de búsqueda: se ataca la merma, no el pedido."

---

## 7:15 - 8:30 | API y dashboard

**Terminal B:** el uvicorn ya está levantado. Abrir
<http://localhost:8000/docs> y ejecutar `GET /salud` y `POST /analisis-completo`
con:

```json
{"sucursal": "El Alto", "categoria": "pollo", "factor_meta": 1.2}
```

**Navegador:** <http://localhost:8501>. Cambiar la categoría a `embutidos` y
mostrar primero la decisión y las cuatro cifras; después abrir los apartados
«¿Por qué esta decisión?» y «Comparación y detalle técnico» para ver causas,
SHAP y comparativa Tema 1. Para una versión de 5 minutos, seguir
[`INFORME.md`](INFORME.md).

**Decir:**

> "La API expone la misma fachada; el dashboard es solo un cliente. Cada
> petición crea una memoria de trabajo nueva para no mezclar sucursales. El
> análisis queda guardado con un UUID que se puede recuperar con
> `GET /explicar/{id}`."

---

## 8:30 - 9:20 | Resultados y optimalidad (respaldo)

**Mostrar** `docs/figuras/benchmark_busqueda.png` o la tabla de
`docs/benchmark_busqueda.md`:

```text
difícil: A* 10,920 Bs / 3,600 nodos
         A* (h=0) 10,920 Bs / 3,756 nodos
         Greedy 11,740 Bs (no óptimo)
```

**Decir:**

> "A* coincide con Dijkstra en los seis escenarios con solución. La heurística
> del dominio ahorra expansiones sin perder optimalidad. Greedy es más rápido,
> pero en el caso difícil cuesta 820 bolivianos más."

Métrica ML de apoyo: **MAE 2 298,48 Bs**, **23,72 % mejor** que la línea base.

---

## 9:20 - 10:00 | Cierre y preguntas

**Decir:**

> "Resumen: predicción calibrada, diagnóstico con factores de certeza, riesgo
> difuso, plan óptimo y explicación unificada. La tabla de trazabilidad del
> informe relaciona cada tema de la materia con una función concreta. La
> limitación principal es que datos y expertos son simulados; el trabajo futuro
> es repetir la elicitación con personal real."

**Si sobra tiempo:** mostrar `docs/INFORME_TECNICO.md` §13 (trazabilidad) y
`docs/commonkads.md` §5 (las 38 reglas).

---

## Fallos frecuentes durante la demo

| Síntoma | Acción rápida |
| ------- | ------------- |
| El dashboard dice "API no disponible" | Iniciar uvicorn y recargar la página. |
| `503` en `/salud` | Ejecutar `python -m data.generar_dataset` y `python -m ml.entrenamiento`. |
| Salida con caracteres raros en Windows | Ejecutar `chcp 65001` antes de `core.demo`. |
| La demo tarda en arrancar | Es la carga del modelo y del fondo SHAP; espere unos segundos. |
| No aparece la explicación larga | Confirmar que se ejecuta `python -m core.demo` y no `expert_system.demo`. |
