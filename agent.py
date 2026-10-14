# ===== agent.py: the agent's brain =====

# ---------------------------------------------------------------
# Tools (schemas copied from ClarifyBench plugins/travel_plugin.py)
# Each parameter has a domain TYPE, like in ClarifyBench:
#   "finite"        -> a list of allowed values        -> certainty 1/n
#   "numeric_range" -> numbers between [low, high]     -> certainty 1/(high-low+1)
#   "string"        -> free text (unbounded)           -> certainty EPSILON
# ---------------------------------------------------------------
from clarifybench_travel import AIRPORTS, ROUTES     # real airports + routes from ClarifyBench
CLASSES = ["economy", "business", "first"]

tools = {
    # Travel domain (ClarifyBench)
    "get_flight_cost": {
        "travel_from":  {"type": "finite", "values": AIRPORTS},
        "travel_to":    {"type": "finite", "values": AIRPORTS},
        "travel_date":  {"type": "string"},
        "travel_class": {"type": "finite", "values": CLASSES},
    },
    "book_flight": {
        "card_id":      {"type": "string"},
        "travel_date":  {"type": "string"},
        "travel_from":  {"type": "finite", "values": AIRPORTS},
        "travel_to":    {"type": "finite", "values": AIRPORTS},
        "travel_class": {"type": "finite", "values": CLASSES},
        "travel_cost":  {"type": "numeric_range", "values": [0, 10000]},
    },
    # Restaurant domain (our simple teaching example)
    "reserve_table": {
        "day":    {"type": "finite", "values": ["Monday", "Tuesday", "Wednesday"]},
        "people": {"type": "numeric_range", "values": [1, 6]},
    },
}


# ----- Step 2: certainty score -----
EPSILON = 0.01    # SAGE: certainty of an unknown free-text parameter (very small)

# ----- Step 7 (Added Value 1): how confident is the user about a change? -----
CONFIDENCE = {"SURE": 0.95, "PREFER": 0.7, "UNSURE": 0.5}

def top(value):
    """A soft value looks like {"LAX": 0.7, "JFK": 0.3}. Its 'top' is the most likely one."""
    if isinstance(value, dict):
        return max(value, key=value.get)
    return value


def domain_size(spec):
    if spec["type"] == "finite":
        return len(spec["values"])
    if spec["type"] == "numeric_range":
        low, high = spec["values"]
        return high - low + 1
    return None                                   # "string" -> unbounded


def certainty(spec, value):
    if isinstance(value, dict):                   # soft (Step 7) -> weight of the top value
        return max(value.values())
    if value is not None:                         # known -> 1
        return 1
    size = domain_size(spec)
    if size is None:                              # unknown + unbounded -> EPSILON
        return EPSILON
    return 1 / size                               # unknown + n options -> 1/n


def is_valid(spec, value):
    if spec["type"] == "finite":
        return value in spec["values"]
    if spec["type"] == "numeric_range":
        low, high = spec["values"]
        return isinstance(value, (int, float)) and low <= value <= high
    return isinstance(value, str) and value.strip() != ""


def score(tool_name, state):
    total = 1
    for param, spec in tools[tool_name].items():
        total = total * certainty(spec, state[param])
    return total


# ----- Step 3: EVPI + penalty for repeated questions -----
PENALTY = 0.1     # SAGE: each time we already asked about a parameter, its value drops

def evpi(tool_name, state, param):
    now = score(tool_name, state)
    imagined = dict(state)            # a copy, so we don't change the real state
    imagined[param] = "ANSWERED"      # imagine the user answered this question
    after = score(tool_name, imagined)
    return after - now                # how much the score would go up


def best_question(tool_name, state, asked):
    best_param, best_value = None, 0
    for param in tools[tool_name]:
        if state[param] is None or isinstance(state[param], dict):   # unknown OR soft
            gain = evpi(tool_name, state, param)
            penalty = PENALTY * asked[param]
            value = gain - penalty
            print(f"   {param:13} EVPI={gain:.4f}  penalty={penalty:.1f}  -> {value:.4f}")
            if value > best_value:
                best_param, best_value = param, value
    return best_param                                         # None = no question is worth asking


# ----- Step 4: decide (ask, execute, or stop?) -----
THRESHOLD = 0.9    # the agent executes only if it is at least 90% sure

def decide(tool_name, state, asked):
    if score(tool_name, state) >= THRESHOLD:
        call = {p: top(v) for p, v in state.items()}
        return "EXECUTE", f"{tool_name}({call})", None
    param = best_question(tool_name, state, asked)
    if param is None:
        return "STOP", "No question is worth asking.", None
    if isinstance(state[param], dict):                       # soft -> confirmation question
        new, old = sorted(state[param], key=state[param].get, reverse=True)[:2]
        return "ASK", f"Just to confirm: {param} = {new} instead of {old}?", param
    options = options_for(tool_name, state, param)
    if options is not None:
        return "ASK", f"What is the {param}? Options: {options}", param
    return "ASK", f"What is the {param}?", param


# ----- Step 5: SAGE update (intersection) -----
MAX_QUESTIONS = 5    # question budget

def update(tool_name, state, param, value):
    """SAGE: new domain = old domain ∩ what the user said."""
    spec = tools[tool_name][param]
    if value is None:                        # "forget it": intersection cannot un-know a value
        return "CANNOT_FORGET"
    if not is_valid(spec, value):            # not an allowed value -> request is infeasible
        return "INFEASIBLE"
    if state[param] is None:                 # {all options} ∩ {value} = {value}
        state[param] = value
        return "OK"
    if state[param] == value:                # {value} ∩ {value} = {value}
        return "OK"
    return "EMPTY"                           # {old} ∩ {new} = ∅  -> broken


# ----- Step 6: the Ledger (our extension: cross out instead of intersect) -----
def new_ledger(tool_name):
    return {param: {"crossed": [], "changed_at": None, "epoch": 0}
            for param in tools[tool_name]}


def update_ledger(tool_name, state, ledger, param, value, turn, confidence=1.0):
    spec = tools[tool_name][param]
    page = ledger[param]
    current = state[param]
    if value is None:                                 # "forget it" -> retract
        if current is None:
            return "NOTHING TO FORGET"
        page["crossed"].append({"value": top(current), "turn": turn})
        state[param] = None                           # back to <UNK>
        page["changed_at"] = turn
        page["epoch"] += 1
        return "RETRACTED"
    if not is_valid(spec, value):
        return "INFEASIBLE"
    if current is None:                               # empty blank -> just fill it
        state[param] = value
        return f"ADDED {value}"
    if isinstance(current, dict) and value in current:   # user answers a confirmation question
        rejected = [v for v in current if v != value][0]
        page["crossed"] = [c for c in page["crossed"] if c["value"] != value]   # un-cross the chosen one
        page["crossed"].append({"value": rejected, "turn": turn})               # cross out the other one
        state[param] = value
        return f"CONFIRMED {value}"
    if current == value:                              # user repeated the same value
        return f"SAME {value}"
    old = top(current)                                # user changed their mind
    page["crossed"].append({"value": old, "turn": turn})   # cross out (keep it!)
    if confidence >= 1.0:
        state[param] = value                          # hard replace
    else:
        state[param] = {value: confidence, old: round(1 - confidence, 2)}   # soft replace (Step 7)
    page["changed_at"] = turn                         # tell the domino (Step 8)
    page["epoch"] += 1                                # new version of this parameter
    return f"REPLACED {old} -> {state[param]}"


def show_ledger(ledger):
    print("   --- LEDGER ---")
    for param, page in ledger.items():
        crossed = [f"{c['value']} (turn {c['turn']})" for c in page["crossed"]]
        print(f"   {param:13} crossed out: {crossed}  epoch: {page['epoch']}")


# ----- Step 8 (Added Value 2): dependencies between parameters (domino) -----
# ROUTES (all flights that exist) comes from clarifybench_travel.py

DEPENDENCIES = {                 # if this parameter changes -> re-check these ones
    "travel_from": ["travel_to"],
    "travel_to":   ["travel_from"],
}


def route_exists(state):
    frm, to = top(state.get("travel_from")), top(state.get("travel_to"))
    if frm is None or to is None:
        return True                              # nothing to check yet
    return (frm, to) in ROUTES


def options_for(tool_name, state, param):
    """The allowed values, minus the ones that would make an impossible route."""
    values = tools[tool_name][param].get("values")
    if values is None:
        return None
    if param == "travel_to" and top(state.get("travel_from")):
        return [v for v in values if (top(state["travel_from"]), v) in ROUTES]
    if param == "travel_from" and top(state.get("travel_to")):
        return [v for v in values if (v, top(state["travel_to"])) in ROUTES]
    return values


def domino(tool_name, state, ledger, asked, changed, turn):
    """After a change, check ONLY the parameters that depend on it."""
    for param in changed:
        for dep in DEPENDENCIES.get(param, []):
            if dep in state and state[dep] is not None and not route_exists(state):
                frm, to = top(state["travel_from"]), top(state["travel_to"])
                print(f"   DOMINO: {param} changed -> check {dep}: no flight {frm} -> {to} -> reopen {dep}")
                ledger[dep]["crossed"].append({"value": top(state[dep]), "turn": turn})
                ledger[dep]["changed_at"] = turn
                ledger[dep]["epoch"] += 1
                state[dep] = None                # back to <UNK>: the agent will ask about it
                asked[dep] = 0                   # a new question, not a repeat
            elif dep in state and state[dep] is not None:
                print(f"   DOMINO: {param} changed -> check {dep}: still OK")


# ----- Executing the tool (simulated, with ClarifyBench's rules) -----
def execute(tool_name, call):
    if tool_name in ("get_flight_cost", "book_flight"):
        if (call["travel_from"], call["travel_to"]) not in ROUTES:
            return {"error": "No available route for the given airports."}
        if tool_name == "get_flight_cost":
            factor = {"economy": 1, "business": 2, "first": 5}[call["travel_class"]]
            digit_sum = sum(int(ch) for ch in call["travel_date"] if ch.isdigit())
            date_factor = 2 if digit_sum % 2 == 0 else 1
            return {"travel_cost": float(ROUTES[(call["travel_from"], call["travel_to"])] * factor * date_factor)}
    return {"status": "ok"}


# ----- The versions we compare -----
METHODS = {
    "sage":              {"update": "sage"},                                    # the paper (intersection)
    "ledger":            {"update": "ledger", "confidence": False, "domino": False, "always_confirm": False},
    "ledger+confidence": {"update": "ledger", "confidence": True,  "domino": False, "always_confirm": False},
    "ledger+domino":     {"update": "ledger", "confidence": False, "domino": True,  "always_confirm": False},
    "always_confirm":    {"update": "ledger", "confidence": False, "domino": True,  "always_confirm": True},
    "ours":              {"update": "ledger", "confidence": True,  "domino": True,  "always_confirm": False},
}
MAX_TURNS = 15


# ----- The conversation loop (works for all methods) -----
def run_conversation(tool_name, user_turns, method="sage", truth=None):
    """user_turns: what the user says on their own (scripted).
       truth: if given, a simulated user answers the agent's questions with these true values."""
    cfg = METHODS[method]
    state = {param: None for param in tools[tool_name]}
    ledger = new_ledger(tool_name)
    asked = {param: 0 for param in tools[tool_name]}     # how many times we asked each parameter
    questions = 0
    pending = list(user_turns)
    last_question = None
    turn_number = 0

    while turn_number < MAX_TURNS:
        if pending:
            turn = pending.pop(0)                         # the user's own next message
        elif last_question is not None and truth is not None:
            turn = {last_question: truth[last_question]}  # simulated user answers the question
        else:
            break
        turn_number += 1
        print("USER :", turn)
        turn = dict(turn)
        category = turn.pop("confidence", "SURE")        # how sure the user sounds (from the reader)
        changed = []
        for param, value in turn.items():
            if cfg["update"] == "sage":
                result = update(tool_name, state, param, value)
                if result == "INFEASIBLE":
                    print(f"   INFEASIBLE: '{value}' is not a valid {param}.")
                    return "INFEASIBLE", state, questions
                if result == "EMPTY":
                    print(f"   BROKEN: {param} -> empty set! ({state[param]} ∩ {value} = ∅)")
                    return "BROKEN", state, questions
                if result == "CANNOT_FORGET":
                    print(f"   SAGE cannot forget {param}: keeps the old value {state[param]}")
            else:
                if cfg["always_confirm"]:
                    confidence = 0.5                      # treat every change as uncertain -> always ask
                elif cfg["confidence"]:
                    confidence = CONFIDENCE[category]     # Added Value 1
                else:
                    confidence = 1.0                      # plain ledger: always a hard replace
                result = update_ledger(tool_name, state, ledger, param, value, turn_number, confidence)
                print(f"   LEDGER: {param} {result}")
                if result == "INFEASIBLE":
                    print(f"   INFEASIBLE: '{value}' is not a valid {param}.")
                    return "INFEASIBLE", state, questions
                if result == "RETRACTED" or result.startswith("REPLACED"):
                    asked[param] = 0                      # epoch: a new question, not a repeat
                    changed.append(param)
        if cfg.get("domino") and changed:
            domino(tool_name, state, ledger, asked, changed, turn_number)   # Added Value 2

        action, text, param = decide(tool_name, state, asked)
        if action == "EXECUTE":
            call = {p: top(v) for p, v in state.items()}
            print("AGENT:", action, text)
            output = execute(tool_name, call)
            print("TOOL :", output)
            if cfg["update"] != "sage":
                show_ledger(ledger)
            if "error" in output:
                return "EXEC_ERROR", call, questions
            return "EXECUTED", call, questions
        if action == "STOP":
            print("AGENT:", text)
            return "STOP", state, questions
        if questions >= MAX_QUESTIONS:                    # no questions left -> stop
            print("   Question budget used up.")
            return "BUDGET", state, questions
        print("AGENT:", action, text)
        questions += 1
        asked[param] += 1
        last_question = param

    return "NO_MORE_TURNS", state, questions