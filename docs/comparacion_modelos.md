# Comparación de modelos

Ordenado por MAE sobre el conjunto de prueba (menor es mejor).

| modelo                     | mae     | rmse    | r2   | mape  | mejora_vs_baseline_pct |
| -------------------------- | ------- | ------- | ---- | ----- | ---------------------- |
| Ridge                      | 2298.48 | 3488.88 | 0.76 | 15.14 | 23.72                  |
| Gradient Boosting          | 2417.25 | 3660.97 | 0.74 | 15.79 | 19.77                  |
| Random Forest              | 2465.73 | 3587.84 | 0.75 | 16.29 | 18.16                  |
| MLPRegressor               | 2485.65 | 3650.86 | 0.74 | 16.35 | 17.50                  |
| Baseline (semana anterior) | 3013.05 | 4496.60 | 0.61 | 19.71 | 0.00                   |
