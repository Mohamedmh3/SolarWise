"""Reusable implementation of the SolarWise notebook pipeline."""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error


FEATURES = [
    "Hour", "Month", "DayOfYear", "Temperature", "Rain",
    "Clear_Sky_Solar_Radiation", "Solar_Lag_24",
]
TARGET = "Solar_Radiation"
RANDOM_STATE = 42


def pv_power_kw(radiation_wm2, temp_c, capacity_kw, efficiency, gamma=-0.004,
                cell_temp_rise=0.03125):
    """The notebook's PV estimate, including the inverter capacity limit."""
    g = np.asarray(radiation_wm2, dtype=float)
    t_cell = np.asarray(temp_c, dtype=float) + cell_temp_rise * g
    power = capacity_kw * (g / 1000.0) * (1 + gamma * (t_cell - 25.0)) * efficiency
    return np.clip(power, 0, capacity_kw)


def load_and_engineer(dataset_path, local_utc_offset=3):
    """Load NASA data and reproduce the notebook's feature engineering."""
    df = pd.read_csv(dataset_path)
    required = {
        "time", "ALLSKY_SFC_SW_DWN", "CLRSKY_SFC_SW_DWN", "T2M",
        "PRECTOTCORR",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")
    df["time"] = pd.to_datetime(df["time"], errors="raise")
    df = df.sort_values("time").reset_index(drop=True)
    if df["time"].diff().dropna().ne(pd.Timedelta(hours=1)).any():
        raise ValueError("Dataset contains gaps; Solar_Lag_24 requires continuous hourly data")
    df = df.rename(columns={
        "ALLSKY_SFC_SW_DWN": "Solar_Radiation",
        "CLRSKY_SFC_SW_DWN": "Clear_Sky_Solar_Radiation",
        "T2M": "Temperature",
        "PRECTOTCORR": "Rain",
    })
    df["Year"] = df["time"].dt.year
    df["Month"] = df["time"].dt.month
    df["Day"] = df["time"].dt.day
    df["Hour"] = df["time"].dt.hour
    df["DayOfWeek"] = df["time"].dt.dayofweek
    df["DayOfYear"] = df["time"].dt.dayofyear
    df["Local_time"] = df["time"] + pd.Timedelta(hours=local_utc_offset)
    df["Local_Hour"] = df["Local_time"].dt.hour
    df["Local_Date"] = df["Local_time"].dt.date
    df["Is_Daytime"] = df["Clear_Sky_Solar_Radiation"] > 20
    ratio = np.where(
        df["Is_Daytime"],
        df["Solar_Radiation"] / df["Clear_Sky_Solar_Radiation"].replace(0, np.nan),
        np.nan,
    )
    df["Solar_Ratio"] = np.clip(ratio, 0, 1.5)
    df["Solar_Difference"] = (
        df["Clear_Sky_Solar_Radiation"] - df["Solar_Radiation"]
    )
    df["Solar_Lag_24"] = df["Solar_Radiation"].shift(24)
    return df


def postprocess(prediction, clear_sky):
    prediction = np.clip(np.asarray(prediction, dtype=float), 0, None)
    return np.where(np.asarray(clear_sky) <= 0, 0.0, prediction)


def train_or_load_model(df, artifact_path, force_retrain=False):
    """Load the notebook artifact or train and save it with the same selection rule."""
    artifact_path = Path(artifact_path)
    if artifact_path.exists() and not force_retrain:
        artifact = joblib.load(artifact_path)
        if artifact.get("features") != FEATURES:
            raise ValueError("best_model.joblib was trained with incompatible features")
        return artifact

    ml = df.dropna(subset=["Solar_Lag_24"]).reset_index(drop=True)
    n = len(ml)
    train_end, val_end = int(n * 0.70), int(n * 0.85)
    train, val = ml.iloc[:train_end], ml.iloc[train_end:val_end]
    models = {
        "Linear Regression": LinearRegression(),
        "Random Forest": RandomForestRegressor(
            n_estimators=60, max_depth=14, min_samples_leaf=5,
            n_jobs=-1, random_state=RANDOM_STATE,
        ),
        "Gradient Boosting": HistGradientBoostingRegressor(
            max_iter=200, random_state=RANDOM_STATE,
        ),
    }
    fitted, scores = {}, {}
    for name, model in models.items():
        model.fit(train[FEATURES], train[TARGET])
        fitted[name] = model
        scores[name] = mean_absolute_error(
            val[TARGET],
            postprocess(model.predict(val[FEATURES]), val["Clear_Sky_Solar_Radiation"]),
        )
    best_mae = min(scores.values())
    chosen_name = next(
        name for name in models if scores[name] <= best_mae * 1.02
    )
    artifact = {
        "model": fitted[chosen_name],
        "features": FEATURES,
        "name": chosen_name,
        "validation_mae": float(scores[chosen_name]),
    }
    joblib.dump(artifact, artifact_path)
    return artifact


def predict_frame(df, artifact):
    """Add the notebook's postprocessed solar prediction to a feature frame."""
    result = df.copy()
    valid = result["Solar_Lag_24"].notna()
    result["Pred_Solar"] = np.nan
    result.loc[valid, "Pred_Solar"] = postprocess(
        artifact["model"].predict(result.loc[valid, FEATURES]),
        result.loc[valid, "Clear_Sky_Solar_Radiation"],
    )
    return result


def run_profile(power, duration, start):
    values = np.zeros(24)
    for hour in range(24):
        overlap = max(0.0, min(start + duration, hour + 1) - max(start, hour))
        values[hour] = overlap * power
    return values


def simulate(load, pv, cap_kwh, soc0_pct, eta_c=0.95, eta_d=0.95, rate_c=0.5):
    """The notebook's battery simulation, returning a pandas DataFrame."""
    load = np.asarray(load, dtype=float).ravel()
    pv = np.asarray(pv, dtype=float).ravel()
    if load.shape != pv.shape:
        raise ValueError("load and pv must have the same shape")
    soc = cap_kwh * soc0_pct / 100.0
    rate = cap_kwh * rate_c
    out = {key: np.zeros(len(load)) for key in
           ["direct", "to_batt", "curtailed", "batt_out", "unmet", "soc_kwh"]}
    for t in range(len(load)):
        direct = min(pv[t], load[t])
        surplus, deficit = pv[t] - direct, load[t] - direct
        room = (cap_kwh - soc) / eta_c if cap_kwh > 0 else 0.0
        charge_in = min(surplus, rate, room)
        soc += charge_in * eta_c
        delivered = min(deficit, rate, soc * eta_d)
        soc -= delivered / eta_d
        out["direct"][t], out["to_batt"][t] = direct, charge_in
        out["curtailed"][t] = surplus - charge_in
        out["batt_out"][t], out["unmet"][t] = delivered, deficit - delivered
        out["soc_kwh"][t] = soc
    sim = pd.DataFrame(out)
    sim["pv"], sim["load"] = pv, load
    sim["soc_pct"] = sim["soc_kwh"] / cap_kwh * 100 if cap_kwh > 0 else 0.0
    return sim


def schedule_day(pv_forecast, hot, normal_starts, appliances):
    """The notebook's greedy Important-then-Flexible scheduler."""
    pv_forecast = np.asarray(pv_forecast, dtype=float)
    starts = dict(normal_starts)
    active = [n for n, a in appliances.items() if (not a["hot"]) or hot]
    load = np.zeros(24)
    for name in active:
        a = appliances[name]
        if a["cat"] == "Essential" or not a["sched"]:
            load += run_profile(a["p"], a["dur"], starts[name])
    for group in ["Important", "Flexible"]:
        names = [n for n in active if appliances[n]["cat"] == group and appliances[n]["sched"]]
        names.sort(key=lambda n: -appliances[n]["p"] * appliances[n]["dur"])
        for name in names:
            a = appliances[name]
            best_key, best_start = None, a["normal"]
            for start in range(a["ws"], a["we"] + 1):
                if start + a["dur"] > 24:
                    continue
                profile = run_profile(a["p"], a["dur"], start)
                surplus = np.clip(pv_forecast - load, 0, None)
                key = (round(float(np.minimum(profile, surplus).sum()), 6),
                       -abs(start - a["normal"]))
                if best_key is None or key > best_key:
                    best_key, best_start = key, start
            starts[name] = best_start if best_key is not None and best_key[0] > 0 else a["normal"]
            load += run_profile(a["p"], a["dur"], starts[name])
    return starts, load


def build_appliance_map(rows):
    return {
        row["name"]: {
            "p": float(row["power"]), "dur": float(row["duration"]),
            "cat": row["priority"], "normal": int(row.get("normal", 12)),
            "ws": int(row.get("window_start", 8)), "we": int(row.get("window_end", 20)),
            "sched": bool(row.get("schedulable", row["priority"] != "Essential")),
            "hot": bool(row.get("hot_only", False)),
        }
        for row in rows if row.get("run", True)
    }

