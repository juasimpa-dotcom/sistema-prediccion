# Reglas reales del sistema inteligente

> Documento generado automáticamente con `python -m expert_system.exportar_reglas`.
> Fuentes: `expert_system/reglas.json`, `config.REGLAS_DIFUSAS` y la traza real
> del caso de `expert_system.demo`. No editar a mano.

## 1. Tablas de reglas

### 1.1 Reglas experto (diagnóstico, riesgo y recomendación)

| ID | Categoría (diagnóstico / riesgo / recomendación) | SI (condiciones) | ENTONCES (conclusión) | CF de la regla | Prioridad |
| --- | --- | --- | --- | --- | --- |
| D01 | diagnostico | (stock_cobertura < 0.35 Y ventas_caida_pct > 8) | causa_ventas_bajas=stock_critico | +0.90 | 80 |
| D02 | diagnostico | (stock_cobertura < 0.18 Y es_perecible es sí Y ventas_caida_pct > 5) | causa_ventas_bajas=stock_critico | +0.95 | 95 |
| D03 | diagnostico | (merma_pct > 12 Y es_perecible es sí) | causa_ventas_bajas=merma_alta | +0.85 | 78 |
| D04 | diagnostico | (merma_pct > 9 Y temperatura_media > 15) | causa_ventas_bajas=merma_alta | +0.80 | 70 |
| D05 | diagnostico | (en_promocion es no Y ventas_caida_pct > 10 Y es_feriado es no) | causa_ventas_bajas=falta_promocion | +0.78 | 68 |
| D06 | diagnostico | (afluencia_rel < 0.85 Y ventas_caida_pct > 8) | causa_ventas_bajas=baja_afluencia | +0.86 | 76 |
| D07 | diagnostico | (precio_vs_competencia > 1.08 Y en_promocion es no Y ventas_caida_pct > 6) | causa_ventas_bajas=competencia_precios | +0.82 | 74 |
| D08 | diagnostico | (temporada es baja Y ventas_caida_pct > 12 Y stock_cobertura >= 0.6) | causa_ventas_bajas=estacionalidad | +0.75 | 60 |
| D09 | diagnostico | (temporada es alta Y ventas_caida_pct > 10 Y afluencia_rel >= 0.95 Y en_promocion es no) | causa_ventas_bajas=estacionalidad | +0.70 | 58 |
| D10 | diagnostico | (stock_cobertura < 0.25 O merma_pct > 18) | causa_ventas_bajas=operacion_critica | +0.88 | 90 |
| R01 | riesgo | (cumplimiento_esperado_pct < 85) | nivel_riesgo=alto | +0.95 | 100 |
| R02 | riesgo | (cumplimiento_esperado_pct < 95 Y causa_ventas_bajas está en [stock_critico, merma_alta, operacion_critica]) | nivel_riesgo=alto | +0.88 | 92 |
| R03 | riesgo | (cumplimiento_esperado_pct < 95 Y causa_ventas_bajas está en [baja_afluencia, competencia_precios, falta_promocion]) | nivel_riesgo=alto | +0.82 | 86 |
| R04 | riesgo | (cumplimiento_esperado_pct < 100 Y cumplimiento_esperado_pct >= 90) | nivel_riesgo=medio | +0.75 | 70 |
| R05 | riesgo | (cumplimiento_esperado_pct >= 102 Y stock_cobertura >= 0.6) | nivel_riesgo=bajo | +0.85 | 68 |
| R06 | riesgo | (temporada es alta Y en_promocion es no Y cumplimiento_esperado_pct < 100) | nivel_riesgo=alto | +0.78 | 80 |
| R07 | riesgo | (merma_pct > 15 Y es_perecible es sí Y cumplimiento_esperado_pct < 100) | nivel_riesgo=alto | +0.85 | 88 |
| R08 | riesgo | (cumplimiento_esperado_pct >= 108 Y merma_pct <= 6 Y stock_cobertura >= 0.8) | nivel_riesgo=nulo | +0.90 | 72 |
| A01 | recomendacion | (nivel_riesgo es alto Y causa_ventas_bajas es stock_critico) | accion_recomendada=reponer_stock_urgente | +0.95 | 100 |
| A02 | recomendacion | (stock_cobertura < 0.5 Y nivel_riesgo es medio) | accion_recomendada=reponer_stock | +0.80 | 75 |
| A03 | recomendacion | (causa_ventas_bajas es falta_promocion Y nivel_riesgo es alto) | accion_recomendada=lanzar_promocion | +0.92 | 95 |
| A04 | recomendacion | (causa_ventas_bajas es competencia_precios Y nivel_riesgo es alto) | accion_recomendada=lanzar_promocion | +0.86 | 90 |
| A05 | recomendacion | (afluencia_rel > 0.95 Y personal_rel < 0.8 Y nivel_riesgo es alto) | accion_recomendada=reforzar_personal | +0.85 | 88 |
| A06 | recomendacion | (temporada es alta Y personal_rel < 0.85 Y es_feriado es sí) | accion_recomendada=reforzar_personal | +0.80 | 82 |
| A07 | recomendacion | (causa_ventas_bajas es merma_alta Y temporada es baja Y es_perecible es sí) | accion_recomendada=reducir_pedido_perecible | +0.90 | 93 |
| A08 | recomendacion | (merma_pct > 18 Y es_perecible es sí) | accion_recomendada=reducir_pedido_perecible | +0.88 | 91 |
| A09 | recomendacion | (stock_cobertura < 0.35 Y hay_excedente_en_otra_sucursal es sí) | accion_recomendada=reasignar_inventario | +0.87 | 89 |
| A10 | recomendacion | (causa_ventas_bajas es stock_critico Y reabastecimiento_tardia es sí) | accion_recomendada=reasignar_inventario | +0.84 | 87 |
| A11 | recomendacion | (nivel_riesgo es bajo Y stock_cobertura >= 0.6) | accion_recomendada=mantener_plan | +0.80 | 60 |
| A12 | recomendacion | (causa_ventas_bajas es competencia_precios Y nivel_riesgo es medio) | accion_recomendada=ajustar_precio | +0.78 | 65 |

### 1.2 Reglas puente difuso a simbólico

Estas reglas también viven en la base de conocimientos y traducen los
hechos graduales del motor difuso al razonamiento simbólico.

| ID | Categoría | SI (condiciones) | ENTONCES (conclusión) | CF de la regla | Prioridad |
| --- | --- | --- | --- | --- | --- |
| F01 | difuso | (nivel_riesgo_difuso es crítico) | nivel_riesgo=alto | +0.90 | 110 |
| F02 | difuso | (nivel_riesgo_difuso es alto) | nivel_riesgo=alto | +0.80 | 105 |
| F03 | difuso | (nivel_riesgo_difuso es bajo) | nivel_riesgo=bajo | +0.70 | 90 |
| F04 | difuso | (urgencia_accion es alta) | accion_recomendada=reponer_stock_urgente | +0.85 | 106 |
| F05 | difuso | (urgencia_accion es media) | accion_recomendada=lanzar_promocion | +0.70 | 95 |
| F06 | difuso | (urgencia_accion es ninguna) | accion_recomendada=mantener_plan | +0.75 | 91 |
| F07 | difuso | (merma es alta Y urgencia_accion es alta) | accion_recomendada=reducir_pedido_perecible | +0.88 | 102 |
| F08 | difuso | (nivel_stock es crítico Y urgencia_accion es alta) | accion_recomendada=reasignar_inventario | +0.82 | 99 |

### 1.3 Reglas difusas (Mamdani)

| ID | Antecedentes lingüísticos | Consecuente |
| --- | --- | --- |
| DF01 | cumplimiento_esperado = bajo Y nivel_stock = crítico | nivel_riesgo_incumplimiento = crítico Y urgencia_accion = alta |
| DF02 | cumplimiento_esperado = bajo Y merma = alta | nivel_riesgo_incumplimiento = crítico Y urgencia_accion = alta |
| DF03 | cumplimiento_esperado = bajo Y afluencia = baja | nivel_riesgo_incumplimiento = alto Y urgencia_accion = alta |
| DF04 | cumplimiento_esperado = bajo Y intensidad_promocion = ninguna | nivel_riesgo_incumplimiento = alto Y urgencia_accion = media |
| DF05 | cumplimiento_esperado = bajo Y nivel_stock = adecuado | nivel_riesgo_incumplimiento = alto Y urgencia_accion = media |
| DF06 | cumplimiento_esperado = medio Y nivel_stock = crítico | nivel_riesgo_incumplimiento = alto Y urgencia_accion = alta |
| DF07 | cumplimiento_esperado = medio Y merma = alta | nivel_riesgo_incumplimiento = alto Y urgencia_accion = media |
| DF08 | cumplimiento_esperado = medio Y afluencia = baja | nivel_riesgo_incumplimiento = alto Y urgencia_accion = media |
| DF09 | cumplimiento_esperado = medio Y intensidad_promocion = ninguna | nivel_riesgo_incumplimiento = medio Y urgencia_accion = media |
| DF10 | cumplimiento_esperado = medio Y nivel_stock = excesivo | nivel_riesgo_incumplimiento = medio Y urgencia_accion = baja |
| DF11 | cumplimiento_esperado = alto Y nivel_stock = crítico | nivel_riesgo_incumplimiento = medio Y urgencia_accion = media |
| DF12 | cumplimiento_esperado = alto Y merma = alta | nivel_riesgo_incumplimiento = medio Y urgencia_accion = baja |
| DF13 | cumplimiento_esperado = alto Y afluencia = alta | nivel_riesgo_incumplimiento = bajo Y urgencia_accion = baja |
| DF14 | cumplimiento_esperado = alto Y intensidad_promocion = fuerte | nivel_riesgo_incumplimiento = bajo Y urgencia_accion = ninguna |
| DF15 | cumplimiento_esperado = alto Y nivel_stock = adecuado | nivel_riesgo_incumplimiento = bajo Y urgencia_accion = ninguna |
| DF16 | nivel_stock = crítico Y merma = alta | nivel_riesgo_incumplimiento = crítico Y urgencia_accion = alta |
| DF17 | afluencia = baja Y intensidad_promocion = ninguna | nivel_riesgo_incumplimiento = alto Y urgencia_accion = media |
| DF18 | nivel_stock = excesivo Y merma = baja Y cumplimiento_esperado = alto | nivel_riesgo_incumplimiento = bajo Y urgencia_accion = ninguna |
| DF19 | cumplimiento_esperado = bajo Y intensidad_promocion = fuerte | nivel_riesgo_incumplimiento = alto Y urgencia_accion = media |
| DF20 | afluencia = alta Y merma = media | nivel_riesgo_incumplimiento = medio Y urgencia_accion = baja |
| DF21 | cumplimiento_esperado = medio Y afluencia = normal Y nivel_stock = adecuado | nivel_riesgo_incumplimiento = medio Y urgencia_accion = baja |
| DF22 | cumplimiento_esperado = bajo Y nivel_stock = excesivo | nivel_riesgo_incumplimiento = medio Y urgencia_accion = media |

## 2. Reglas en lenguaje natural

### 2.1 Reglas experto

- **D01 · diagnostico.** La cobertura de stock es baja y las ventas cayeron: falta de inventario _Formulación:_ `SI (stock_cobertura < 0.35 Y ventas_caida_pct > 8) ENTONCES causa_ventas_bajas=stock_critico (FC +0.90)` (prioridad 80).
- **D02 · diagnostico.** Desabastecimiento severo de un producto perecible de alta rotación _Formulación:_ `SI (stock_cobertura < 0.18 Y es_perecible es sí Y ventas_caida_pct > 5) ENTONCES causa_ventas_bajas=stock_critico (FC +0.95)` (prioridad 95).
- **D03 · diagnostico.** Merma elevada en perecibles: se pierde producto antes de venderlo _Formulación:_ `SI (merma_pct > 12 Y es_perecible es sí) ENTONCES causa_ventas_bajas=merma_alta (FC +0.85)` (prioridad 78).
- **D04 · diagnostico.** El calor incrementa la merma y deja menos unidades vendibles _Formulación:_ `SI (merma_pct > 9 Y temperatura_media > 15) ENTONCES causa_ventas_bajas=merma_alta (FC +0.80)` (prioridad 70).
- **D05 · diagnostico.** Sin promoción ni feriado, la caída de ventas apunta a falta de estímulo comercial _Formulación:_ `SI (en_promocion es no Y ventas_caida_pct > 10 Y es_feriado es no) ENTONCES causa_ventas_bajas=falta_promocion (FC +0.78)` (prioridad 68).
- **D06 · diagnostico.** La afluencia está por debajo del promedio de la sucursal _Formulación:_ `SI (afluencia_rel < 0.85 Y ventas_caida_pct > 8) ENTONCES causa_ventas_bajas=baja_afluencia (FC +0.86)` (prioridad 76).
- **D07 · diagnostico.** Precio por encima de la competencia sin promoción explica la pérdida de clientes _Formulación:_ `SI (precio_vs_competencia > 1.08 Y en_promocion es no Y ventas_caida_pct > 6) ENTONCES causa_ventas_bajas=competencia_precios (FC +0.82)` (prioridad 74).
- **D08 · diagnostico.** Temporada baja con inventario suficiente: caída estacional de la demanda _Formulación:_ `SI (temporada es baja Y ventas_caida_pct > 12 Y stock_cobertura >= 0.6) ENTONCES causa_ventas_bajas=estacionalidad (FC +0.75)` (prioridad 60).
- **D09 · diagnostico.** En temporada alta, con afluencia normal y sin promoción, el cliente no compra _Formulación:_ `SI (temporada es alta Y ventas_caida_pct > 10 Y afluencia_rel >= 0.95 Y en_promocion es no) ENTONCES causa_ventas_bajas=estacionalidad (FC +0.70)` (prioridad 58).
- **D10 · diagnostico.** Desabastecimiento extremo o merma descontrolada: operación crítica _Formulación:_ `SI (stock_cobertura < 0.25 O merma_pct > 18) ENTONCES causa_ventas_bajas=operacion_critica (FC +0.88)` (prioridad 90).
- **R01 · riesgo.** Cumplimiento esperado muy por debajo del 85 %: riesgo alto _Formulación:_ `SI (cumplimiento_esperado_pct < 85) ENTONCES nivel_riesgo=alto (FC +0.95)` (prioridad 100).
- **R02 · riesgo.** Una causa operativa con cumplimiento menor al 95 % agrava el riesgo _Formulación:_ `SI (cumplimiento_esperado_pct < 95 Y causa_ventas_bajas está en [stock_critico, merma_alta, operacion_critica]) ENTONCES nivel_riesgo=alto (FC +0.88)` (prioridad 92).
- **R03 · riesgo.** Una causa de demanda o competencia también amenaza la meta _Formulación:_ `SI (cumplimiento_esperado_pct < 95 Y causa_ventas_bajas está en [baja_afluencia, competencia_precios, falta_promocion]) ENTONCES nivel_riesgo=alto (FC +0.82)` (prioridad 86).
- **R04 · riesgo.** Cumplimiento entre 90 % y 100 %: riesgo medio _Formulación:_ `SI (cumplimiento_esperado_pct < 100 Y cumplimiento_esperado_pct >= 90) ENTONCES nivel_riesgo=medio (FC +0.75)` (prioridad 70).
- **R05 · riesgo.** Cumplimiento adecuado con stock sano: riesgo bajo _Formulación:_ `SI (cumplimiento_esperado_pct >= 102 Y stock_cobertura >= 0.6) ENTONCES nivel_riesgo=bajo (FC +0.85)` (prioridad 68).
- **R06 · riesgo.** Temporada alta sin promoción y meta ajustada: riesgo alto _Formulación:_ `SI (temporada es alta Y en_promocion es no Y cumplimiento_esperado_pct < 100) ENTONCES nivel_riesgo=alto (FC +0.78)` (prioridad 80).
- **R07 · riesgo.** Merma extrema en perecibles con meta en riesgo _Formulación:_ `SI (merma_pct > 15 Y es_perecible es sí Y cumplimiento_esperado_pct < 100) ENTONCES nivel_riesgo=alto (FC +0.85)` (prioridad 88).
- **R08 · riesgo.** Meta superada, merma controlada y stock suficiente: sin riesgo _Formulación:_ `SI (cumplimiento_esperado_pct >= 108 Y merma_pct <= 6 Y stock_cobertura >= 0.8) ENTONCES nivel_riesgo=nulo (FC +0.90)` (prioridad 72).
- **A01 · recomendacion.** Reposición urgente ante desabastecimiento y riesgo alto _Formulación:_ `SI (nivel_riesgo es alto Y causa_ventas_bajas es stock_critico) ENTONCES accion_recomendada=reponer_stock_urgente (FC +0.95)` (prioridad 100).
- **A02 · recomendacion.** Reponer inventario antes de que la cobertura crítica se agrave _Formulación:_ `SI (stock_cobertura < 0.5 Y nivel_riesgo es medio) ENTONCES accion_recomendada=reponer_stock (FC +0.80)` (prioridad 75).
- **A03 · recomendacion.** Lanzar promoción cuando no hubo estímulo comercial y la meta está en riesgo _Formulación:_ `SI (causa_ventas_bajas es falta_promocion Y nivel_riesgo es alto) ENTONCES accion_recomendada=lanzar_promocion (FC +0.92)` (prioridad 95).
- **A04 · recomendacion.** Promoción defensiva frente a precios de la competencia _Formulación:_ `SI (causa_ventas_bajas es competencia_precios Y nivel_riesgo es alto) ENTONCES accion_recomendada=lanzar_promocion (FC +0.86)` (prioridad 90).
- **A05 · recomendacion.** Reforzar personal cuando hay mucha afluencia y la dotación es baja _Formulación:_ `SI (afluencia_rel > 0.95 Y personal_rel < 0.8 Y nivel_riesgo es alto) ENTONCES accion_recomendada=reforzar_personal (FC +0.85)` (prioridad 88).
- **A06 · recomendacion.** Reforzar turnos en temporada alta con feriado y personal justo _Formulación:_ `SI (temporada es alta Y personal_rel < 0.85 Y es_feriado es sí) ENTONCES accion_recomendada=reforzar_personal (FC +0.80)` (prioridad 82).
- **A07 · recomendacion.** Reducir el pedido de perecibles si hay merma alta en temporada baja _Formulación:_ `SI (causa_ventas_bajas es merma_alta Y temporada es baja Y es_perecible es sí) ENTONCES accion_recomendada=reducir_pedido_perecible (FC +0.90)` (prioridad 93).
- **A08 · recomendacion.** Merma extrema: recortar de inmediato el pedido de perecibles _Formulación:_ `SI (merma_pct > 18 Y es_perecible es sí) ENTONCES accion_recomendada=reducir_pedido_perecible (FC +0.88)` (prioridad 91).
- **A09 · recomendacion.** Reasignar inventario desde otra sucursal con excedentes _Formulación:_ `SI (stock_cobertura < 0.35 Y hay_excedente_en_otra_sucursal es sí) ENTONCES accion_recomendada=reasignar_inventario (FC +0.87)` (prioridad 89).
- **A10 · recomendacion.** Si el reabastecimiento es lento, traer stock de otra sucursal _Formulación:_ `SI (causa_ventas_bajas es stock_critico Y reabastecimiento_tardia es sí) ENTONCES accion_recomendada=reasignar_inventario (FC +0.84)` (prioridad 87).
- **A11 · recomendacion.** Con riesgo bajo y stock suficiente, mantener el plan de compras _Formulación:_ `SI (nivel_riesgo es bajo Y stock_cobertura >= 0.6) ENTONCES accion_recomendada=mantener_plan (FC +0.80)` (prioridad 60).
- **A12 · recomendacion.** Ajustar precios ante competencia con riesgo controlado _Formulación:_ `SI (causa_ventas_bajas es competencia_precios Y nivel_riesgo es medio) ENTONCES accion_recomendada=ajustar_precio (FC +0.78)` (prioridad 65).
- **F01 · difuso.** Riesgo difuso crítico: escalar a riesgo alto para el motor crisp _Formulación:_ `SI (nivel_riesgo_difuso es crítico) ENTONCES nivel_riesgo=alto (FC +0.90)` (prioridad 110).
- **F02 · difuso.** Riesgo difuso alto: confirmar riesgo alto con certeza moderada _Formulación:_ `SI (nivel_riesgo_difuso es alto) ENTONCES nivel_riesgo=alto (FC +0.80)` (prioridad 105).
- **F03 · difuso.** Riesgo difuso bajo: respaldar un riesgo bajo _Formulación:_ `SI (nivel_riesgo_difuso es bajo) ENTONCES nivel_riesgo=bajo (FC +0.70)` (prioridad 90).
- **F04 · difuso.** Urgencia difusa alta: reponer stock de inmediato _Formulación:_ `SI (urgencia_accion es alta) ENTONCES accion_recomendada=reponer_stock_urgente (FC +0.85)` (prioridad 106).
- **F05 · difuso.** Urgencia difusa media: activar una promoción correctiva _Formulación:_ `SI (urgencia_accion es media) ENTONCES accion_recomendada=lanzar_promocion (FC +0.70)` (prioridad 95).
- **F06 · difuso.** Urgencia difusa nula: mantener el plan de compras _Formulación:_ `SI (urgencia_accion es ninguna) ENTONCES accion_recomendada=mantener_plan (FC +0.75)` (prioridad 91).
- **F07 · difuso.** Merma fuzzificada alta con urgencia máxima: recortar pedido perecible _Formulación:_ `SI (merma es alta Y urgencia_accion es alta) ENTONCES accion_recomendada=reducir_pedido_perecible (FC +0.88)` (prioridad 102).
- **F08 · difuso.** Stock fuzzificado crítico con urgencia máxima: reasignar inventario _Formulación:_ `SI (nivel_stock es crítico Y urgencia_accion es alta) ENTONCES accion_recomendada=reasignar_inventario (FC +0.82)` (prioridad 99).

### 2.2 Reglas difusas

- **DF01.** Cumplimiento bajo con stock crítico: riesgo crítico y acción inmediata SI cumplimiento_esperado = bajo Y nivel_stock = crítico; ENTONCES nivel_riesgo_incumplimiento = crítico Y urgencia_accion = alta.
- **DF02.** Cumplimiento bajo con merma alta agrava el riesgo SI cumplimiento_esperado = bajo Y merma = alta; ENTONCES nivel_riesgo_incumplimiento = crítico Y urgencia_accion = alta.
- **DF03.** Cumplimiento bajo y poca afluencia: riesgo alto SI cumplimiento_esperado = bajo Y afluencia = baja; ENTONCES nivel_riesgo_incumplimiento = alto Y urgencia_accion = alta.
- **DF04.** Cumplimiento bajo sin promoción: riesgo alto SI cumplimiento_esperado = bajo Y intensidad_promocion = ninguna; ENTONCES nivel_riesgo_incumplimiento = alto Y urgencia_accion = media.
- **DF05.** Cumplimiento bajo con stock adecuado: riesgo alto SI cumplimiento_esperado = bajo Y nivel_stock = adecuado; ENTONCES nivel_riesgo_incumplimiento = alto Y urgencia_accion = media.
- **DF06.** Cumplimiento medio con stock crítico: riesgo alto SI cumplimiento_esperado = medio Y nivel_stock = crítico; ENTONCES nivel_riesgo_incumplimiento = alto Y urgencia_accion = alta.
- **DF07.** Cumplimiento medio con merma alta: riesgo alto SI cumplimiento_esperado = medio Y merma = alta; ENTONCES nivel_riesgo_incumplimiento = alto Y urgencia_accion = media.
- **DF08.** Cumplimiento medio con afluencia baja: riesgo alto SI cumplimiento_esperado = medio Y afluencia = baja; ENTONCES nivel_riesgo_incumplimiento = alto Y urgencia_accion = media.
- **DF09.** Cumplimiento medio sin promoción: riesgo medio SI cumplimiento_esperado = medio Y intensidad_promocion = ninguna; ENTONCES nivel_riesgo_incumplimiento = medio Y urgencia_accion = media.
- **DF10.** Cumplimiento medio con excedente de stock: riesgo medio SI cumplimiento_esperado = medio Y nivel_stock = excesivo; ENTONCES nivel_riesgo_incumplimiento = medio Y urgencia_accion = baja.
- **DF11.** Cumplimiento alto pero stock crítico: riesgo medio SI cumplimiento_esperado = alto Y nivel_stock = crítico; ENTONCES nivel_riesgo_incumplimiento = medio Y urgencia_accion = media.
- **DF12.** Cumplimiento alto con merma alta: riesgo medio SI cumplimiento_esperado = alto Y merma = alta; ENTONCES nivel_riesgo_incumplimiento = medio Y urgencia_accion = baja.
- **DF13.** Cumplimiento alto y afluencia alta: riesgo bajo SI cumplimiento_esperado = alto Y afluencia = alta; ENTONCES nivel_riesgo_incumplimiento = bajo Y urgencia_accion = baja.
- **DF14.** Cumplimiento alto con promoción fuerte: riesgo bajo SI cumplimiento_esperado = alto Y intensidad_promocion = fuerte; ENTONCES nivel_riesgo_incumplimiento = bajo Y urgencia_accion = ninguna.
- **DF15.** Cumplimiento alto con stock adecuado: riesgo bajo SI cumplimiento_esperado = alto Y nivel_stock = adecuado; ENTONCES nivel_riesgo_incumplimiento = bajo Y urgencia_accion = ninguna.
- **DF16.** Stock crítico y merma alta: riesgo crítico SI nivel_stock = crítico Y merma = alta; ENTONCES nivel_riesgo_incumplimiento = crítico Y urgencia_accion = alta.
- **DF17.** Afluencia baja sin promoción: riesgo alto SI afluencia = baja Y intensidad_promocion = ninguna; ENTONCES nivel_riesgo_incumplimiento = alto Y urgencia_accion = media.
- **DF18.** Escenario ideal: riesgo bajo y sin urgencia SI nivel_stock = excesivo Y merma = baja Y cumplimiento_esperado = alto; ENTONCES nivel_riesgo_incumplimiento = bajo Y urgencia_accion = ninguna.
- **DF19.** Cumplimiento bajo con promoción fuerte: riesgo alto atenuado SI cumplimiento_esperado = bajo Y intensidad_promocion = fuerte; ENTONCES nivel_riesgo_incumplimiento = alto Y urgencia_accion = media.
- **DF20.** Afluencia alta con merma media: riesgo medio SI afluencia = alta Y merma = media; ENTONCES nivel_riesgo_incumplimiento = medio Y urgencia_accion = baja.
- **DF21.** Cumplimiento medio con operación estable: riesgo medio SI cumplimiento_esperado = medio Y afluencia = normal Y nivel_stock = adecuado; ENTONCES nivel_riesgo_incumplimiento = medio Y urgencia_accion = baja.
- **DF22.** Cumplimiento bajo con sobrestock: riesgo medio SI cumplimiento_esperado = bajo Y nivel_stock = excesivo; ENTONCES nivel_riesgo_incumplimiento = medio Y urgencia_accion = media.

## 3. Resumen de reglas

| Categoría | Cantidad |
| --- | --- |
| diagnostico | 10 |
| riesgo | 8 |
| recomendacion | 12 |
| difuso | 8 |
| Reglas difusas (`config.py`) | 22 |
| **Total exportado** | **60** |

## 4. Ejemplo de traza con caso concreto

Caso `Sucursal El Alto / pollo` de `expert_system/demo.py`. Los datos se
inyectan con certeza 1.0 y el encadenamiento hacia adelante usa el umbral
declarado en `config.UMBRAL_CF_EXPERTO`.

### 4.1 Hechos del caso

| Hecho observado | Valor |
| --- | --- |
| ventas_caida_pct | 18.0 |
| stock_cobertura | 0.12 |
| merma_pct | 14.5 |
| temperatura_media | 17.0 |
| es_perecible | sí |
| en_promocion | no |
| es_feriado | no |
| afluencia_rel | 0.72 |
| precio_vs_competencia | 1.12 |
| temporada | alta |
| cumplimiento_esperado_pct | 82.0 |
| descuento_pct | 0.0 |
| personal_rel | 0.72 |
| hay_excedente_en_otra_sucursal | sí |
| reabastecimiento_tardia | sí |

### 4.2 Reglas disparadas, en orden

El CF de conclusión de cada fila es `CF premisa × FC regla`. El CF final
puede cambiar después al combinarse varias reglas con MYCIN.

| Orden | Regla | Categoría | Premisa | CF premisa | FC regla | CF conclusión | Conclusión |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | R01 | riesgo | (cumplimiento_esperado_pct < 85) | +1.00 | +0.95 | +0.95 | nivel_riesgo=alto |
| 2 | D02 | diagnostico | (stock_cobertura < 0.18 Y es_perecible es sí Y ventas_caida_pct > 5) | +1.00 | +0.95 | +0.95 | causa_ventas_bajas=stock_critico |
| 3 | A01 | recomendacion | (nivel_riesgo es alto Y causa_ventas_bajas es stock_critico) | +0.95 | +0.95 | +0.90 | accion_recomendada=reponer_stock_urgente |
| 4 | R02 | riesgo | (cumplimiento_esperado_pct < 95 Y causa_ventas_bajas está en [stock_critico, merma_alta, operacion_critica]) | +0.95 | +0.88 | +0.84 | nivel_riesgo=alto |
| 5 | D10 | diagnostico | (stock_cobertura < 0.25 O merma_pct > 18) | +1.00 | +0.88 | +0.88 | causa_ventas_bajas=operacion_critica |
| 6 | A09 | recomendacion | (stock_cobertura < 0.35 Y hay_excedente_en_otra_sucursal es sí) | +1.00 | +0.87 | +0.87 | accion_recomendada=reasignar_inventario |
| 7 | A10 | recomendacion | (causa_ventas_bajas es stock_critico Y reabastecimiento_tardia es sí) | +0.95 | +0.84 | +0.80 | accion_recomendada=reasignar_inventario |
| 8 | R06 | riesgo | (temporada es alta Y en_promocion es no Y cumplimiento_esperado_pct < 100) | +1.00 | +0.78 | +0.78 | nivel_riesgo=alto |
| 9 | D01 | diagnostico | (stock_cobertura < 0.35 Y ventas_caida_pct > 8) | +1.00 | +0.90 | +0.90 | causa_ventas_bajas=stock_critico |
| 10 | D03 | diagnostico | (merma_pct > 12 Y es_perecible es sí) | +1.00 | +0.85 | +0.85 | causa_ventas_bajas=merma_alta |
| 11 | D06 | diagnostico | (afluencia_rel < 0.85 Y ventas_caida_pct > 8) | +1.00 | +0.86 | +0.86 | causa_ventas_bajas=baja_afluencia |
| 12 | D07 | diagnostico | (precio_vs_competencia > 1.08 Y en_promocion es no Y ventas_caida_pct > 6) | +1.00 | +0.82 | +0.82 | causa_ventas_bajas=competencia_precios |
| 13 | D04 | diagnostico | (merma_pct > 9 Y temperatura_media > 15) | +1.00 | +0.80 | +0.80 | causa_ventas_bajas=merma_alta |
| 14 | D05 | diagnostico | (en_promocion es no Y ventas_caida_pct > 10 Y es_feriado es no) | +1.00 | +0.78 | +0.78 | causa_ventas_bajas=falta_promocion |

Se dispararon **14 reglas** en total.

### 4.3 Certeza final acumulada

| Atributo | Conclusión | CF final |
| --- | --- | --- |
| causa_ventas_bajas | stock_critico | +0.99 |
| nivel_riesgo | alto | +1.00 |
| accion_recomendada | reasignar_inventario | +0.97 |
