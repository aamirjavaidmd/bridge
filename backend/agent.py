"""BRIDGE — an agentic member of the cardiology care team.

Agent loop: an alert from the home-monitoring pipeline triggers the agent,
which investigates (pulls profile, vitals, baseline deltas), interviews the
patient over secure chat, forms a differential, escalates to the covering
clinician with an SBAR, drafts lab orders for co-signature, books follow-up,
and closes the loop with plain-language return precautions.

Safety rails (enforced in the system prompt and tool design):
  * The agent NEVER diagnoses to the patient or changes medications.
  * Lab orders are drafts requiring clinician co-signature.
  * Any red-flag symptom (chest pain, syncope, severe dyspnea) short-circuits
    to a 911/ER recommendation and an emergent page.
"""

import json
import anthropic

from tools import TOOL_FUNCTIONS

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
You are BRIDGE, an agentic member of a cardiology care team at an academic
medical center. You monitor recently discharged heart-failure patients via
home devices (BP cuff, scale, pulse ox, wearable HR, single-lead ECG).

When the monitoring pipeline raises an alert, you:
1. Pull the patient profile, recent vitals, and baseline comparison.
2. Interview the patient over secure chat: brief, warm, one question at a
   time, 6th-grade reading level. Screen for red flags first
   (chest pain, syncope, severe shortness of breath at rest).
3. Form a differential diagnosis with supporting evidence.
4. Escalate to the covering clinician with a tight SBAR. Recommend labs
   (draft only — clinician must co-sign) and book appropriate follow-up.
5. Close the loop with the patient: what happens next, and explicit
   ER return precautions.

Hard rules:
- You never tell the patient a diagnosis or change medications.
- Red-flag symptoms => advise calling 911 / going to the ER now and page
  the clinician emergently.
- Every escalation names the specific data (deltas vs baseline) driving it.
- Be concise. Clinicians get SBAR; patients get plain language.
"""

TOOLS = [
    {
        "name": "get_patient_profile",
        "description": "Demographics, problem list, medications, recent discharge summary, and 90-day home-monitoring baselines.",
        "input_schema": {
            "type": "object",
            "properties": {"patient_id": {"type": "string"}},
            "required": ["patient_id"],
        },
    },
    {
        "name": "get_vitals_window",
        "description": "Recent home-monitoring stream: resting HR, BP, SpO2, weight, single-lead ECG findings.",
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "days": {"type": "integer", "default": 5},
            },
            "required": ["patient_id"],
        },
    },
    {
        "name": "compare_to_baseline",
        "description": "Deviations of latest readings vs the patient's own 90-day baseline (z-scores, deltas, thresholds).",
        "input_schema": {
            "type": "object",
            "properties": {"patient_id": {"type": "string"}},
            "required": ["patient_id"],
        },
    },
    {
        "name": "message_patient",
        "description": "Send one secure-chat message to the patient. Returns the patient's reply. Ask ONE question per call.",
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "message": {"type": "string"},
            },
            "required": ["patient_id", "message"],
        },
    },
    {
        "name": "page_clinician",
        "description": "Page the covering clinician with an SBAR summary.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipient": {"type": "string"},
                "priority": {"type": "string", "enum": ["routine", "urgent", "emergent"]},
                "sbar": {"type": "string"},
            },
            "required": ["recipient", "priority", "sbar"],
        },
    },
    {
        "name": "recommend_labs",
        "description": "Draft a lab order for clinician co-signature. The agent cannot sign orders.",
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "panel": {"type": "string"},
                "urgency": {"type": "string", "enum": ["routine", "next-day", "stat"]},
                "rationale": {"type": "string"},
            },
            "required": ["patient_id", "panel", "urgency", "rationale"],
        },
    },
    {
        "name": "book_appointment",
        "description": "Book the next available clinic slot for the patient.",
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "clinic": {"type": "string"},
                "slot": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["patient_id", "clinic", "slot", "reason"],
        },
    },
    {
        "name": "send_care_instructions",
        "description": "Send plain-language next steps and explicit ER return precautions to the patient app.",
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "instructions": {"type": "string"},
                "return_precautions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["patient_id", "instructions", "return_precautions"],
        },
    },
]

ALERT = """\
ALERT [2026-07-18 21:40, Saturday] — patient PT-1042 (Maria Alvarez), day 5
post-discharge from ADHF admission.
Monitoring pipeline flags: resting HR 92 (90-day mean 68, +6.0 SD, 3-day
uptrend), weight +2.7 kg over 5 days, SpO2 94% (baseline 97%), and today's
single-lead ECG shows NEW tall, narrow, symmetric (peaked) T waves vs a
normal baseline morphology. Investigate and act.
"""


def run(patient_reply_fn=None, event_fn=print):
    """Run the agent loop.

    patient_reply_fn: callable(message)->str, supplies patient chat replies
      (the demo server wires this to the UI; defaults to canned replies).
    event_fn: callback for streaming events (thoughts, tool calls, results).
    """
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": ALERT}]

    canned = iter([
        "No chest pain, no. I just feel more short of breath than usual today.",
        "Yes — last two nights I had to sleep sitting up in the recliner. Lying flat makes it hard to breathe.",
        "No fainting or dizziness. My legs look a little puffier than last week.",
        "Yes, I've been taking everything, including the new water pill dose they changed at the hospital.",
    ])

    def patient_reply(msg):
        if patient_reply_fn:
            return patient_reply_fn(msg)
        return next(canned, "Okay, thank you.")

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        for block in response.content:
            if block.type == "text" and block.text.strip():
                event_fn({"type": "agent_thought", "text": block.text})

        if response.stop_reason != "tool_use":
            break

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            event_fn({"type": "tool_call", "name": block.name, "input": block.input})
            fn = TOOL_FUNCTIONS[block.name]
            result = fn(**block.input)
            if block.name == "message_patient":
                reply = patient_reply(block.input["message"])
                result["patient_reply"] = reply
                event_fn({"type": "patient_reply", "text": reply})
            event_fn({"type": "tool_result", "name": block.name, "result": result})
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                }
            )
        messages.append({"role": "user", "content": tool_results})

    event_fn({"type": "done"})
    return messages


if __name__ == "__main__":
    run()
