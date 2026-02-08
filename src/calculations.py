
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Tuple, Optional
import math
import pandas as pd

SCENARIOS = ["low","mid","high"]
SCENARIO_LABELS = {"low":"Bajo","mid":"Medio","high":"Alto"}

@dataclass
class Factors:
    complejidad: float = 1.0
    altura: float = 1.0
    localizacion: float = 1.0
    intensidad_mep: float = 1.0
    acabados: float = 1.0
    certificacion: float = 1.0
    plazo: float = 1.0
    estado_previo: float = 1.0
    indexacion_temporal: float = 1.0  # factor de actualización por índice (MITMA/INE), manual o cargado

    def combined(self) -> float:
        return float(self.complejidad * self.altura * self.localizacion * self.intensidad_mep *
                     self.acabados * self.certificacion * self.plazo * self.estado_previo * self.indexacion_temporal)

def _is_mep(ch_key: str) -> bool:
    return ch_key.startswith("mep_") or ch_key in ("mep","mep_renov","mep_interiores")

def _is_arch_finish(ch_key: str) -> bool:
    return ch_key in ("acabados","particiones","carpinterias","envolvente","envolvente_mej","techos","obra_civil","albanileria")

def sum_chapters(module_def: Dict[str, Any], scenario: str, m2_above: float, m2_below: float,
                 intensity_mep: float, finishes: float) -> pd.DataFrame:
    rows = []
    for ch in module_def["chapters"]:
        key = ch["key"]
        label = ch["label"]
        basis = ch.get("basis","base")

        factor = 1.0
        if _is_mep(key):
            factor *= intensity_mep
        if _is_arch_finish(key):
            factor *= finishes

        if "above" in ch:
            above = ch["above"][scenario]
            below = ch["below"][scenario]
            cost = above*m2_above + below*m2_below
            rows.append([key,label,basis,above,below,m2_above,m2_below,cost*factor,factor,"chapter_rate"])
        else:
            single = ch["single"][scenario]
            cost = single*(m2_above)
            rows.append([key,label,basis,single,None,m2_above,0.0,cost*factor,factor,"chapter_rate"])

    return pd.DataFrame(rows, columns=["chapter_key","capitulo","basis","eur_m2_above","eur_m2_below","m2_above","m2_below","cost_direct","factor_capitulo","source_mode"])

def apply_building_use(df: pd.DataFrame, module_def: Dict[str, Any], building_use: Optional[str]) -> Tuple[pd.DataFrame, Dict[str,float]]:
    if not building_use:
        return df, {"arch":1.0,"mep":1.0,"overall":1.0}
    use_profiles = module_def.get("use_profiles",{})
    up = use_profiles.get(building_use)
    if not up:
        return df, {"arch":1.0,"mep":1.0,"overall":1.0}

    arch_m = float(up.get("arch",1.0))
    mep_m = float(up.get("mep",1.0))
    overall_m = float(up.get("overall",1.0))

    df = df.copy()
    is_mep = df["chapter_key"].apply(_is_mep)
    df.loc[is_mep, "cost_direct"] *= mep_m
    df.loc[~is_mep, "cost_direct"] *= arch_m
    df["cost_direct"] *= overall_m
    return df, {"arch":arch_m,"mep":mep_m,"overall":overall_m}

def estimate_module(cost_data: Dict[str, Any], module_key: str, scenario: str,
                    m2_above: float, m2_below: float,
                    factors: Factors,
                    options: Dict[str, Any] | None = None,
                    benchmark_row: Dict[str, Any] | None = None,
                    auto_calibrate_to_benchmark: bool = False) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """
    PRO:
    - Coste directo bottom-up por capítulos.
    - Multiplicadores por uso (edificio).
    - Multiplicadores por intervención/nivel/uso (fit-out local).
    - Indexación temporal (factor).
    - Calibración opcional a benchmark top-down (escenario).
    """
    options = options or {}
    module_def = cost_data["modules"][module_key]

    df = sum_chapters(module_def, scenario, m2_above, m2_below, factors.intensidad_mep, factors.acabados)

    # optional filtering
    if module_key == "fitout_oficinas" and not options.get("include_furniture", False):
        df = df[df["chapter_key"]!="mobiliario"].copy()

    # use profiles (only edificio completo)
    use_mults = {"arch":1.0,"mep":1.0,"overall":1.0}
    if module_key in ("obra_nueva_edificio","reposicionamiento_edificio"):
        df, use_mults = apply_building_use(df, module_def, options.get("building_use"))

    # module multipliers
    mult = 1.0
    if module_key == "reposicionamiento_edificio":
        mult *= module_def["defaults"]["intervention_multiplier"][options.get("intervention_level","medio")]
    if module_key == "reforma_piso":
        mult *= module_def["defaults"]["level_multiplier"][options.get("reform_level","integral")]
    if module_key == "reforma_local":
        mult *= module_def["defaults"]["intervention_multiplier"][options.get("intervention_level","media")]
    if module_key == "fitout_local_por_uso":
        mult *= module_def.get("use_multipliers",{}).get(options.get("use","otros"),1.0)

    # global factor (incl. temporal index)
    combined = factors.combined() * mult
    df["cost_direct"] *= combined
    df["factor_global"] = combined
    df["factor_use_arch"] = use_mults["arch"]
    df["factor_use_mep"] = use_mults["mep"]
    df["factor_use_overall"] = use_mults["overall"]
    df["factor_module"] = mult

    direct = float(df["cost_direct"].sum())

    # Optional calibration to benchmark (top-down)
    calib = 1.0
    if auto_calibrate_to_benchmark and benchmark_row and benchmark_row.get("pem_"+scenario) is not None:
        # area basis: for building modules use total built; for others use m2_above (single)
        area = (m2_above + m2_below) if ("above" in module_def["chapters"][0]) else m2_above
        if area > 0 and direct > 0:
            target_direct = float(benchmark_row["pem_"+scenario]) * float(area)
            calib = target_direct / direct
            df["cost_direct"] *= calib
            df["source_mode"] = "calibrated_to_benchmark"
            direct = float(df["cost_direct"].sum())
    df["factor_calibration"] = calib

    defaults = module_def["defaults"]
    indirects_pct = float(defaults["indirects_pct"][scenario])
    gg_bi_pct = float(defaults["gg_bi_pct"])
    soft_pct_default = float(defaults["soft_costs_pct"][scenario])
    soft_items_pct = float(options.get("soft_items_pct", soft_pct_default))
    soft_pct = soft_items_pct
    cont_pct_default = float(defaults["contingency_pct"][scenario])
    cont_items_pct = float(options.get("cont_items_pct", cont_pct_default))
    cont_pct = cont_items_pct

    indirects = direct * indirects_pct
    gg_bi = direct * gg_bi_pct
    soft = direct * soft_pct
    contingency = direct * cont_pct
    total = direct + indirects + gg_bi + soft + contingency

    return df, {"direct":direct,"indirects":indirects,"gg_bi":gg_bi,"soft_costs":soft, "soft_pct_used":soft_pct, "soft_pct_default":soft_pct_default,"contingency":contingency, "cont_pct_used":cont_pct, "cont_pct_default":cont_pct_default,"total":total,
                "calibration":calib, "use_arch":use_mults["arch"], "use_mep":use_mults["mep"], "use_overall":use_mults["overall"], "module_mult":mult}

def totals_table(totals_by_scenario: Dict[str, Dict[str,float]], area_ref: float) -> pd.DataFrame:
    rows=[]
    for sc, t in totals_by_scenario.items():
        rows.append([sc, SCENARIO_LABELS[sc], t["total"], (t["total"]/area_ref if area_ref>0 else math.nan),
                     t["direct"], t["indirects"], t["gg_bi"], t["soft_costs"], t["contingency"], t.get("calibration",1.0)])
    return pd.DataFrame(rows, columns=["scenario","escenario","total_eur","eur_m2","direct_eur","indirects_eur","gg_bi_eur","soft_costs_eur","contingency_eur","calib_factor"])
