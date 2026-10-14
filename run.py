# ===== run.py: Step 8 - Added Value 2 (domino) =====
from agent import run_conversation

# The user changes the ORIGIN airport. But there is no flight ORD -> JFK (ClarifyBench's real route table)!
user_turns = [
    {},                                                                        # "How much is a flight?"
    {"travel_date": "2026-11-05", "travel_from": "SFO", "travel_to": "JFK"},   # "Nov 5th, SFO to JFK"
    {"travel_class": "business", "travel_from": "ORD"},                        # "Business. Actually I'll leave from Chicago (ORD)."
    {"travel_to": "LAX"},                                                      # (if asked) "OK, then LAX."
]

print("########## SAGE + LEDGER (no dependency check) ##########")
status, call, q = run_conversation("get_flight_cost", user_turns, method="ledger")
print(f"=> {status} | {call['travel_from']} -> {call['travel_to']} | questions = {q}")

print()
print("########## OURS (ledger + confidence + domino) ##########")
status, call, q = run_conversation("get_flight_cost", user_turns, method="ours")
print(f"=> {status} | {call['travel_from']} -> {call['travel_to']} | questions = {q}")