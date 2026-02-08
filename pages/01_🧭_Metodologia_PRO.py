
import streamlit as st
from pathlib import Path
import pandas as pd
from src.io import load_yaml, load_csv

st.set_page_config(page_title="Costes Construcción España - Metodología", page_icon="🧭", layout="wide")
st.title("🧭 Metodología")

data_dir = Path(__file__).parent.parent / "data"
cost = load_yaml(data_dir / "cost_ranges.yaml")
bench = load_csv(data_dir / "benchmarks.csv")
sources = load_csv(data_dir / "sources_matrix.csv")

st.markdown("""
### Cómo funciona el modelo
1) **Bottom-up por capítulos**: rangos €/m² por capítulo y escenario.
2) **Factores**: multiplicadores (complejidad, MEP, acabados, etc.) e **indexación temporal**.
3) **Uso (edificios completos)**: multiplicadores por uso separando **Arquitectura** vs **MEP**.
4) **Top-down (benchmarks)**: ratios €/m² por tipología.  
   - Opcional: **auto-calibración** para alinear el coste directo al benchmark del escenario.

> Nota: en esta versión no se realiza import automático de BC3 (BCCA/Madrid/Ayto) por compatibilidad/licencias.  
> El modelo está preparado para incorporar un parser propio si se dispone de los ficheros y permisos.
""")

st.subheader("Benchmarks")
st.dataframe(bench, use_container_width=True)

st.subheader("Fuentes")
st.dataframe(sources, use_container_width=True)

st.subheader("Estructura de datos")
st.code("""
data/
  cost_ranges.yaml        # rangos por capítulo + multiplicadores por uso
  benchmarks.csv          # ratios top-down por tipología y escenarios
  sources_matrix.csv      # trazabilidad de fuentes (enlace + fecha + notas)
""")
