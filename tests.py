# ===== tests.py: many test cases for our SAGE reproduction (Phase 4) =====
import io, contextlib
from agent import run_conversation, score, evpi, tools, EPSILON, AIRPORTS

passed, failed = 0, 0

def check(name, got, expected):
    global passed, failed
    ok = got == expected
    passed += ok
    failed += (not ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"   got={got}  expected={expected}"))

def quiet_run(tool, turns, method):
    with contextlib.redirect_stdout(io.StringIO()):       # hide the conversation printing
        return run_conversation(tool, turns, method)


print("===== A. Math checks (score + EVPI, like the paper) =====")
empty = {p: None for p in tools["get_flight_cost"]}
n = len(AIRPORTS)   # 24 airports in ClarifyBench
check("A1 score, nothing known = 1/24*1/24*1/3*eps", round(score("get_flight_cost", empty), 12), round(1/(n*n*3)*EPSILON, 12))
check("A2 score, all known = 1", score("get_flight_cost", {"travel_from": "SFO", "travel_to": "JFK", "travel_date": "x", "travel_class": "first"}), 1)
check("A3 free-text param has the biggest EVPI", max(empty, key=lambda p: evpi("get_flight_cost", empty, p)), "travel_date")
r = {"day": None, "people": None}
check("A4 restaurant EVPI(people) = 0.278", round(evpi("reserve_table", r, "people"), 3), 0.278)
check("A5 restaurant EVPI(day) = 0.111", round(evpi("reserve_table", r, "day"), 3), 0.111)

full = {"travel_from": "SFO", "travel_to": "JFK", "travel_date": "2026-11-05", "travel_class": "economy"}

print()
print("===== B. Explicit requests: everything given -> execute with 0 questions =====")
for i, (frm, to, cls) in enumerate([("SFO", "JFK", "economy"), ("LAX", "BOS", "first"), ("ORD", "LAX", "business")], 1):
    turn = {"travel_from": frm, "travel_to": to, "travel_date": "2026-11-05", "travel_class": cls}
    check(f"B{i} {frm}->{to} {cls}", quiet_run("get_flight_cost", [turn], "sage")[0], "EXECUTED")

print()
print("===== C. Ambiguous requests: info comes step by step -> ask, then execute =====")
check("C1 nothing, then everything", quiet_run("get_flight_cost", [{}, full], "sage")[0], "EXECUTED")
check("C2 one value per turn", quiet_run("get_flight_cost", [{}, {"travel_date": "2026-11-05"}, {"travel_from": "SFO"}, {"travel_to": "JFK"}, {"travel_class": "economy"}], "sage")[0], "EXECUTED")
check("C3 user never answers -> penalty makes it stop asking", quiet_run("get_flight_cost", [{}] * 10, "sage")[0], "STOP")
check("C4 restaurant: day then people", quiet_run("reserve_table", [{}, {"people": 4}, {"day": "Tuesday"}], "sage")[0], "EXECUTED")

print()
print("===== D. Infeasible requests: invalid value -> infeasible =====")
check("D1 airport that does not exist (XYZ)", quiet_run("get_flight_cost", [{"travel_to": "XYZ"}], "sage")[0], "INFEASIBLE")
check("D2 class that does not exist", quiet_run("get_flight_cost", [{"travel_class": "premium"}], "sage")[0], "INFEASIBLE")
check("D3 too many people (9)", quiet_run("reserve_table", [{"people": 9}], "sage")[0], "INFEASIBLE")
check("D4 ledger also detects infeasible", quiet_run("get_flight_cost", [{"travel_to": "XYZ"}], "ledger")[0], "INFEASIBLE")

print()
print("===== E. Revisions: SAGE breaks, the ledger handles them =====")
rev_to = [{}, {"travel_date": "2026-11-05", "travel_from": "SFO", "travel_to": "JFK"}, {"travel_class": "business", "travel_to": "LAX"}]
check("E1 SAGE: change destination -> BROKEN", quiet_run("get_flight_cost", rev_to, "sage")[0], "BROKEN")
check("E2 Ledger: change destination -> EXECUTED", quiet_run("get_flight_cost", rev_to, "ledger")[0], "EXECUTED")
check("E3 Ledger: uses the NEW value (LAX)", quiet_run("get_flight_cost", rev_to, "ledger")[1]["travel_to"], "LAX")
rev_cls = [{"travel_from": "SFO", "travel_to": "JFK"}, {"travel_class": "economy"}, {"travel_class": "first", "travel_date": "2026-11-05"}]
check("E4 SAGE: change class -> BROKEN", quiet_run("get_flight_cost", rev_cls, "sage")[0], "BROKEN")
check("E5 Ledger: change class -> uses 'first'", quiet_run("get_flight_cost", rev_cls, "ledger")[1]["travel_class"], "first")
rev_rest = [{"people": 4}, {"people": 6, "day": "Tuesday"}]
check("E6 SAGE restaurant: 4 -> 6 people -> BROKEN", quiet_run("reserve_table", rev_rest, "sage")[0], "BROKEN")
check("E7 Ledger restaurant: 4 -> 6 people -> 6", quiet_run("reserve_table", rev_rest, "ledger")[1]["people"], 6)

print()
print("===== F. Retraction ('forget it'): SAGE keeps a stale value, the ledger re-asks =====")
retract = [{"travel_from": "SFO", "travel_to": "JFK", "travel_class": "economy"}, {"travel_to": None}, {"travel_to": "BOS", "travel_date": "2026-11-05"}]
check("F1 SAGE: still uses the forgotten JFK", quiet_run("get_flight_cost", retract, "sage")[1]["travel_to"], "JFK")
check("F2 Ledger: uses BOS after re-asking", quiet_run("get_flight_cost", retract, "ledger")[1]["travel_to"], "BOS")

print()
print("===== G. Added Value 1: confidence (SURE / PREFER / UNSURE) =====")
start = [{}, {"travel_date": "2026-11-05", "travel_from": "SFO", "travel_to": "JFK"}]
def change(cat): return {"travel_class": "business", "travel_to": "LAX", "confidence": cat}
confirm_lax = {"travel_to": "LAX"}
confirm_jfk = {"travel_to": "JFK"}

s, call, q = quiet_run("get_flight_cost", start + [change("SURE")], "ours")
check("G1 SURE -> executes without asking", s, "EXECUTED")
check("G2 SURE -> uses LAX", call["travel_to"], "LAX")

s, call, q = quiet_run("get_flight_cost", start + [change("PREFER")], "ours")
check("G3 PREFER -> does NOT execute yet (asks to confirm)", s, "NO_MORE_TURNS")
s, call, q = quiet_run("get_flight_cost", start + [change("PREFER"), confirm_lax], "ours")
check("G4 PREFER + user confirms LAX -> LAX", call["travel_to"], "LAX")
s, call, q = quiet_run("get_flight_cost", start + [change("PREFER"), confirm_jfk], "ours")
check("G5 PREFER + user goes back to JFK -> JFK", call["travel_to"], "JFK")

s, call, q = quiet_run("get_flight_cost", start + [change("UNSURE")], "ours")
check("G6 UNSURE -> asks to confirm", s, "NO_MORE_TURNS")

s, call, q = quiet_run("get_flight_cost", start + [change("UNSURE")], "ledger")
check("G7 Ledger only (no confidence) -> guesses LAX without asking", (s, call["travel_to"]), ("EXECUTED", "LAX"))
s, call, q = quiet_run("get_flight_cost", start + [change("UNSURE"), confirm_jfk], "ledger")
check("G8 Ledger only -> wrong call when user really wanted JFK", call["travel_to"], "LAX")
s, call, q = quiet_run("get_flight_cost", start + [change("UNSURE"), confirm_jfk], "ours")
check("G9 Ours -> right call (JFK)", call["travel_to"], "JFK")

print()
print("===== H. Added Value 2: domino (dependencies between parameters) =====")
from agent import options_for
base = [{}, {"travel_date": "2026-11-05", "travel_from": "SFO", "travel_to": "JFK"}]
move_origin = {"travel_class": "business", "travel_from": "ORD"}         # ORD -> JFK does not exist!
s, call, q = quiet_run("get_flight_cost", base + [move_origin], "ledger")
check("H1 Ledger only: executes ORD->JFK -> tool error", s, "EXEC_ERROR")
s, call, q = quiet_run("get_flight_cost", base + [move_origin], "ours")
check("H2 Ours: detects the broken route and asks (no execution)", s, "NO_MORE_TURNS")
s, call, q = quiet_run("get_flight_cost", base + [move_origin, {"travel_to": "LAX"}], "ours")
check("H3 Ours + user picks LAX -> executes ORD->LAX", (s, call["travel_from"], call["travel_to"]), ("EXECUTED", "ORD", "LAX"))
opts = options_for("get_flight_cost", {"travel_from": "ORD", "travel_to": None}, "travel_to")
check("H4 Ours never offers an impossible destination (JFK) from ORD", ("JFK" in opts, "LAX" in opts), (False, True))
ok_base = [{}, {"travel_date": "2026-11-05", "travel_from": "SFO", "travel_to": "LAX"}]
s1, c1, q1 = quiet_run("get_flight_cost", ok_base + [{"travel_class": "economy", "travel_from": "JFK"}], "ledger")
s2, c2, q2 = quiet_run("get_flight_cost", ok_base + [{"travel_class": "economy", "travel_from": "JFK"}], "ours")
check("H5 Route still OK (JFK->LAX): ours asks NO extra question", (s2, q2), (s1, q1))

print()
print(f"===== TOTAL: {passed} passed, {failed} failed =====")