# Benchmark de búsqueda y planificación

Comparación de los algoritmos de la Fase 5 sobre escenarios de distinta dificultad. BFS, DFS y backtracking usan el límite de profundidad indicado; A*, Greedy y costo uniforme exploran sin límite. El tiempo se mide con `time.perf_counter` en la misma máquina, por lo que sirve para comparar algoritmos entre sí, no como cifra absoluta.

## facil

Meta cercana: pocas acciones y solución poco costosa.

Meta 12,000 Bs, presupuesto 6,000 Bs, stock inicial 400 u, merma inicial 12 %.

| Algoritmo | Escenario | ¿Solución? | Costo (Bs) | Nodos expandidos | Nodos generados | Profundidad | Tiempo (s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BFS | facil | True | 1400.0 | 4 | 15 | 1 | 0.000746 |
| DFS | facil | True | 3600.0 | 5 | 18 | 4 | 0.000682 |
| Backtracking | facil | True | 3600.0 | 5 | 4 | 4 | 0.000211 |
| Costo uniforme | facil | True | 1400.0 | 49 | 242 | 1 | 0.010435 |
| Greedy | facil | True | 1400.0 | 2 | 6 | 1 | 0.000362 |
| A* | facil | True | 1400.0 | 35 | 174 | 1 | 0.007219 |
| A* (h=0) | facil | True | 1400.0 | 49 | 242 | 1 | 0.010032 |

## medio

Caso de referencia con costos heterogéneos y varias combinaciones.

Meta 24,000 Bs, presupuesto 9,000 Bs, stock inicial 400 u, merma inicial 12 %.

| Algoritmo | Escenario | ¿Solución? | Costo (Bs) | Nodos expandidos | Nodos generados | Profundidad | Tiempo (s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BFS | medio | True | 7500.0 | 114 | 514 | 4 | 0.02165 |
| DFS | medio | True | 7350.0 | 135 | 329 | 6 | 0.01648 |
| Backtracking | medio | True | 7350.0 | 203 | 310 | 6 | 0.01249 |
| Costo uniforme | medio | True | 5900.0 | 880 | 3757 | 5 | 0.168269 |
| Greedy | medio | True | 7500.0 | 51 | 236 | 4 | 0.009347 |
| A* | medio | True | 5900.0 | 819 | 3538 | 5 | 0.160082 |
| A* (h=0) | medio | True | 5900.0 | 880 | 3757 | 5 | 0.167123 |

## dificil

Meta exigente que requiere combinar casi todas las palancas.

Meta 32,000 Bs, presupuesto 12,000 Bs, stock inicial 300 u, merma inicial 16 %.

| Algoritmo | Escenario | ¿Solución? | Costo (Bs) | Nodos expandidos | Nodos generados | Profundidad | Tiempo (s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BFS | dificil | False | 0.0 | 1675 | 5656 | 10 | 0.231255 |
| DFS | dificil | False | 0.0 | 1675 | 5656 | 10 | 0.233749 |
| Backtracking | dificil | False | 0.0 | 2652 | 5656 | 10 | 0.237381 |
| Costo uniforme | dificil | True | 10920.0 | 3756 | 15194 | 16 | 0.655907 |
| Greedy | dificil | True | 11740.0 | 2706 | 11071 | 14 | 0.467685 |
| A* | dificil | True | 10920.0 | 3600 | 14790 | 16 | 0.52197 |
| A* (h=0) | dificil | True | 10920.0 | 3756 | 15194 | 16 | 0.428344 |

## sin_solucion

Presupuesto insuficiente: la frontera se agota sin alcanzar la meta.

Meta 60,000 Bs, presupuesto 3,000 Bs, stock inicial 200 u, merma inicial 10 %.

| Algoritmo | Escenario | ¿Solución? | Costo (Bs) | Nodos expandidos | Nodos generados | Profundidad | Tiempo (s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BFS | sin_solucion | False | 0.0 | 138 | 343 | 6 | 0.00952 |
| DFS | sin_solucion | False | 0.0 | 138 | 343 | 6 | 0.01105 |
| Backtracking | sin_solucion | False | 0.0 | 206 | 343 | 6 | 0.00956 |
| Costo uniforme | sin_solucion | False | 0.0 | 216 | 544 | 0 | 0.017292 |
| Greedy | sin_solucion | False | 0.0 | 216 | 544 | 0 | 0.017126 |
| A* | sin_solucion | False | 0.0 | 216 | 544 | 0 | 0.018099 |
| A* (h=0) | sin_solucion | False | 0.0 | 216 | 544 | 0 | 0.017016 |

## Verificación de optimalidad

A* con la heurística admisible y consistente y costo uniforme (Dijkstra) alcanzan el mismo costo mínimo verificable en todos los escenarios con solución: 6 resultados coincidentes.

A* (h=0) usa la heurística trivial y equivale a costo uniforme; la diferencia de nodos expandidos cuantifica el aporte de la heurística del dominio.
