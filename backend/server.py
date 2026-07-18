"""Live-mode server: streams real agent events to the demo UI over SSE.

Usage:
    export ANTHROPIC_API_KEY=sk-...
    uvicorn server:app --reload
    # then open frontend/index.html and click "Live mode"

The frontend defaults to replay mode (demo/trace.json) so the 60-second
video is deterministic; live mode proves the loop is real.
"""

import json
import queue
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import agent

app = FastAPI(title="BRIDGE agent server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/run")
def run_agent():
    q: "queue.Queue[dict|None]" = queue.Queue()

    def event_fn(evt):
        q.put(evt)

    def worker():
        try:
            agent.run(event_fn=event_fn)
        except Exception as e:  # surface errors to the UI
            q.put({"type": "error", "text": str(e)})
        q.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def stream():
        while True:
            evt = q.get()
            if evt is None:
                break
            yield f"data: {json.dumps(evt)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
