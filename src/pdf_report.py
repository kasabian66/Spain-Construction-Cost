
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict
from pathlib import Path
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

@dataclass
class ReportInputs:
    title: str
    module_label: str
    area_label: str
    m2_above: float
    m2_below: float
    scenario_label: str
    building_use: str
    factors: Dict[str, float]
    options: Dict[str, str]
    notes: str

def export_pdf(filepath: str | Path, inputs: ReportInputs, df_breakdown: pd.DataFrame, totals: Dict[str,float],
               sources_df: pd.DataFrame, bench_row: dict | None) -> None:
    c = canvas.Canvas(str(filepath), pagesize=A4)
    width, height = A4
    x0 = 2*cm
    y = height - 2*cm

    def draw(txt, dy=14, font=("Helvetica",10)):
        nonlocal y
        c.setFont(font[0], font[1])
        c.drawString(x0, y, txt)
        y -= dy

    draw(inputs.title, dy=18, font=("Helvetica-Bold",14))
    draw(f"Módulo: {inputs.module_label}")
    if inputs.building_use:
        draw(f"Uso: {inputs.building_use}")
    draw(f"Escenario: {inputs.scenario_label}")
    draw(f"Superficie: {inputs.area_label} | Sobre rasante: {inputs.m2_above:.1f} m² | Bajo rasante: {inputs.m2_below:.1f} m²")

    if bench_row:
        draw("")
        draw("Benchmark (top-down)", dy=16, font=("Helvetica-Bold",11))
        draw(f"{bench_row.get('label','')}: {bench_row.get('pem_low','')} / {bench_row.get('pem_mid','')} / {bench_row.get('pem_high','')} ({bench_row.get('unit','')})", dy=12, font=("Helvetica",9))

    draw("")
    draw("Factores", dy=16, font=("Helvetica-Bold",11))
    for k,v in inputs.factors.items():
        draw(f"- {k}: {v:.3f}", dy=12, font=("Helvetica",10))

    if inputs.options:
        draw("")
        draw("Opciones", dy=16, font=("Helvetica-Bold",11))
        for k,v in inputs.options.items():
            draw(f"- {k}: {v}", dy=12, font=("Helvetica",10))

    draw("")
    draw("Desglose directo (capítulos)", dy=16, font=("Helvetica-Bold",11))
    c.setFont("Helvetica", 9)
    y -= 2
    c.drawString(x0, y, "Capítulo")
    c.drawRightString(x0 + 16*cm, y, "Coste")
    y -= 12

    for _, row in df_breakdown.iterrows():
        cap = str(row.get("capitulo",""))[:78]
        val = float(row.get("cost_direct",0.0))
        c.drawString(x0, y, cap)
        c.drawRightString(x0 + 16*cm, y, f"{val:,.0f} €")
        y -= 11
        if y < 2.5*cm:
            c.showPage()
            y = height - 2*cm
            c.setFont("Helvetica", 9)

    draw("")
    draw("Resumen", dy=16, font=("Helvetica-Bold",11))
    draw(f"Directo: {totals['direct']:,.0f} €")
    draw(f"Indirectos: {totals['indirects']:,.0f} €")
    draw(f"GG+BI: {totals['gg_bi']:,.0f} €")
    draw(f"Soft costs: {totals['soft_costs']:,.0f} €")
    draw(f"Contingencia: {totals['contingency']:,.0f} €")
    draw(f"TOTAL: {totals['total']:,.0f} €", font=("Helvetica-Bold",10))
    draw("")
    draw("Fuentes (resumen)", dy=16, font=("Helvetica-Bold",11))
    c.setFont("Helvetica", 8)
    for _, s in sources_df.head(12).iterrows():
        txt = f"- {s['fuente']} | {s['tipo']} | {s['fecha_consulta']} | {s['enlace']}"
        if len(txt) > 135:
            txt = txt[:132] + "..."
        c.drawString(x0, y, txt)
        y -= 10
        if y < 2.5*cm:
            c.showPage()
            y = height - 2*cm
            c.setFont("Helvetica", 8)

    draw("")
    draw("Aviso: estimación paramétrica orientativa. No sustituye un presupuesto por medición.", dy=12, font=("Helvetica-Oblique",8))
    c.save()
