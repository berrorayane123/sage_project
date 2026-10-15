import json

def airport_text(code):
    return code

def turn_to_sentence(turn):
    origin = turn.get("travel_from")
    destination = turn.get("travel_to")

     # Retraction
    if "travel_to" in turn and turn["travel_to"] is None:
        return "Actually, forget my destination."

    if "travel_from" in turn and turn["travel_from"] is None:
        return "Actually, forget my departure."

    if "travel_date" in turn and turn["travel_date"] is None:
        return "Actually, forget my travel date."

    if "travel_class" in turn and turn["travel_class"] is None:
        return "Actually, forget my travel class."

    # Full origin + destination turn
    if origin and destination:
        sentence = f"I want to fly from {airport_text(origin)} to {airport_text(destination)}"

        if turn.get("travel_date"):
            sentence += f" on {turn['travel_date']}"

        if turn.get("travel_class"):
            sentence += f", {turn['travel_class']} class"

        return sentence + "."

    # Destination revision
    if destination:
        confidence = turn.get("confidence", "SURE")

        if confidence == "PREFER":
            return f"Actually, I would prefer {airport_text(destination)} as my destination."

        if confidence == "UNSURE":
            return f"Maybe change my destination to {airport_text(destination)}, I'm not sure."

        return f"Actually, change my destination to {airport_text(destination)}."

    # Origin revision
    if origin:
      confidence = turn.get("confidence", "SURE")

      if confidence == "PREFER":
        return f"Actually, I would prefer {airport_text(origin)} as my departure."

      if confidence == "UNSURE":
        return f"Maybe change my departure to {airport_text(origin)}, I'm not sure."

      return f"Actually, change my departure to {airport_text(origin)}."
    # Travel class revision
    if turn.get("travel_class"):
        travel_class = turn["travel_class"]
        confidence = turn.get("confidence", "SURE")

        if confidence == "PREFER":
            return f"Actually, I would prefer {travel_class} class."

        if confidence == "UNSURE":
            return f"Maybe change my travel class to {travel_class}, I'm not sure."

        return f"Actually, change my travel class to {travel_class}."

    # Travel date revision
    if turn.get("travel_date"):
        travel_date = turn["travel_date"]
        confidence = turn.get("confidence", "SURE")

        if confidence == "PREFER":
            return f"Actually, I would prefer to travel on {travel_date}."

        if confidence == "UNSURE":
            return f"Maybe change my travel date to {travel_date}, I'm not sure."

        return f"Actually, change my travel date to {travel_date}."

    return ""
with open("clarifybench_revise.json", "r", encoding="utf-8") as f:
    cases = json.load(f)

REVISION_KINDS = {
    "revise_sure",
    "revise_prefer",
    "revise_unsure_new",
    "revise_unsure_old",
    "retract",
    "domino",
}

revision_cases = [
    case for case in cases
    if case["kind"] in REVISION_KINDS
]

language_cases = []

for case in revision_cases:
    sentences = [
        turn_to_sentence(turn)
        for turn in case["turns"]
    ]

    expected_turns = []

    for turn in case["turns"]:
        expected = dict(turn)

        if "confidence" not in expected:
            expected["confidence"] = "SURE"

        expected_turns.append(expected)

    language_cases.append({
        "id": case["id"],
        "kind": case["kind"],
        "sentences": sentences,
        "expected_turns": expected_turns,
        "truth": case["truth"]
    })

with open("language_cases.json", "w", encoding="utf-8") as f:
    json.dump(language_cases, f, indent=2)

print(f"Saved {len(language_cases)} cases to language_cases.json")