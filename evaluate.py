# ===== evaluate.py: runs every version on ClarifyBench-Revise and prints the result tables =====
import io, json, csv, contextlib
from agent import run_conversation

METHODS = ["sage", "ledger", "ledger+confidence", "ledger+domino", "always_confirm", "ours"]
cases = json.load(open("clarifybench_revise.json", encoding="utf-8"))


def run_case(case, method):
    with contextlib.redirect_stdout(io.StringIO()):                 # hide the conversation printing
        status, call, questions = run_conversation("get_flight_cost", case["turns"], method, truth=case["truth"])
    correct = status == "EXECUTED" and call == case["truth"]
    stale = (case["old_value"] is not None and call.get(case["changed_param"]) == case["old_value"]
             and case["truth"][case["changed_param"]] != case["old_value"])
    return {"id": case["id"], "kind": case["kind"], "method": method, "status": status,
            "correct": int(correct), "stale": int(stale), "exec_error": int(status == "EXEC_ERROR"),
            "broken": int(status == "BROKEN"), "questions": questions}


rows = [run_case(c, m) for c in cases for m in METHODS]
with open("results.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)


def table(title, kinds):
    print(f"\n{title}")
    print(f"{'method':20} {'n':>4} {'correct':>9} {'stale':>7} {'exec_err':>9} {'broken':>7} {'avg_q':>6}")
    for m in METHODS:
        r = [x for x in rows if x["method"] == m and x["kind"] in kinds]
        n = len(r)
        pct = lambda key: f"{100 * sum(x[key] for x in r) / n:6.1f}%"
        avg_q = sum(x["questions"] for x in r) / n
        print(f"{m:20} {n:>4} {pct('correct'):>9} {pct('stale'):>7} {pct('exec_error'):>9} {pct('broken'):>7} {avg_q:6.2f}")


table("TABLE 1 - Normal conversations (no change of mind): our extension must NOT hurt",
      ["explicit", "normal"])
table("TABLE 2 - All conversations where the user changes their mind",
      ["revise_sure", "revise_prefer", "revise_unsure_new", "revise_unsure_old", "retract", "domino"])
for kind in ["revise_sure", "revise_prefer", "revise_unsure_new", "revise_unsure_old", "retract", "domino"]:
    table(f"  by type: {kind}", [kind])
print("\nAll rows saved in results.csv")