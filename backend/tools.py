"""Tool implementations for the BRIDGE cardiology agent.

In the hackathon build, patient data comes from synthetic JSON and the
patient/NP conversations are relayed through the demo UI over SSE. In a
production build these would hit the EHR (FHIR), the RPM vendor API, and
the clinic's secure messaging + scheduling systems.
"""

import json
from pathlib import Path
from datetime import datetime

import analysis

DATA = Path(__file__).resolve().parent.parent / "data"


def _load(name: str) -> dict:
    return json.loads((DATA / name).read_text())


def get_patient_profile(patient_id: str) -> dict:
    """Demographics, problem list, meds, discharge summary, 90-day baselines, devices."""
    p = analysis.load_profile()
    return {k: v for k, v in p.items() if k != "ecg_beats"}  # beats are large; fetched via ECG analysis


def get_vitals_window(patient_id: str, days: int = 5) -> dict:
    """Recent home-monitoring stream plus the per-metric deviation computed vs baseline."""
    p = analysis.load_profile()
    return {
        "window": p["home_vitals"][-days:],
        "deviations": analysis.analyze_vitals(p),
    }


def compare_to_baseline(patient_id: str) -> dict:
    """Real trend-deviation analysis: per-metric z-scores/trends + ECG morphology delta.

    Delegates to analysis.summarize(), which computes everything from the
    patient profile (see backend/analysis.py). ECG sample arrays are stripped
    from the tool result to keep it compact for the model.
    """
    s = analysis.summarize(analysis.load_profile())
    s["ecg"] = {k: v for k, v in s["ecg"].items() if k not in ("baseline_beat", "recent_beat")}
    return s


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
