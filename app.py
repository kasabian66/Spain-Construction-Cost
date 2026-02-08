
import streamlit as st
import pandas as pd
import numpy as np
import math
from pathlib import Path
import tempfile

from src.io import load_yaml, load_csv
from src.calculations import Factors, estimate_module, totals_table, SCENARIOS, SCENARIO_LABELS
from src.pdf_report import export_pdf, ReportInputs

st.set_page_config(page_title="Costes Construcción España", page_icon="🏗️", layout="wide")

DATA_DIR = Path(__file__).parent / "data"
cost_data = load_yaml(DATA_DIR / "cost_ranges.yaml")
sources_df = load_csv(DATA_DIR / "sources_matrix.csv")
bench_df = load_csv(DATA_DIR / "benchmarks.csv")
cities_df = load_csv(DATA_DIR / "cities.csv")
soft_df = load_csv(DATA_DIR / "soft_cost_items.csv")
cont_df = load_csv(DATA_DIR / "contingency_items.csv")

st.title("🏗️ Costes Construcción España")
st.caption("Modelo paramétrico: bottom-up por capítulos + benchmarks top-down + calibración opcional + exportables.")

with st.expander("### Ayuda: Benchmark, calibración y riesgo"):
    st.write("""Mostrar benchmark (top-down): enseña un ratio €/m² de referencia (una “regla rápida”) para comparar si tu resultado está en orden de magnitud.

Auto-calibrar al benchmark: si lo activas, la app escala el coste directo por capítulos para que el total directo cuadre con ese ratio €/m² del escenario elegido. Útil cuando confías en ese benchmark (por ejemplo, una referencia de visado o un ratio contrastado), pero ojo: “fuerza” el resultado.

Monte Carlo (riesgo): hace muchas simulaciones para estimar incertidumbre y te da P50/P80/P90 (coste “probable”, “con colchón”, etc.).""")


# Sidebar: module
module_options = [
 ("obra_nueva_edificio","Nueva edificación (edificio completo)"),
 ("reposicionamiento_edificio","Reposicionamiento (rehabilitación integral)"),
 ("reforma_piso","Reforma de piso (vivienda)"),
 ("reforma_local","Reforma de local"),
 ("fitout_oficinas","Fit-out de oficinas (interior)"),
 ("fitout_local_por_uso","Fit-out de local por uso"),
]
module_key = st.sidebar.selectbox("Módulo", options=[k for k,_ in module_options], format_func=lambda k: dict(module_options)[k])
module_def = cost_data["modules"][module_key]

st.subheader(module_def["label"])
st.caption(module_def.get("measurement",""))

# Area inputs
col1, col2, col_city, col3, col4 = st.columns([1.2,1.0,1.0,1.1,1.5])

with col1:
    if module_key in ("obra_nueva_edificio","reposicionamiento_edificio"):
        m2_above = st.number_input("Sobre rasante (m² construidos)", min_value=0.0, value=5000.0, step=50.0)
        m2_below = st.number_input("Bajo rasante (m² construidos)", min_value=0.0, value=1000.0, step=50.0)
        area_ref = m2_above + m2_below
        area_label = "m² construidos"
    else:
        area_type = st.selectbox("Tipo de superficie", ["m² útiles","m² construidos"])
        m2_above = st.number_input(f"Superficie ({area_type})", min_value=0.0, value=200.0, step=5.0)
        m2_below = 0.0
        area_ref = m2_above
        area_label = area_type

with col2:
    scenario_pick = st.multiselect("Escenarios", SCENARIOS, default=SCENARIOS, format_func=lambda s: SCENARIO_LABELS[s])
    include_optional = st.checkbox("Incluir capítulos opcionales", value=True)


with col_city:
    st.markdown("**Ciudad**")
    city = st.selectbox("Ciudad", options=list(cities_df["city"].values), index=0)
    if city == "Custom":
        city_factor = st.slider("Factor localización (manual)", 0.90, 1.20, 1.0, 0.01)
    else:
        city_factor = float(cities_df.loc[cities_df["city"]==city, "location_factor"].iloc[0])
    st.caption(f"Factor localización: {city_factor:.2f}")

with col3:
    st.markdown("**Benchmark / calibración**")
    st.caption("Benchmark = ratio €/m² de referencia. Auto-calibrar ajusta el coste directo por capítulos para que coincida con ese ratio (por escenario).")
    use_benchmark = st.checkbox("Mostrar benchmark (top-down)", value=True)
    auto_calib = st.checkbox("Auto-calibrar al benchmark", value=False, help="Escala el coste directo por capítulos para coincidir con el benchmark del escenario.")
    st.caption("Consejo: usa auto-calibración cuando tengas una referencia fiable (p.ej. visado/ratio).")

with col4:
    st.markdown("**Modo**")
    st.caption("Monte Carlo simula incertidumbre para estimar P50/P80/P90 del coste total (riesgo).")
    show_montecarlo = st.checkbox("Monte Carlo (riesgo)", value=False)
    n_mc = st.number_input("Simulaciones", min_value=200, max_value=20000, value=2000, step=200, disabled=not show_montecarlo)

if area_ref <= 0:
    st.warning("Introduce una superficie > 0.")
    st.stop()

# Options
options = {}
building_use_label = ""
bench_row = None

if module_key in ("obra_nueva_edificio","reposicionamiento_edificio"):
    uses = module_def.get("use_profiles",{})
    use_key = st.selectbox("Uso del edificio", options=list(uses.keys()), format_func=lambda k: uses[k].get("label",k))
    options["building_use"] = use_key
    building_use_label = uses.get(use_key,{}).get("label",use_key)
    st.caption(f"Multiplicadores por uso → Arquitectura {uses[use_key]['arch']:.2f} | MEP {uses[use_key]['mep']:.2f} | Global {uses[use_key]['overall']:.2f}")

    if use_benchmark:
        # pick benchmark row by key
        b = bench_df[bench_df["key"]==use_key]
        if not b.empty:
            bench_row = b.iloc[0].to_dict()
            st.info(f"Benchmark {bench_row['label']}: Bajo {bench_row['pem_low']:.0f} | Medio {bench_row['pem_mid']:.0f} | Alto {bench_row['pem_high']:.0f} {bench_row['unit']}")
        else:
            st.warning("No hay benchmark específico para este uso en data/benchmarks.csv. Puedes añadirlo.")

# Module-specific options
if module_key == "reposicionamiento_edificio":
    options["intervention_level"] = st.selectbox("Grado de intervención", ["ligero","medio","intensivo"], index=1)
if module_key == "reforma_piso":
    options["reform_level"] = st.selectbox("Nivel de reforma", ["parcial","integral","integral_plus"], index=1)
if module_key == "reforma_local":
    options["intervention_level"] = st.selectbox("Nivel de intervención", ["ligera","media","intensiva"], index=1)
if module_key == "fitout_oficinas":
    options["include_furniture"] = st.checkbox("Incluir mobiliario (opcional)", value=False)
    if use_benchmark:
        b = bench_df[bench_df["key"]=="fitout_oficinas"]
        if not b.empty:
            bench_row = b.iloc[0].to_dict()
            key_bench = "fitout_oficinas_barcelona" if (("city" in locals()) and (city == "Barcelona")) else "fitout_oficinas"
            b = bench_df[bench_df["key"]==key_bench]
            if not b.empty:
                bench_row = b.iloc[0].to_dict()
                st.info(f"Benchmark fit-out oficinas: Bajo {float(bench_row['pem_low']):.0f} | Medio {float(bench_row['pem_mid']):.0f} | Alto {float(bench_row['pem_high']):.0f} {bench_row['unit']}")
if module_key == "fitout_local_por_uso":
    options["use"] = st.selectbox("Uso del local", ["retail","restauracion","fitness","clinica","otros"], index=0)

# Factors sliders
st.markdown("### Factores (multiplicadores)")
f1,f2,f3,f4,f5 = st.columns(5)
with f1:
    complejidad = st.slider("Complejidad", 0.85, 1.25, 1.0, 0.01)
    altura = st.slider("Altura", 0.95, 1.20, 1.0, 0.01)
with f2:
    localizacion_adj = st.slider("Localización (ajuste adicional)", 0.90, 1.20, 1.0, 0.01)
    localizacion = float(localizacion_adj * city_factor)
    indexacion = st.slider("Indexación temporal", 0.85, 1.35, 1.0, 0.01, help="Factor manual (MITMA/INE).")
    st.caption(f"Localización efectiva: {localizacion:.2f}")
with f3:
    intensidad_mep = st.slider("Intensidad MEP", 0.90, 1.30, 1.0, 0.01)
    acabados = st.slider("Nivel acabados", 0.90, 1.30, 1.0, 0.01)
with f4:
    certificacion = st.slider("Certificación/ESG", 1.00, 1.12, 1.0, 0.01)
    plazo = st.slider("Plazo", 0.95, 1.15, 1.0, 0.01)
with f5:
    estado_previo = st.slider("Estado previo", 0.85, 1.35, 1.0, 0.01)


st.markdown("### Soft costs (desglose)")
with st.expander("Editar desglose de soft costs (sobre coste directo)"):
    st.caption("Se aplican como % sobre coste directo. Marca 'aplica' para incluir/excluir conceptos.")
    _soft_df = soft_df.copy()
    if "aplica" not in _soft_df.columns:
        _soft_df["aplica"] = True

    soft_edit = st.data_editor(
        _soft_df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "aplica": st.column_config.CheckboxColumn("Aplica", help="Incluir este concepto en el total"),
            "concepto": st.column_config.TextColumn("Concepto"),
            "pct_sobre_directo": st.column_config.NumberColumn("% sobre directo", format="%.2f %%", min_value=0.0, step=0.10),
        },
    )
    soft_items_pct = float(soft_edit.loc[soft_edit["aplica"]==True, "pct_sobre_directo"].sum())
    soft_items_frac = soft_items_pct/100.0
    st.write(f"**Soft costs total (suma aplicables): {soft_items_pct:.2f}% del directo**")

st.markdown("### Contingencia (desglose)")
with st.expander("Editar desglose de contingencia (sobre coste directo)"):
    st.caption("Se aplica como % sobre coste directo. Marca 'aplica' para incluir/excluir conceptos.")
    _cont_df = cont_df.copy()
    if "aplica" not in _cont_df.columns:
        _cont_df["aplica"] = True

    cont_edit = st.data_editor(
        _cont_df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "aplica": st.column_config.CheckboxColumn("Aplica", help="Incluir este concepto en el total"),
            "concepto": st.column_config.TextColumn("Concepto"),
            "pct_sobre_directo": st.column_config.NumberColumn("% sobre directo", format="%.2f %%", min_value=0.0, step=0.10),
        },
    )
    cont_items_pct = float(cont_edit.loc[cont_edit["aplica"]==True, "pct_sobre_directo"].sum())
    cont_items_frac = cont_items_pct/100.0
    st.write(f"**Contingencia total (suma aplicables): {cont_items_pct:.2f}% del directo**")

factors = Factors(

    complejidad=complejidad, altura=altura, localizacion=localizacion,
    intensidad_mep=intensidad_mep, acabados=acabados, certificacion=certificacion,
    plazo=plazo, estado_previo=estado_previo, indexacion_temporal=indexacion
)

# Compute
totals_by_scenario, breakdowns = {}, {}
# Soft costs + contingencia overrides
options['soft_items_pct'] = float(soft_items_frac) if 'soft_items_frac' in globals() else float(soft_df['pct_sobre_directo'].sum())/100.0
options['cont_items_pct'] = float(cont_items_frac) if 'cont_items_frac' in globals() else float(cont_df['pct_sobre_directo'].sum())/100.0
for sc in scenario_pick:
    df, totals = estimate_module(
        cost_data, module_key, sc,
        float(m2_above), float(m2_below),
        factors, options=options,
        benchmark_row=bench_row,
        auto_calibrate_to_benchmark=auto_calib
    )
    if not include_optional:
        df = df[df["basis"]!="optional"].copy()
        direct = float(df["cost_direct"].sum())
        defaults = module_def["defaults"]
        totals = {
            "direct": direct,
            "indirects": direct * float(defaults["indirects_pct"][sc]),
            "gg_bi": direct * float(defaults["gg_bi_pct"]),
            "soft_costs": direct * float(defaults["soft_costs_pct"][sc]),
            "contingency": direct * float(defaults["contingency_pct"][sc]),
        }
        totals["total"] = sum(totals.values())
        totals["calibration"] = 1.0
    totals_by_scenario[sc] = totals
    breakdowns[sc] = df


st.markdown("### Capítulos (aplicabilidad)")
st.caption("Marca qué capítulos aplican. Se aplica a todos los escenarios.")
chap_base = pd.DataFrame(
    [{"aplica": True, "chapter_key": c["key"], "capitulo": c["label"], "basis": c.get("basis","base")}
     for c in module_def["chapters"]]
)
chap_edit = st.data_editor(
    chap_base,
    use_container_width=True,
    hide_index=True,
    column_config={
        "aplica": st.column_config.CheckboxColumn("Aplica"),
        "capitulo": st.column_config.TextColumn("Capítulo", disabled=True),
        "basis": st.column_config.TextColumn("Tipo", disabled=True),
        "chapter_key": st.column_config.TextColumn("Key", disabled=True),
    },
)
chap_included = set(chap_edit.loc[chap_edit["aplica"]==True, "chapter_key"].tolist())

# Recalcular totales con capítulos seleccionados
for sc in scenario_pick:
    df = breakdowns[sc].copy()
    df = df[df["chapter_key"].isin(chap_included)].copy()
    breakdowns[sc] = df
    direct = float(df["cost_direct"].sum())
    defaults = module_def["defaults"]
    indirects = direct * float(defaults["indirects_pct"][sc])
    gg_bi = direct * float(defaults["gg_bi_pct"])
    soft = direct * float(options.get("soft_items_pct", defaults["soft_costs_pct"][sc]))
    cont = direct * float(options.get("cont_items_pct", defaults["contingency_pct"][sc]))
    totals_by_scenario[sc].update({
        "direct": direct,
        "indirects": indirects,
        "gg_bi": gg_bi,
        "soft_costs": soft,
        "contingency": cont,
        "total": direct + indirects + gg_bi + soft + cont,
    })

st.markdown("### Resultados")
t_tab = totals_table(totals_by_scenario, float(area_ref))
st.dataframe(t_tab.style.format({
    "total_eur":"{:,.0f} €","eur_m2":"{:,.0f} €/m²","direct_eur":"{:,.0f} €",
    "indirects_eur":"{:,.0f} €","gg_bi_eur":"{:,.0f} €","soft_costs_eur":"{:,.0f} €",
    "contingency_eur":"{:,.0f} €","calib_factor":"{:.3f}"
}), use_container_width=True)

# Breakdown tabs
st.markdown("### Desglose por capítulos (directo)")
tabs = st.tabs([SCENARIO_LABELS[s] for s in scenario_pick]) if scenario_pick else []
for i, sc in enumerate(scenario_pick):
    with tabs[i]:
        df = breakdowns[sc].copy()
        df2 = df[["capitulo","cost_direct"]].groupby("capitulo", as_index=False).sum().sort_values("cost_direct", ascending=False)
        st.dataframe(df2.style.format({"cost_direct":"{:,.0f} €"}), use_container_width=True)
        st.bar_chart(df2.set_index("capitulo")["cost_direct"])

# Tornado sensitivity (simple): show contribution of each factor
st.markdown("### Sensibilidad (drivers)")
driver = pd.DataFrame([
    ["Complejidad", complejidad],
    ["Altura", altura],
    ["Localización", localizacion],
    ["Indexación temporal", indexacion],
    ["Intensidad MEP", intensidad_mep],
    ["Nivel acabados", acabados],
    ["Certificación/ESG", certificacion],
    ["Plazo", plazo],
    ["Estado previo", estado_previo],
], columns=["driver","factor"])
driver["impact_vs_1"] = (driver["factor"] - 1.0).abs()
driver = driver.sort_values("impact_vs_1", ascending=False)
st.dataframe(driver[["driver","factor"]].style.format({"factor":"{:.3f}"}), use_container_width=True)

# Monte Carlo risk (lognormal around current totals of mid scenario)
if show_montecarlo and "mid" in totals_by_scenario:
    st.markdown("### Riesgo (Monte Carlo)")
    base_total = totals_by_scenario["mid"]["total"]
    # sigma based on contingency + complexity (heuristic)
    sigma = min(0.35, 0.12 + 0.10*(complejidad-1.0) + 0.15*(estado_previo-1.0))
    mu = math.log(base_total) - 0.5*sigma*sigma
    sims = np.random.lognormal(mean=mu, sigma=sigma, size=int(n_mc))
    p50 = float(np.percentile(sims,50))
    p80 = float(np.percentile(sims,80))
    p90 = float(np.percentile(sims,90))
    st.write(f"P50: **{p50:,.0f} €** | P80: **{p80:,.0f} €** | P90: **{p90:,.0f} €**  (sigma={sigma:.2f})")
    hist = pd.DataFrame({"total": sims})
    st.bar_chart(hist["total"].value_counts(bins=30).sort_index())

# Export
st.markdown("### Exportables")
cA, cB, cC = st.columns([1,1,2])
with cA:
    sc_export = st.selectbox("Escenario a exportar", scenario_pick if scenario_pick else SCENARIOS, format_func=lambda s: SCENARIO_LABELS[s])
with cB:
    project_name = st.text_input("Proyecto (opcional)", value="")
with cC:
    st.caption("CSV: desglose + factores. PDF: resumen + desglose + fuentes + benchmark.")

if st.button("Preparar CSV"):
    df_out = breakdowns[sc_export].copy()
    df_out["scenario"] = sc_export
    df_out["module"] = module_key
    df_out["project"] = project_name
    df_out["area_ref_m2"] = float(area_ref)
    st.download_button("⬇️ Descargar CSV", df_out.to_csv(index=False).encode("utf-8"), file_name=f"capex_{module_key}_{sc_export}.csv", mime="text/csv")

if st.button("Preparar PDF"):
    with tempfile.TemporaryDirectory() as td:
        pdf_path = Path(td) / f"capex_{module_key}_{sc_export}.pdf"
        inp = ReportInputs(
            title=f"Informe CAPEX PRO - {project_name}".strip(" -"),
            module_label=module_def["label"],
            area_label=area_label,
            m2_above=float(m2_above),
            m2_below=float(m2_below),
            scenario_label=SCENARIO_LABELS[sc_export],
            building_use=building_use_label,
            factors={
                "complejidad":complejidad,"altura":altura,"localizacion":localizacion,"indexacion_temporal":indexacion,
                "intensidad_mep":intensidad_mep,"acabados":acabados,"certificacion":certificacion,"plazo":plazo,"estado_previo":estado_previo
            },
            options={k:str(v) for k,v in options.items()},
            notes="Estimación paramétrica orientativa."
        )
        export_pdf(pdf_path, inp, breakdowns[sc_export], totals_by_scenario[sc_export], sources_df, bench_row)
        st.download_button("⬇️ Descargar PDF", pdf_path.read_bytes(), file_name=pdf_path.name, mime="application/pdf")

with st.expander("Fuentes (matriz)"):
    st.dataframe(sources_df, use_container_width=True)

with st.expander("Benchmarks (data/benchmarks.csv)"):
    st.dataframe(bench_df, use_container_width=True)

st.markdown("---")
st.caption("Edita rangos y multiplicadores en data/cost_ranges.yaml y benchmarks en data/benchmarks.csv. Mantén trazabilidad en data/sources_matrix.csv.")
