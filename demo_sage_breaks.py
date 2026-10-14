# ===== demo_sage_breaks.py: shows SAGE's limitation (keep this file!) =====
from agent import run_conversation

print("========== Conversation 1: normal user -> SAGE works ==========")
print("RESULT:", run_conversation("get_flight_cost", [
    {},                                                                  # "How much is a flight?"
    {"travel_date": "2026-11-05", "travel_from": "SFO", "travel_to": "JFK"},  # "Nov 5th, SFO to JFK"
    {"travel_class": "business"},                                        # "Business"
], method="sage"))

print()
print("========== Conversation 2: user changes their mind -> SAGE breaks ==========")
print("RESULT:", run_conversation("get_flight_cost", [
    {},
    {"travel_date": "2026-11-05", "travel_from": "SFO", "travel_to": "JFK"},
    {"travel_class": "business", "travel_to": "LAX"},                    # "Business. Actually, to LAX instead."
], method="sage"))

print()
print("========== Conversation 3: user says 'forget it' -> SAGE keeps a stale value ==========")
print("RESULT:", run_conversation("get_flight_cost", [
    {"travel_from": "SFO", "travel_to": "JFK", "travel_class": "economy"},
    {"travel_to": None},                                                 # "Forget the destination I gave you"
    {"travel_to": "BOS", "travel_date": "2026-11-05"},
], method="sage"))
