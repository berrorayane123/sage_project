# ===== build_revise.py: builds "ClarifyBench-Revise" from the real ClarifyBench Travel tasks =====
# For every real get_flight_cost task in ClarifyBench (splits A and E), we keep the TRUE call
# and create several conversations around it: normal ones, and ones where the user changes their mind.
import json, glob, os, sys
from clarifybench_travel import AIRPORTS, ROUTES

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join("ClarifyBench", "ClarifyBench")
CLASSES = ["economy", "business", "first"]
PARAMS = ["travel_to", "travel_class", "travel_date", "travel_from"]     # which parameter the user revises


def load_tasks():
    tasks, seen = [], set()
    for split in ["A", "E"]:
        for path in sorted(glob.glob(os.path.join(DATA_DIR, f"ClarifyBench_{split}", "*.json"))):
            data = json.load(open(path, encoding="utf-8"))
            if data.get("primary_api") != "TravelAPI":
                continue
            for call in data["ground_truth_tool_calls"]:
                if call["tool_name"] != "get_flight_cost":
                    continue
                p = call["parameters"]
                truth = {k: p[k] for k in ["travel_from", "travel_to", "travel_date", "travel_class"]}
                key = tuple(truth.values())
                if key not in seen:
                    seen.add(key)
                    tasks.append({"source": f"{split}/{os.path.basename(path)}",
                                  "user_query": data["user_query"], "truth": truth})
    return tasks


def wrong_value(param, truth):
    """A different, valid value (that keeps the route possible), used as the 'old' value."""
    if param == "travel_class":
        return [c for c in CLASSES if c != truth["travel_class"]][0]
    if param == "travel_date":
        return "2024-12-25" if truth["travel_date"] != "2024-12-25" else "2024-12-26"
    if param == "travel_to":
        return [a for a in AIRPORTS if a != truth["travel_to"] and (truth["travel_from"], a) in ROUTES][0]
    if param == "travel_from":
        return [a for a in AIRPORTS if a != truth["travel_from"] and (a, truth["travel_to"]) in ROUTES][0]


def domino_case(truth):
    """Old trip (F_old -> T_old) is fine, but after the user moves the origin to F, F -> T_old does not exist."""
    F, T = truth["travel_from"], truth["travel_to"]
    for t_old in AIRPORTS:
        if t_old == T or (F, t_old) in ROUTES:
            continue
        for f_old in AIRPORTS:
            if f_old != F and (f_old, t_old) in ROUTES:
                return f_old, t_old
    return None


def build():
    cases = []
    for i, task in enumerate(load_tasks()):
        t = task["truth"]
        X = PARAMS[i % len(PARAMS)]                       # the parameter this task revises
        old = wrong_value(X, t)
        route = {"travel_from": t["travel_from"], "travel_to": t["travel_to"]}
        first = {**route, X: old}                         # first message, with the OLD value of X

        def add(kind, turns, truth, changed=None, old_value=None):
            cases.append({"id": f"{i:03d}-{kind}", "task": i, "kind": kind, "source": task["source"],
                          "user_query": task["user_query"], "turns": turns, "truth": truth,
                          "changed_param": changed, "old_value": old_value})

        add("explicit", [dict(t)], t)                                             # everything at once
        add("normal", [dict(route)], t)                                           # the rest is asked
        add("revise_sure", [first, {X: t[X], "confidence": "SURE"}], t, X, old)   # "Actually, X"
        add("revise_prefer", [first, {X: t[X], "confidence": "PREFER"}], t, X, old)   # "X would be better"
        add("revise_unsure_new", [first, {X: t[X], "confidence": "UNSURE"}], t, X, old)  # "maybe X?" (wants new)
        add("revise_unsure_old", [{**route, X: t[X]}, {X: old, "confidence": "UNSURE"}], t, X, old)  # "maybe X?" (keeps old)
        add("retract", [first, {X: None}], t, X, old)                             # "forget X"
        d = domino_case(t)
        if d:
            f_old, t_old = d
            add("domino", [{"travel_from": f_old, "travel_to": t_old},
                           {"travel_from": t["travel_from"], "confidence": "SURE"}], t, "travel_to", t_old)
    return cases


if __name__ == "__main__":
    cases = build()
    json.dump(cases, open("clarifybench_revise.json", "w", encoding="utf-8"), indent=1)
    kinds = {}
    for c in cases:
        kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
    print(f"Built {len(cases)} conversations from {len({c['task'] for c in cases})} real ClarifyBench tasks:")
    for k, v in kinds.items():
        print(f"   {k:20} {v}")