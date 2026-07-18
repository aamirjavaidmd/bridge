# BRIDGE — an agentic member of the cardiology care team

**Bridging hospital-based care (20th-century medicine) with AI-enabled continuous home care (21st-century medicine).**

BRIDGE is an AI platform that bridges care between episodic hospital and clinic visits (20th century medicine) and continuous home-based monitoring (21st century medicine). With an initial focus on high-risk patients with chronic cardiovascular diseases (the top driver of morbidity/mortality and most expensive disease in the United States), the algorithm synthesizes insights from wearables -- such as vitals, weight, and single-lead ECG -- chat-based symptom assessment, and the patient's health record to detect disease earlier, notify the care team, and intervene to prevent hospitalizations and other adverse outcomes. This will result in improved health and lower healthcare costs. 

## The 60-second story

Maria, 67. HFrEF (EF 30%), prior STEMI with an LAD stent, CKD 3a. Discharged 5 days ago after a heart-failure exacerbation; **spironolactone was increased at discharge**. On a Saturday night:

1. **Detect** — A real analysis engine flags her data against her own 90-day baseline: resting HR +6 SD (3-day uptrend), weight +2.7 kg, SpO2 −3, HRV collapsing, and today's single-lead ECG shows a **new peaked T wave** (+0.475 mV vs the median of her prior beats). Five signals, one patient — severity **HIGH**.
2. **Investigate** — The agent pulls her profile, med list, and the computed baseline deltas.
3. **Interview** — It messages Maria: screens red flags first (no chest pain, no syncope), elicits orthopnea and worsening dyspnea, confirms adherence to the increased spironolactone.
4. **Reason** — Differential: recurrent HF exacerbation + probable hyperkalemia (MRA increase + ARNI + CKD), ischemia unlikely. Triage: **HIGH priority**.
5. **Escalate** — Maria jumps to the top of the covering NP's worklist as HIGH with the full assessment attached. The NP reviews it and — on her own authority — **orders the stat BMP + BNP and books the clinic visit herself**.
6. **Close the loop** — The agent sends Maria plain-language next steps and explicit ER return precautions.

**Outcome:** medications adjusted, potassium abnormality corrected, and a **heart-failure hospitalization avoided** — caught by continuous home monitoring while the weekend was still underway.

## Why this is agentic (not a wrapper)

- Multi-step autonomous loop: alert → investigation (3 data tools) → multi-turn patient interview → clinical reasoning → escalation → patient education.
- 8 tools with real side effects (`backend/tools.py`), orchestrated by Claude's native tool use (`backend/agent.py`).
- The agent decides *what to ask, in what order, and when to escalate* — the interview branches on red-flag answers (chest pain would short-circuit to a 911 recommendation + emergent page).

## A real analysis engine (not hardcoded numbers)

Everything the agent cites is **computed from data**, not scripted. `backend/analysis.py` reads a structured patient profile (`data/patient_profile.json` — problem list, discharge summary, med list, 90-day baselines, a home-vitals time series, and a set of dated single-lead ECG beats) and computes:

- **Per-metric deviation** vs the patient's own baseline: z-score, absolute delta, short-window trend slope, and rule-based clinical flags (e.g. weight >2 kg gain, SpO2 drop).
- **ECG morphology change**: a **median baseline beat** is built from the prior normal tracings and the most recent beat is compared against it — T-wave amplitude delta and T/R ratio — to detect a new peaked-T-wave pattern.
- **A fused alert** with an overall severity tier (LOW/MED/HIGH) and the specific supporting evidence, plus med-aware context (MRA up-titration + ARNI + CKD raises the pretest probability of hyperkalemia).

The demo data is fixed, but the code path is genuine — point the loaders at a FHIR/RPM feed and nothing else changes. The in-browser demo embeds a snapshot of the same dataset and **runs the identical analysis in JavaScript**, so the vitals tiles, deltas, and the median-beat ECG you see are computed live in the page.

## Safety by design

- The agent **never diagnoses to the patient and never changes medications**.
- Every clinical action with consequence — ordering labs, booking the visit, holding a medication — is taken by the **human clinician (the covering NP)**, never the agent.
- Red-flag symptoms bypass everything: immediate ER guidance + emergent page.
- Every escalation cites the specific data (computed deltas vs the patient's own baseline) driving it.

## Repo layout

```
backend/
  agent.py     # Claude agent loop: system prompt, tool schemas, tool-use orchestration
  analysis.py  # trend-deviation engine: z-scores, trend slopes, rule flags, median-beat ECG comparison
  tools.py     # tool implementations (wired to analysis.py; EHR/RPM/messaging/scheduling stubs)
  server.py    # FastAPI SSE server for live mode
data/
  patient_profile.json  # single source of truth: PMH, discharge summary, meds, 90-day baselines,
                        #   home-vitals series, and dated single-lead ECG beats (5 normal + 1 abnormal)
demo/
  trace.json   # recorded agent run used for deterministic replay
frontend/
  index.html   # click-driven interactive demo (patient app + care-team worklist) with a computed
               #   median-beat ECG; ?auto=1 gives the fully-timed autoplay fallback
tools/
  gen_profile.py  # regenerates data/patient_profile.json (synthetic beats are deterministic, seed=7)
```

All patient data is synthetic. No PHI anywhere in this repo.

## Run it

**Interactive demo (default — what the demo video shows):**
```
open frontend/index.html
```
Click through the story like a real product:
1. **▶ START DEMO** — the patient app opens on the alert (vitals tiles + AI flag, all computed). The agent interviews Maria; **you type her replies** (a suggested-reply chip is one click if you'd rather). It screens red flags first, then escalates her to the care team as HIGH.
2. **Care team tab** — the covering NP's risk-tiered worklist; Maria is now HIGH at the top. Click her row to open her monitoring view: computed vitals + the **median-beat ECG** (baseline vs today, with the new peaked T wave shaded).
3. **Review assessment** — reveals the agent's tool calls, its reasoning with the computed evidence, and the full patient interview.
4. **Order labs & schedule appointment** — the NP places the stat BMP + BNP and books the clinic visit herself.
5. **Send patient instructions** — closes the loop with plain-language next steps + ER precautions, then the outcome.

**Autoplay fallback (fully timed ~55-second run):**
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

The tool layer is deliberately thin: `get_vitals_window` maps to any RPM vendor API, `get_patient_profile` to a FHIR read, `page_clinician` to the clinic's secure messaging, `book_appointment` to the scheduling API — and `analysis.py` runs the same math on whatever the loaders return. Swap the stubs, keep the agent.

---
Built at the Abridge × Anthropic healthcare hackathon by Aamir Javaid, MD — cardiology fellow, UCSF.
