# ===== chat.py: LIVE demo - type anything, the agent answers =====
#   python chat.py          -> our full method
#   python chat.py sage     -> original SAGE (to show it breaking)
#   add "offline" to use the backup reader instead of Gemini:  python chat.py ours offline
import sys
from agent import (tools, METHODS, CONFIDENCE, new_ledger, update, update_ledger, domino,
                   decide, execute, top, show_ledger)
from reader import read_message, simple_reader

TOOL = "get_flight_cost"
OFFLINE = "offline" in sys.argv                    # no internet / Google busy -> backup reader
args = [a for a in sys.argv[1:] if a != "offline"]
method = args[0] if args else "ours"
cfg = METHODS[method]

state = {p: None for p in tools[TOOL]}
ledger = new_ledger(TOOL)
asked = {p: 0 for p in tools[TOOL]}
last_question, turn_number = None, 0

print(f"=== Flight assistant ({method}{', offline reader' if OFFLINE else ''}) - type 'quit' to stop ===")
while True:
    message = input("\nYOU  : ").strip()
    if message.lower() in ("quit", "exit"):
        break
    turn_number += 1
    known = {p: top(v) for p, v in state.items()}
    turn = simple_reader(message, known) if OFFLINE else read_message(message, known, last_question)
    print(f"   (reader: {turn})")
    category = turn.pop("confidence", "SURE")
    changed = []
    broken = False
    for param, value in turn.items():
        if cfg["update"] == "sage":
            result = update(TOOL, state, param, value)
            if result == "EMPTY":
                print(f"   BROKEN: {param} -> {state[param]} ∩ {value} = ∅   (SAGE cannot change a value)")
                broken = True
            elif result == "CANNOT_FORGET":
                print(f"   SAGE cannot forget {param}: keeps {state[param]}")
            elif result == "INFEASIBLE":
                print(f"   '{value}' is not a valid {param}.")
        else:
            confidence = 0.5 if cfg["always_confirm"] else (CONFIDENCE[category] if cfg["confidence"] else 1.0)
            result = update_ledger(TOOL, state, ledger, param, value, turn_number, confidence)
            print(f"   LEDGER: {param} {result}")
            if result == "RETRACTED" or result.startswith("REPLACED"):
                asked[param] = 0
                changed.append(param)
    if broken:
        print("AGENT: Sorry, I'm stuck. (This is the SAGE limitation.)")
        break
    if cfg.get("domino") and changed:
        domino(TOOL, state, ledger, asked, changed, turn_number)

    print(f"   STATE: {state}")
    action, text, param = decide(TOOL, state, asked)
    if action == "EXECUTE":
        call = {p: top(v) for p, v in state.items()}
        print("AGENT: OK!", text)
        print("TOOL :", execute(TOOL, call))
        if cfg["update"] != "sage":
            show_ledger(ledger)
        break
    if action == "STOP":
        print("AGENT:", text)
        break
    print("AGENT:", text)
    asked[param] += 1
    last_question = text