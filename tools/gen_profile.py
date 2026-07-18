"""Generate data/patient_profile.json — the single source of truth the
analysis engine (backend/analysis.py and the in-browser port) reads."""
import json, math, random
from pathlib import Path

random.seed(7)
OUT = Path(__file__).resolve().parent.parent / "data" / "patient_profile.json"

N = 150  # samples per single-beat ECG

def pqrst(p, t_amp):
    def g(mu, sig, a): return a * math.exp(-((p - mu) ** 2) / (2 * sig * sig))
    y = g(0.12, 0.025, 0.10)      # P
    y += g(0.235, 0.012, -0.06)   # Q
    y += g(0.25, 0.012, 0.95)     # R
    y += g(0.268, 0.013, -0.18)   # S
    t_sig = max(0.026, 0.055 - (t_amp - 0.14) * 0.05)  # narrows as it peaks
    y += g(0.44, t_sig, t_amp)    # T — morphs
    return y

def beat(t_amp, noise=0.0):
    # sample one cardiac cycle across p in [0.02, 0.62] so P-QRS-T fills the window
    pts = []
    for i in range(N):
        p = 0.02 + (0.62 - 0.02) * i / (N - 1)
        v = pqrst(p, t_amp)
        if noise:
            v += random.gauss(0, noise)
        pts.append(round(v, 4))
    return pts

# --- 5 normal baseline beats over prior weeks + 1 recent abnormal ---
baseline_dates = ["2026-05-30", "2026-06-13", "2026-06-27", "2026-07-05", "2026-07-14"]
ecg_beats = []
for d in baseline_dates:
    t = random.uniform(0.13, 0.17)
    ecg_beats.append({"date": d, "classification": "normal", "t_wave": "normal",
                      "samples": beat(t, noise=0.006)})
ecg_beats.append({"date": "2026-07-18", "classification": "abnormal",
                  "t_wave": "peaked (device-flagged): tall, narrow, symmetric",
                  "samples": beat(0.62, noise=0.004)})

profile = {
    "patient_id": "PT-1042",
    "demographics": {"name": "Maria Alvarez", "age": 67, "sex": "F", "mrn": "UCSF-4471203"},
    "problem_list": [
        "HFrEF (LVEF 30%, TTE 07/2026)",
        "CAD s/p STEMI 2023, DES to proximal LAD",
        "Hypertension",
        "CKD stage 3a (baseline Cr 1.3)",
        "Type 2 diabetes mellitus",
    ],
    "discharge_summary": {
        "admission_dates": "2026-07-08 to 2026-07-13",
        "principal_diagnosis": "Acute decompensated heart failure exacerbation",
        "hospital_course": (
            "67F with HFrEF (EF 30%) admitted with a 4-day history of progressive "
            "dyspnea, orthopnea, and 3 kg weight gain. Diuresed with IV furosemide "
            "to net -4.2 L. Spironolactone up-titrated for GDMT optimization. "
            "Discharged euvolemic on day 5, Cr at baseline, K 4.4."
        ),
        "discharge_changes": [
            "Spironolactone INCREASED 12.5 -> 25 mg daily",
            "Furosemide 40 mg daily (resumed home dose)",
            "Counseled on daily weights, 2 g sodium, 1.5 L fluid restriction",
        ],
        "discharge_weight_kg": 71.2,
        "discharge_labs": {"K": 4.4, "Cr": 1.4, "eGFR": 44, "BNP": 1240, "Na": 138},
        "follow_up": "HF clinic within 7 days; repeat BMP within 5-7 days of MRA change",
    },
    "medications": [
        {"drug": "Sacubitril/valsartan", "dose": "49/51 mg", "freq": "BID", "class": "ARNI",
         "renal_k_risk": True},
        {"drug": "Spironolactone", "dose": "25 mg", "freq": "daily", "class": "MRA",
         "renal_k_risk": True, "recently_changed": "increased 12.5 -> 25 mg at discharge"},
        {"drug": "Carvedilol", "dose": "25 mg", "freq": "BID", "class": "beta-blocker"},
        {"drug": "Furosemide", "dose": "40 mg", "freq": "daily", "class": "loop diuretic"},
        {"drug": "Dapagliflozin", "dose": "10 mg", "freq": "daily", "class": "SGLT2i"},
        {"drug": "Aspirin", "dose": "81 mg", "freq": "daily", "class": "antiplatelet"},
        {"drug": "Atorvastatin", "dose": "80 mg", "freq": "daily", "class": "statin"},
        {"drug": "Metformin", "dose": "1000 mg", "freq": "BID", "class": "biguanide"},
    ],
    "allergies": ["NKDA"],
    "care_team": {
        "covering_np": "Dana Kim, NP — Cardiology, UCSF HF Clinic",
        "cardiologist": "Dr. R. Chen",
        "pharmacy": "UCSF Ambulatory Pharmacy",
    },
    "devices": ["BP cuff", "cellular scale", "pulse oximeter", "wearable (HR/HRV)",
                "single-lead ECG patch"],
    "baselines_90d": {
        "resting_hr": {"mean": 68, "sd": 4, "unit": "bpm"},
        "weight_kg": {"mean": 71.2, "sd": 0.6, "unit": "kg"},
        "spo2": {"mean": 97, "sd": 1, "unit": "%"},
        "sbp": {"mean": 118, "sd": 6, "unit": "mmHg"},
        "dbp": {"mean": 72, "sd": 5, "unit": "mmHg"},
        "hrv_sdnn": {"mean": 42, "sd": 6, "unit": "ms"},
        "resp_rate": {"mean": 16, "sd": 2, "unit": "/min"},
    },
    "home_vitals": [
        {"date": "2026-07-14", "resting_hr": 70, "weight_kg": 71.3, "spo2": 97,
         "sbp": 116, "dbp": 70, "hrv_sdnn": 41, "resp_rate": 16, "symptoms": "none"},
        {"date": "2026-07-15", "resting_hr": 72, "weight_kg": 71.6, "spo2": 97,
         "sbp": 118, "dbp": 72, "hrv_sdnn": 39, "resp_rate": 16, "symptoms": "none"},
        {"date": "2026-07-16", "resting_hr": 78, "weight_kg": 72.4, "spo2": 96,
         "sbp": 122, "dbp": 76, "hrv_sdnn": 35, "resp_rate": 17, "symptoms": "mild fatigue"},
        {"date": "2026-07-17", "resting_hr": 84, "weight_kg": 73.1, "spo2": 95,
         "sbp": 126, "dbp": 78, "hrv_sdnn": 31, "resp_rate": 18, "symptoms": "tired, slept propped up"},
        {"date": "2026-07-18", "time": "21:40", "resting_hr": 92, "weight_kg": 73.9, "spo2": 94,
         "sbp": 128, "dbp": 80, "hrv_sdnn": 27, "resp_rate": 20, "symptoms": "pending agent check-in"},
    ],
    "ecg_meta": {"lead": "I", "source": "single-lead home patch",
                 "representation": "median beat, one normalized cardiac cycle, 150 samples",
                 "amplitude_unit": "mV"},
    "ecg_beats": ecg_beats,
}

OUT.write_text(json.dumps(profile, indent=2))
print("wrote", OUT, OUT.stat().st_size, "bytes;", len(ecg_beats), "beats")
