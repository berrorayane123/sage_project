# ===== sensitivity.py: does our result depend on the exact numbers 0.95 / 0.7 / 0.5? =====
import io, json, contextlib
import agent
from agent import run_conversation

cases = [c for c in json.load(open("clarifybench_revise.json", encoding="utf-8")) if c["kind"] != "explicit"]

SETTINGS = [                      # (SURE, PREFER, UNSURE)
    (0.95, 0.70, 0.50),           # the values we use
    (0.95, 0.60, 0.40),
    (0.95, 0.80, 0.60),
    (0.99, 0.85, 0.50),
    (0.91, 0.75, 0.55),
    (0.95, 0.70, 0.92),           # broken on purpose: UNSURE above the 0.9 threshold
]

print(f"{'SURE':>6} {'PREFER':>7} {'UNSURE':>7} | {'correct':>8} {'avg_q':>6}")
for sure, prefer, unsure in SETTINGS:
    agent.CONFIDENCE.update({"SURE": sure, "PREFER": prefer, "UNSURE": unsure})
    correct, questions = 0, 0
    for c in cases:
        with contextlib.redirect_stdout(io.StringIO()):
            status, call, q = run_conversation("get_flight_cost", c["turns"], "ours", truth=c["truth"])
        correct += status == "EXECUTED" and call == c["truth"]
        questions += q
    note = "   <- broken on purpose" if unsure > agent.THRESHOLD else ""
    print(f"{sure:6.2f} {prefer:7.2f} {unsure:7.2f} | {100 * correct / len(cases):7.1f}% {questions / len(cases):6.2f}{note}")