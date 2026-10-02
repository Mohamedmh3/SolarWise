"""Notebook-faithful runtime adapter for the SolarWise Tkinter UI."""
from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path

import numpy as np

try:
    from .pipeline import (
        build_appliance_map, load_and_engineer, predict_frame, pv_power_kw,
        run_profile, schedule_day, simulate, train_or_load_model,
    )
except ImportError:
    from pipeline import (
        build_appliance_map, load_and_engineer, predict_frame, pv_power_kw,
        run_profile, schedule_day, simulate, train_or_load_model,
    )

HERE = Path(__file__).resolve().parent
SETTINGS_PATH = HERE / "solarwise_settings.json"
MODEL_PATH = HERE / "best_model.joblib"
_CACHE = {}


def _settings():
    with SETTINGS_PATH.open(encoding="utf-8-sig") as fh:
        return json.load(fh)


def runtime_info():
    """Return provenance information for the UI without exposing model internals."""
    settings = _settings()
    df, artifact = _get_frame(settings)
    return {
        "dataset": settings["dataset"],
        "source": "NASA POWER",
        "location": "Damascus",
        "model": artifact["name"],
        "features": len(artifact["features"]),
        "date_start": df["Local_Date"].min().isoformat(),
        "date_end": df["Local_Date"].max().isoformat(),
        "artifact": MODEL_PATH.name,
        "modeled_note": "PV, household demand, and battery flows are modeled estimates.",
    }


def load_appliances(path=None):
    path = Path(path or HERE / "appliances.csv")
    result = []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            result.append({
                "name": row["Appliance"], "power": float(row["Power_kW"]),
                "duration": float(row["Duration_h"]), "priority": row["Category"],
                "run": True, "normal": int(float(row["Normal_Start"])),
                "window_start": int(float(row["Window_Start"])),
                "window_end": int(float(row["Window_End"])),
                "schedulable": row["Schedulable"].strip().lower() == "true",
                "hot_only": row["Only_On_Hot_Days"].strip().lower() == "true",
            })
    return result


def _get_frame(settings):
    key = (settings["dataset"], settings.get("local_utc_offset_h", 3))
    if key not in _CACHE:
        df = load_and_engineer(
            HERE / settings["dataset"], settings.get("local_utc_offset_h", 3)
        )
        artifact = train_or_load_model(df, MODEL_PATH)
        df = predict_frame(df, artifact)
        _CACHE[key] = (df, artifact)
    return _CACHE[key]


def _day_rows(df):
    grouped = []
    for date, part in df.dropna(subset=["Pred_Solar"]).groupby("Local_Date", sort=True):
        part = part.sort_values("Local_Hour")
        if len(part) == 24 and list(part["Local_Hour"]) == list(range(24)):
            grouped.append((date, part))
    return grouped


def _format_time(value):
    return f"{int(value):02d}:{int(round((value % 1) * 60)):02d}"


def _classify(value, thresholds):
    return "LOW" if value < thresholds[0] else "MEDIUM" if value < thresholds[1] else "HIGH"


def _ui_window(name, start, appliance, forecast, radiation, base_load, normal, thresholds):
    profile = run_profile(appliance["p"], appliance["dur"], start)
    touched = np.where(profile > 0)[0]
    surplus = np.clip(forecast - base_load, 0, None)
    covered = float(np.minimum(profile, surplus).sum())
    energy = float(profile.sum())
    solar = float(forecast[touched].sum())
    return {
        "start": start, "end": start + appliance["dur"],
        "solar": solar / max(appliance["dur"], 1),
        "demand": energy / max(appliance["dur"], 1),
        "surplus": float(np.clip(surplus - profile, 0, None)[touched].sum()),
        "coverage": covered / energy * 100 if energy else 0.0,
        "label": f"{_format_time(start)}-{_format_time(start + appliance['dur'])}",
        "availability": _classify(float(radiation[touched].mean()), thresholds) if len(touched) else "LOW",
        "battery_draw": max(0.0, energy - covered),
    }


def _analyze_day(part, settings, appliances, system):
    app_map = build_appliance_map(appliances)
    normal = {name: a["normal"] for name, a in app_map.items()}
    temperature = part["Temperature"].to_numpy(float)
    hot = float(temperature.max()) >= float(settings["hot_day_threshold_c"])
    pv_capacity = float(system["pv_kw"])
    inverter_capacity = float(system.get("inverter_kw", pv_capacity))
    if pv_capacity <= 0 or inverter_capacity <= 0:
        raise ValueError("PV and inverter capacity must be greater than zero")
    effective_capacity = min(pv_capacity, inverter_capacity)
    pv_forecast = pv_power_kw(
        part["Pred_Solar"], temperature, effective_capacity,
        float(settings["pv"]["system_efficiency"]),
        float(settings["pv"]["gamma"]), float(settings["pv"]["cell_temp_rise"]),
    )
    pv_actual = pv_power_kw(
        part["Solar_Radiation"], temperature, effective_capacity,
        float(settings["pv"]["system_efficiency"]),
        float(settings["pv"]["gamma"]), float(settings["pv"]["cell_temp_rise"]),
    )
    starts, demand = schedule_day(pv_forecast, hot, normal, app_map)
    sim = simulate(
        demand, pv_actual, float(system["battery_kwh"]), float(system["soc"]),
        float(settings["battery"]["eta_charge"]),
        float(settings["battery"]["eta_discharge"]),
        float(settings["battery"]["max_rate_c"]),
    )
    windows, recommendations = {}, []
    for name, appliance in app_map.items():
        if not appliance["sched"] or (appliance["hot"] and not hot):
            continue
        base = np.zeros(24)
        for other_name, other in app_map.items():
            if other_name != name and (not other["hot"] or hot):
                base += run_profile(
                    other["p"], other["dur"], normal[other_name]
                )
        candidates = []
        for start in range(appliance["ws"], appliance["we"] + 1):
            if start + appliance["dur"] <= 24:
                candidates.append(_ui_window(
                    name, start, appliance, pv_forecast,
                    part["Solar_Radiation"].to_numpy(float), base, normal,
                    settings["hourly_class_thresholds_wm2"],
                ))
        candidates.sort(key=lambda item: (item["coverage"], -abs(item["start"] - appliance["normal"])), reverse=True)
        if candidates:
            windows[name] = [candidates[0], candidates[1] if len(candidates) > 1 else None]
            best = candidates[0]
            recommendations.append({
                "kind": "success" if best["coverage"] >= 80 else "warn",
                "title": f"{name}: {best['label']}",
                "text": f"Forecast solar covers about {best['coverage']:.0f}% of its load.",
            })
    radiation = part["Solar_Radiation"].to_numpy(float)
    daylight = np.where(radiation > 10)[0]
    cloud = part.loc[part["Clear_Sky_Solar_Radiation"] > 10, "Solar_Radiation"]
    clear = part.loc[part["Clear_Sky_Solar_Radiation"] > 10, "Clear_Sky_Solar_Radiation"]
    full = next((i for i, value in enumerate(sim["soc_kwh"]) if value >= float(system["battery_kwh"]) * .999), None)
    return {
        "analyzed_date": str(part["Local_Date"].iloc[0]),
        "weather": {"irradiance": radiation.tolist()},
        "generation": pv_actual.tolist(), "forecast_generation": pv_forecast.tolist(),
        "demand": demand.tolist(), "total_gen": float(sim["pv"].sum()),
        "total_demand": float(sim["load"].sum()),
        "scheduled_energy": float(sum(
            a["p"] * a["dur"] for a in app_map.values()
            if a["sched"] and (not a["hot"] or hot)
        )),
        "balance": float(sim["pv"].sum() - sim["load"].sum()),
        "ratio": float(sim["direct"].sum() / max(sim["pv"].sum(), 1e-9)),
        "level": _classify(float(radiation.mean()), settings["hourly_class_thresholds_wm2"]),
        "battery_full_at": full, "peak_hour": int(np.argmax(pv_actual)),
        "sunrise": int(daylight.min()) if len(daylight) else 0,
        "sunset": int(daylight.max()) if len(daylight) else 0,
        "avg_cloud": float((1 - cloud.to_numpy() / clear.to_numpy()).mean() * 100) if len(cloud) else 0.0,
        "max_temp": float(temperature.max()), "windows": windows,
        "recommendations": recommendations,
        "soc": float(sim["soc_pct"].iloc[-1]) if len(sim) else float(system["soc"]),
        "metrics": {
            "direct_solar_kwh": float(sim["direct"].sum()),
            "battery_consumed_kwh": float(sim["batt_out"].sum()),
            "unused_solar_kwh": float(sim["curtailed"].sum()),
            "unmet_kwh": float(sim["unmet"].sum()),
        },
    }


def analyze(system, appliances, day):
    settings = _settings()
    df, _ = _get_frame(settings)
    days = _day_rows(df)
    if len(days) < 2:
        raise ValueError("Solar dataset must contain at least two complete local days")
    _, part = days[-2 if day == "today" else -1]
    return _analyze_day(part, settings, appliances, system)


def warning(today, tomorrow):
    if today["total_gen"] <= 0:
        return None
    drop = (today["total_gen"] - tomorrow["total_gen"]) / today["total_gen"]
    if drop < 0.2:
        return None
    return {
        "kind": "danger", "title": "Cloudy day tomorrow",
        "text": f"Solar production is expected to be about {drop:.0%} lower than today "
                 f"({tomorrow['total_gen']:.1f} vs {today['total_gen']:.1f} kWh).",
        "drop": drop,
    }
