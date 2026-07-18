"""BRIDGE trend-deviation analysis engine.

Reads a structured patient profile (data/patient_profile.json) — problem list,
discharge summary, med list, 90-day baselines, a home-vitals time series, and a
set of dated single-lead ECG beats — and computes, from the data:

  * per-metric deviation vs the patient's own 90-day baseline: z-score, absolute
    delta, short-window trend slope, and rule-based clinical flags;
  * an ECG morphology comparison: a MEDIAN baseline beat built from the prior
    normal tracings, compared against the most recent beat (T-wave amplitude
    delta and T/R ratio) to detect a new peaked-T-wave pattern;
  * a fused alert with an overall severity tier and the specific evidence.

Pure standard library so it runs anywhere. The demo data is fixed, but the code
path is real: point the loaders at a FHIR/RPM feed and nothing else changes.
The in-browser demo ports these same computations to JavaScript.
"""

from __future__ import annotations
import json
from pathlib import Path
from statistics import median

DATA = Path(__file__).resolve().parent.parent / "data"

# Fractional windows within the normalized single-beat sample array.
R_WINDOW = (0.30, 0.45)
T_WINDOW = (0.58, 0.86)

# Metrics where a DROP from baseline is the abnormal direction.
LOWER_IS_WORSE = {"spo2", "hrv_sdnn"}


def load_profile(name: str = "patient_profile.json") -> dict:
    return json.loads((DATA / name).read_text())


def _slope_per_day(values: list[float]) -> float:
    """Least-squares slope (units/day) over an evenly-spaced daily series."""
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    mx = sum(xs) / n
    my = sum(values) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, values))
    den = sum((x - mx) ** 2 for x in xs)
    return num / den if den else 0.0


def _window_peak(samples: list[float], window: tuple[float, float]) -> float:
    lo = int(window[0] * (len(samples) - 1))
    hi = int(window[1] * (len(samples) - 1))
    return max(samples[lo : hi + 1])


def median_beat(beats: list[list[float]]) -> list[float]:
    """Element-wise median across aligned single-beat sample arrays."""
    return [median(col) for col in zip(*beats)]


def analyze_vitals(profile: dict) -> list[dict]:
    """Per-metric deviation of the latest reading vs the 90-day baseline."""
    baselines = profile["baselines_90d"]
    vitals = profile["home_vitals"]
    latest = vitals[-1]
    out = []
    for key, base in baselines.items():
        series = [v[key] for v in vitals if key in v]
        if not series:
            continue
        value = latest[key]
        z = (value - base["mean"]) / base["sd"] if base["sd"] else 0.0
        delta = value - base["mean"]
        slope = _slope_per_day(series)
        worse_dir = -1 if key in LOWER_IS_WORSE else 1
        flagged = worse_dir * z >= 2.0  # >=2 SD in the abnormal direction
        out.append({
            "metric": key,
            "unit": base.get("unit", ""),
            "value": round(value, 1),
            "baseline_mean": base["mean"],
            "baseline_sd": base["sd"],
            "z_score": round(z, 1),
            "delta": round(delta, 1),
            "slope_per_day": round(slope, 2),
            "flagged": bool(flagged),
        })
    return out


def analyze_ecg(profile: dict) -> dict:
    """Compare the most recent beat against the median of the prior normal beats."""
    beats = profile["ecg_beats"]
    baseline_samples = [b["samples"] for b in beats if b["classification"] == "normal"]
    recent = beats[-1]
    base_beat = median_beat(baseline_samples)

    base_t = _window_peak(base_beat, T_WINDOW)
    base_r = _window_peak(base_beat, R_WINDOW)
    rec_t = _window_peak(recent["samples"], T_WINDOW)
    rec_r = _window_peak(recent["samples"], R_WINDOW)

    t_delta = rec_t - base_t
    base_ratio = base_t / base_r if base_r else 0.0
    rec_ratio = rec_t / rec_r if rec_r else 0.0
    # "peaked" heuristic: T amplitude climbs well above baseline and past ~0.35 of R
    peaked = t_delta >= 0.20 and rec_ratio >= 0.35

    return {
        "baseline_beat": [round(v, 4) for v in base_beat],
        "recent_beat": recent["samples"],
        "recent_date": recent["date"],
        "n_baseline_beats": len(baseline_samples),
        "baseline_t_mv": round(base_t, 3),
        "recent_t_mv": round(rec_t, 3),
        "t_delta_mv": round(t_delta, 3),
        "baseline_tr_ratio": round(base_ratio, 2),
        "recent_tr_ratio": round(rec_ratio, 2),
        "peaked_t_wave": bool(peaked),
    }


def summarize(profile: dict) -> dict:
    """Fuse per-metric + ECG findings into a triage-ready alert."""
    vitals = analyze_vitals(profile)
    ecg = analyze_ecg(profile)
    by = {v["metric"]: v for v in vitals}

    evidence = []
    hr = by.get("resting_hr")
    if hr and hr["flagged"]:
        evidence.append(
            f"Resting HR {hr['value']} vs baseline {hr['baseline_mean']} "
            f"(+{hr['z_score']} SD), {'rising' if hr['slope_per_day'] > 0 else 'flat'} "
            f"{round(hr['slope_per_day'],1)} bpm/day"
        )
    wt = by.get("weight_kg")
    if wt:
        gain = round(wt["value"] - profile["home_vitals"][0]["weight_kg"], 1)
        if gain >= 2.0:
            evidence.append(f"Weight +{gain} kg over {len(profile['home_vitals'])} days (>2 kg threshold)")
    sp = by.get("spo2")
    if sp and sp["flagged"]:
        evidence.append(f"SpO2 {sp['value']}% ({sp['delta']} vs baseline {sp['baseline_mean']}%)")
    hrv = by.get("hrv_sdnn")
    if hrv and hrv["flagged"]:
        evidence.append(f"HRV(SDNN) {hrv['value']} ms ({hrv['delta']} vs {hrv['baseline_mean']} ms)")
    if ecg["peaked_t_wave"]:
        evidence.append(
            f"NEW peaked T waves on {ecg['recent_date']} "
            f"(+{ecg['t_delta_mv']} mV, T/R {ecg['baseline_tr_ratio']}->{ecg['recent_tr_ratio']}) "
            f"vs median of {ecg['n_baseline_beats']} prior normal beats"
        )

    n_flags = sum(1 for v in vitals if v["flagged"])
    multi_signal = n_flags >= 2
    # med context: MRA up-titration + ARNI + CKD raises hyperkalemia pretest probability
    k_risk_meds = [m for m in profile["medications"] if m.get("renal_k_risk")]
    mra_increased = any("increased" in (m.get("recently_changed") or "") for m in profile["medications"])
    hyperk_context = ecg["peaked_t_wave"] and mra_increased and len(k_risk_meds) >= 2

    if multi_signal and ecg["peaked_t_wave"]:
        severity = "high"
    elif multi_signal or ecg["peaked_t_wave"]:
        severity = "medium"
    else:
        severity = "low"

    return {
        "patient_id": profile["patient_id"],
        "severity": severity,
        "n_metric_flags": n_flags,
        "multi_signal": multi_signal,
        "hyperkalemia_context": hyperk_context,
        "evidence": evidence,
        "vitals": vitals,
        "ecg": ecg,
    }


if __name__ == "__main__":
    s = summarize(load_profile())
    view = {k: v for k, v in s.items() if k != "ecg"}
    view["ecg"] = {k: v for k, v in s["ecg"].items() if k not in ("baseline_beat", "recent_beat")}
    print(json.dumps(view, indent=2))
