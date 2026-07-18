"""Tool implementations for the BRIDGE cardiology agent.

In the hackathon build, patient data comes from synthetic JSON and the
patient/NP conversations are relayed through the demo UI over SSE. In a
production build these would hit the EHR (FHIR), the RPM vendor API, and
the clinic's secure messaging + scheduling systems.
"""

import json
from pathlib import Path
from datetime import datetime

DATA = Path(__file__).resolve().parent.parent / "data"


def _load(name: str) -> dict:
    return json.loads((DATA / name).read_text())


def get_patient_profile(patient_id: str) -> dict:
    """Demographics, problem list, meds, recent discharge summary, 90-day baselines."""
    return _load("patient.json")


def get_vitals_window(patient_id: str, days: int = 5) -> dict:
    """Recent home-monitoring stream (HR q10min, daily BP/weight/SpO2/single-lead ECG)."""
    stream = _load("vitals_stream.json")
    return {"days": stream["days"][-days:], "deviation_summary": stream["deviation_summary"]}


def compare_to_baseline(patient_id: str) -> dict:
    """Compute deviations of the latest readings vs the 90-day baseline."""
    p = _load("patient.json")["baseline_90d"]
    latest = _load("vitals_stream.json")["days"][-1]
    return {
        "resting_hr": {
            "latest": latest["resting_hr_bpm"],
            "baseline_mean": p["resting_hr_bpm"]["mean"],
            "z_score": round(
                (latest["resting_hr_bpm"] - p["resting_hr_bpm"]["mean"]) / p["resting_hr_bpm"]["sd"], 1
            ),
        },
        "weight": {
            "latest_kg": latest["weight_kg"],
            "baseline_mean_kg": p["weight_kg"]["mean"],
            "delta_5d_kg": round(latest["weight_kg"] - 71.2, 1),
            "threshold": ">2 kg over 3 days triggers HF alert",
        },
        "spo2": {"latest": latest["spo2_pct"], "baseline_mean": p["spo2_pct"]["mean"]},
        "ecg": {"latest": latest["ecg"], "baseline": p["ecg"]},
    }


def message_patient(patient_id: str, message: str) -> dict:
    """Send a secure chat message to the patient's app. Returns the patient reply.

    The demo server intercepts this call, renders the message in the patient
    pane, and returns the scripted/live patient response.
    """
    return {"status": "delivered", "channel": "patient_app", "message": message}


def page_clinician(recipient: str, priority: str, sbar: str) -> dict:
    """Page the covering clinician with an SBAR summary. priority: routine|urgent|emergent."""
    return {
        "status": "delivered",
        "recipient": recipient,
        "priority": priority,
        "timestamp": datetime.now().isoformat(timespec="minutes"),
        "sbar": sbar,
    }


def recommend_labs(patient_id: str, panel: str, urgency: str, rationale: str) -> dict:
    """Draft a lab order recommendation for clinician sign-off (agent never signs orders)."""
    return {
        "status": "drafted_for_signoff",
        "panel": panel,
        "urgency": urgency,
        "rationale": rationale,
        "requires": "clinician co-signature",
    }


def book_appointment(patient_id: str, clinic: str, slot: str, reason: str) -> dict:
    """Book the next available clinic slot."""
    return {"status": "booked", "clinic": clinic, "slot": slot, "reason": reason}


def send_care_instructions(patient_id: str, instructions: str, return_precautions: list) -> dict:
    """Send plain-language guidance and ER return precautions to the patient app."""
    return {
        "status": "delivered",
        "instructions": instructions,
        "return_precautions": return_precautions,
    }


TOOL_FUNCTIONS = {
    "get_patient_profile": get_patient_profile,
    "get_vitals_window": get_vitals_window,
    "compare_to_baseline": compare_to_baseline,
    "message_patient": message_patient,
    "page_clinician": page_clinician,
    "recommend_labs": recommend_labs,
    "book_appointment": book_appointment,
    "send_care_instructions": send_care_instructions,
}
