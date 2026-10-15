# ===== reader.py: Gemini reads ANY user sentence and turns it into a structured turn =====
#   "hmm maybe LA instead? not sure"  ->  {"travel_to": "LAX", "confidence": "UNSURE"}
import os, re, json, time, datetime
from clarifybench_travel import AIRPORTS, CITIES

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
# If a model is busy (503), we switch to the next one instead of waiting
MODELS = [MODEL] + [m for m in ["gemini-3.5-flash", "gemini-3.7-flash", "gemini-3.8-flash",
                                "gemini-3.1-flash-lite"] if m != MODEL]
PARAMS = ["travel_from", "travel_to", "travel_date", "travel_class"]
CATEGORIES = ["SURE", "PREFER", "UNSURE"]
_client = None


def client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


PROMPT = """You read ONE message from a user who is talking to a flight-price assistant.
Extract what the user says in THIS message only, as JSON.

Parameters:
- travel_from: departure airport code, one of {airports}
- travel_to: arrival airport code, one of {airports}
- travel_date: the date, format YYYY-MM-DD (today is {today})
- travel_class: one of economy, business, first
City names map to airport codes like this: {cities}

What the assistant already knows: {state}
The assistant's last question was: {question}

Return ONLY a JSON object with two keys:
- "values": an object with every parameter the user gives, answers or changes in THIS message.
  Use null for a parameter the user asks to forget or remove. Leave out parameters the user does not mention.
  If the user answers a yes/no confirmation question, put the value they chose.
- "confidence": how sure the user sounds about what they say in THIS message:
  "SURE"   = clear answer or clear change ("Boston", "actually make it Boston", "yes")
  "PREFER" = a preference, not final ("Boston would be better", "I'd rather Boston", "I think Boston")
  "UNSURE" = hesitant ("maybe Boston?", "not sure, Boston?", "Boston or not, I don't know")
"""


def read_message(message, state=None, last_question=None, retries=5):
    """Returns a turn like {"travel_to": "LAX", "confidence": "UNSURE"}."""
    prompt = PROMPT.format(airports=", ".join(AIRPORTS), cities=json.dumps(CITIES),
                           today=datetime.date.today().isoformat(),
                           state=json.dumps(state or {}), question=last_question or "none")
    prompt += f'\nUser message: "{message}"'
    for model in MODELS:                                  # try each model once
        try:
            response = client().models.generate_content(
                model=model, contents=prompt,
                config={"response_mime_type": "application/json", "temperature": 0})
            return to_turn(json.loads(response.text))
        except Exception as error:
            text = str(error)
            if "API key" in text:                         # wrong key: tell the user
                raise
            print(f"   ({model} busy: {text[:40]}... trying the next one)")
    print("   (Gemini is busy -> using the simple backup reader)")
    return simple_reader(message, state)                 # never get stuck


# ----- Backup reader (no internet): simple keyword rules -----
HEDGE_UNSURE = ["maybe", "not sure", "perhaps", "i don't know", "idk", "?"]
HEDGE_PREFER = ["would be better", "i'd rather", "i would rather", "i think", "prefer", "better"]
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug",
                                      "sep", "oct", "nov", "dec"], 1)}


ALIASES = {"la": "LAX", "l.a.": "LAX", "nyc": "JFK", "ny": "JFK", "sf": "SFO", "chi": "ORD"}


def find_airport(text):
    for city, code in sorted(CITIES.items(), key=lambda kv: -len(kv[0])):
        if city.lower() in text:
            return code, text.index(city.lower())
    for alias, code in ALIASES.items():
        match = re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", text)
        if match:
            return code, match.start()
    for code in AIRPORTS:
        match = re.search(rf"\b{code.lower()}\b", text)
        if match:
            return code, match.start()
    return None, None


def simple_reader(message, state=None):
    text = message.lower()
    turn = {}

    # Handle retractions
    if any(w in text for w in ["forget", "remove", "ignore"]):
        if any(w in text for w in ["destination", "to ", "going"]):
            turn["travel_to"] = None
        elif any(w in text for w in ["origin", "departure", "from", "leaving"]):
            turn["travel_from"] = None
        elif "date" in text:
            turn["travel_date"] = None
        elif "class" in text:
            turn["travel_class"] = None

        turn["confidence"] = "SURE"
        return turn

    # Find airports/cities
    places = []
    rest = text

    while True:
        code, pos = find_airport(rest)

        if code is None:
            break

        places.append((code, rest[:pos]))

        word = re.match(
            r"[a-z.]+(?: [a-z]+)?",
            rest[pos:]
        ).group()

        names = (
            [c.lower() for c in CITIES if CITIES[c] == code]
            + [a for a in ALIASES if ALIASES[a] == code]
            + [code.lower()]
        )

        hit = next(
            (
                n
                for n in sorted(names, key=len, reverse=True)
                if rest[pos:].startswith(n)
            ),
            word,
        )

        # Blank the airport/city already found so we can find another one
        rest = rest[:pos] + " " * len(hit) + rest[pos + len(hit):]

    # Special case:
    # "Actually, change my departure to ORD."
    if len(places) == 1 and "departure" in text:
        turn["travel_from"] = places[0][0]
        places = []

    # Special case:
    # "change my departure from San Francisco to Los Angeles"
    if (
        len(places) == 2
        and "departure" in text
        and "from" in text
        and " to " in text
    ):
        turn["travel_from"] = places[1][0]
        places = []

    # Special case:
    # "Los Angeles instead of New York"
    if "instead of" in text and len(places) == 2:
        turn["travel_to"] = places[0][0]
        places = []

    # Normal origin/destination extraction
    for code, before in places:
        if (
            re.search(r"from\s*$", before.strip() + " ")
            or before.strip().endswith("from")
        ):
            turn["travel_from"] = code
        else:
            if "travel_to" not in turn:
                turn["travel_to"] = code
            else:
                turn.setdefault("travel_from", code)

    # Normal "from X to Y"
    if len(places) == 2 and "from" in text and "travel_from" not in turn:
        turn["travel_from"] = places[0][0]
        turn["travel_to"] = places[1][0]

    # Travel class
    for cls in ["economy", "business", "first"]:
        if cls in text:
            turn["travel_class"] = cls

    # ISO date: YYYY-MM-DD
    iso = re.search(r"\d{4}-\d{2}-\d{2}", text)

    if iso:
        turn["travel_date"] = iso.group()

    else:
        # Dates such as August 10th, 2024
        m = re.search(
            r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
            r"\w*\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?",
            text,
        )

        if m:
            year = (
                int(m.group(3))
                if m.group(3)
                else datetime.date.today().year
            )

            turn["travel_date"] = (
                f"{year}-{MONTHS[m.group(1)]:02d}-{int(m.group(2)):02d}"
            )

    # Confidence
    if any(w in text for w in HEDGE_UNSURE):
        turn["confidence"] = "UNSURE"

    elif any(w in text for w in HEDGE_PREFER):
        turn["confidence"] = "PREFER"

    else:
        turn["confidence"] = "SURE"

    return turn

def to_turn(data):
    values = data.get("values", {}) or {}
    turn = {p: v for p, v in values.items() if p in PARAMS}
    category = str(data.get("confidence", "SURE")).upper()
    turn["confidence"] = category if category in CATEGORIES else "SURE"
    return turn


if __name__ == "__main__":                                # quick test
    for sentence in ["I want to fly from San Francisco to New York on November 5th, economy",
                     "Actually, make it Boston",
                     "Hmm, Boston would be better I think",
                     "maybe Boston? not sure",
                     "Forget the destination I gave you"]:
        print(f"{sentence!r:70} -> {read_message(sentence)}")