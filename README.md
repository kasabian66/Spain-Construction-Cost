# Costes Construcción España — Streamlit

Estimador **PRO** de CAPEX (Construcción + MEP + indirectos + soft + contingencia) con:

- **Bottom-up por capítulos** (rangos €/m² por escenario)
- **Factores** (complejidad, MEP, acabados, certificación, plazo, estado previo, indexación temporal)
- **Uso del edificio** (multiplicadores Arquitectura/MEP/Global)
- **Benchmarks top-down** (ratios €/m²) y **auto-calibración** opcional
- Exportables **CSV + PDF**
- (Opcional) **Monte Carlo** para riesgo (P50/P80/P90)

## Ejecutar
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Editar datos
- `data/cost_ranges.yaml` → rangos por capítulo, escenarios, multiplicadores por uso.
- `data/benchmarks.csv` → ratios top-down por tipología (Bajo/Medio/Alto).
- `data/sources_matrix.csv` → matriz de fuentes (enlace + fecha + notas).

## Fuentes principales (consulta 2026-02-07)
Ver `data/sources_matrix.csv`. Incluye: COA Málaga (valores estimativos), IVE (MBE), COAM (módulo colegial), Comunidad de Madrid (costes referencia), BCCA Andalucía, Ayuntamiento de Madrid (cuadro de precios), MITMA (índice costes), INE (materiales/mano de obra), C&W (fit-out).

## Aviso
Estimación paramétrica orientativa. No sustituye medición/presupuesto.

## Soft costs
- `data/soft_cost_items.csv`: desglose editable (% sobre directo).

## Contingencia
- `data/contingency_items.csv`: desglose editable (% sobre directo).

## Ciudad
- `data/cities.csv`: factor de localización por ciudad.

**Formato**: en `soft_cost_items.csv` y `contingency_items.csv` los porcentajes se expresan en % (p.ej. 4.0 = 4%).

## Aplicabilidad
En la app puedes marcar capítulos y conceptos de soft costs/contingencia como **no aplicables** (no se suman).
