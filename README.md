# BRIDGE — an agentic member of the cardiology care team

**Bridging hospital-based care (20th-century medicine) with AI-enabled continuous home care (21st-century medicine).**

Heart failure is the #1 cause of readmission in US medicine. The most dangerous window is the first two weeks after discharge — and the most dangerous hours are nights and weekends, when no one is watching the home-monitoring data. BRIDGE is an autonomous agent that watches, investigates, interviews the patient, escalates to a human clinician, and closes the loop — end to end.

## The 60-second story

Maria, 67. HFrEF (EF 30%), prior STEMI with an LAD stent, CKD 3a. Discharged 5 days ago after a heart-failure exacerbation; **spironolactone was increased at discharge**. On a Saturday night at 21:40:

1. **Detect** — Her resting HR is +6 SD above her own 90-day baseline (3-day uptrend), weight is up 2.7 kg in 5 days, SpO2 has dropped, and today's single-lead ECG shows **new peaked T waves**.
2. **Investigate** — The agent pulls her profile, med list, and baseline deltas.
3. **Interview** — It messages Maria: screens red flags first (no chest pain, no syncope), elicits orthopnea and worsening dyspnea, confirms adherence to the increased spironolactone.
4. **Reason** — Differential: recurrent HF exacerbation + probable hyperkalemia (MRA increase + ARNI + CKD), ischemia unlikely. Triage: urgent, not emergent.
5. **Escalate** — Pages the covering NP with a tight SBAR, drafts a stat BMP + BNP **for clinician co-signature**, and books Monday's first clinic slot.
6. **Close the loop** — Sends Maria plain-language next steps and explicit ER return precautions.

Throughout, the covering NP's view is a **panel worklist**: every monitored patient, risk-tiered by the agent (LOW / MED / HIGH). When the agent escalates, Maria's row jumps to the top as HIGH with the full assessment attached — the NP logs in Monday to a prioritized queue, not a pile of raw telemetry.

**Outcome:** Monday clinic. K+ 5.8. Spironolactone held, furosemide doubled. **A readmission averted — caught on a Saturday night, treated in clinic on Monday.**

## Why this is agentic (not a wrapper)

- Multi-step autonomous loop: alert → investigation (3 data tools) → multi-turn patient interview → clinical reasoning → escalation → scheduling → patient education.
- 8 tools with real side effects (`backend/tools.py`), orchestrated by Claude's native tool use (`backend/agent.py`).
- The agent decides *what to ask, in what order, and when to escalate* — the interview branches on red-flag answers (chest pain would short-circuit to a 911 recommendation + emergent page).

## Safety by design

- The agent **never diagnoses to the patient and never changes medications**.
- Lab orders are **drafts requiring clinician co-signature** — a human is always in the loop for anything with clinical consequence.
- Red-flag symptoms bypass everything: immediate ER guidance + emergent page.
- Every escalation cites the specific data (deltas vs the patient's own baseline) driving it.

## Repo layout

```
backend/
  agent.py     # Claude agent loop: system prompt, tool schemas, tool-use orchestration
  tools.py     # tool implementations (EHR/RPM/messaging/scheduling stubs)
  server.py    # FastAPI SSE server for live mode
data/
  patient.json        # synthetic patient: profile, meds, discharge summary, 90-day baselines
  vitals_stream.json  # 5-day post-discharge home-monitoring stream
demo/
  trace.json   # recorded agent run used for deterministic replay
frontend/
  index.html   # click-driven interactive demo (patient app + care-team worklist) with live ECG morphing; ?auto=1 for timed autoplay
```

All patient data is synthetic. No PHI anywhere in this repo.

## Run it

**Interactive demo (default — what the demo video shows):**
```
open frontend/index.html
```
Click through the story like a real product:
1. **▶ START DEMO** — the patient app opens on the alert; the agent interviews Maria (red flags first), then escalates.
2. **Care team tab** — the covering NP's risk-tiered worklist; click **Alvarez, Maria** to open her monitoring view (vitals + live ECG morphing to peaked T waves).
3. **Review assessment** — reveals the agent's tool calls, reasoning, and the full patient interview.
4. **Page covering clinician** — sends the SBAR and flips Maria to HIGH on the worklist.
5. **Send patient instructions** — closes the loop with plain-language next steps + ER precautions.

**Autoplay fallback (fully timed ~60-second run):**
```
open frontend/index.html?auto=1   # click ▶ PLAY DEMO
```

**Live mode (real Claude agent loop):**
```
cd backend
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...
uvicorn server:app --port 8000
# open frontend/index.html and click LIVE MODE
```

## What Monday looks like

The tool layer is deliberately thin: `get_vitals_window` maps to any RPM vendor API, `get_patient_profile` to a FHIR read, `page_clinician` to the clinic's secure messaging, `book_appointment` to the scheduling API. Swap the stubs, keep the agent.

---
Built at the Abridge × Anthropic healthcare hackathon by Aamir Javaid, MD — cardiology fellow, UCSF.
