# ===== eval_language.py: TABLE B - the user writes normal sentences, a reader turns them into updates =====
#
#   python build_language_cases.py    -> language_cases.json (162 change-of-mind conversations as sentences)
#   python eval_language.py simple    -> offline backup reader (no internet, no key)
#   python eval_language.py gemini    -> Gemini reads every sentence (needs GEMINI_API_KEY)
#
# Gemini answers are saved in reader_cache.json. If Google is busy (503) or the free quota is used up (429),
# this script WAITS and RETRIES, and if it still fails it STOPS. It never switches to the backup reader in
# secret, so every number printed for "gemini" really comes from Gemini. Run it again later: it continues
# from the cache.
import io, os, sys, csv, json, time, datetime, contextlib
import reader
from agent import run_conversation
from clarifybench_travel import CITIES

MODE = sys.argv[1] if len(sys.argv) > 1 else "simple"
CACHE_FILE = "reader_cache.json"
METHODS = ["sage", "ledger", "ledger+confidence", "ledger+domino", "always_confirm", "ours"]
CATEGORIES = ["SURE", "PREFER", "UNSURE"]


# ---------- 1. Reading a sentence ----------
def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


CACHE = load_cache()


def save_cache():
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(CACHE, f, indent=2, ensure_ascii=False)


def ask_gemini(sentence, state, last_question):
    """Gemini ONLY. Waits and retries when Google is busy; stops instead of using the backup reader."""
    prompt = reader.PROMPT.format(airports=", ".join(reader.AIRPORTS), cities=json.dumps(CITIES),
                                  today=datetime.date.today().isoformat(),
                                  state=json.dumps(state or {}), question=last_question or "none")
    prompt += f'\nUser message: "{sentence}"'
    for attempt in range(1, 6):
        for model in reader.MODELS:
            try:
                response = reader.client().models.generate_content(
                    model=model, contents=prompt,
                    config={"response_mime_type": "application/json", "temperature": 0})
                return reader.to_turn(json.loads(response.text))
            except Exception as error:
                if "API key" in str(error) or isinstance(error, KeyError):
                    sys.exit("No valid GEMINI_API_KEY. Set it with: setx GEMINI_API_KEY \"your_key\"")
                print(f"   ({model}: {str(error)[:45]}...)")
        wait = 30 * attempt
        print(f"   Google is busy, waiting {wait} s (attempt {attempt}/5)...")
        time.sleep(wait)
    save_cache()
    sys.exit("\nGoogle is still busy. Nothing was faked: run the same command later, it continues from the cache.")


def read_sentence(sentence, state, last_question=None):
    if MODE == "simple":
        return reader.simple_reader(sentence, state)
    key = json.dumps({"sentence": sentence, "state": state, "last_question": last_question}, sort_keys=True)
    if key not in CACHE:
        CACHE[key] = ask_gemini(sentence, state, last_question)
        save_cache()
        time.sleep(1)                                    # be gentle with the free quota
    return CACHE[key]


def read_case(case):
    """Read every sentence of one conversation. The state given to the reader is what it understood so far."""
    state, predictions = {}, []
    for sentence in case["sentences"]:
        turn = read_sentence(sentence, state)
        predictions.append(turn)
        state.update({k: v for k, v in turn.items() if k != "confidence"})
    return predictions


# ---------- 2. Running the agent on what the reader understood ----------
def run_case(case, predictions, method, info):
    with contextlib.redirect_stdout(io.StringIO()):
        status, call, questions = run_conversation("get_flight_cost", predictions, method, truth=case["truth"])
    correct = status == "EXECUTED" and call == case["truth"]
    stale = (info["old_value"] is not None and call.get(info["changed_param"]) == info["old_value"]
             and case["truth"][info["changed_param"]] != info["old_value"])
    return {"id": case["id"], "kind": case["kind"], "method": method, "status": status,
            "correct": int(correct), "stale": int(stale), "exec_error": int(status == "EXEC_ERROR"),
            "broken": int(status == "BROKEN"), "questions": questions}


def values_of(turn):
    return {k: v for k, v in turn.items() if k != "confidence"}


if __name__ == "__main__":
    if MODE not in ("simple", "gemini"):
        sys.exit("Use: python eval_language.py simple   or   python eval_language.py gemini")
    cases = json.load(open("language_cases.json", encoding="utf-8"))
    original = {c["id"]: c for c in json.load(open("clarifybench_revise.json", encoding="utf-8"))}
    print(f"Reader: {MODE}   |   {len(cases)} conversations, {sum(len(c['sentences']) for c in cases)} sentences")

    reading, rows = [], []
    for n, case in enumerate(cases, 1):
        predictions = read_case(case)
        for i, (sentence, got, gold) in enumerate(zip(case["sentences"], predictions, case["expected_turns"])):
            reading.append({"id": case["id"], "turn": i, "sentence": sentence,
                            "expected": json.dumps(gold), "read": json.dumps(got),
                            "all_ok": int(got == gold), "values_ok": int(values_of(got) == values_of(gold)),
                            "confidence_ok": int(got.get("confidence") == gold.get("confidence")),
                            "gold_confidence": gold.get("confidence"), "is_change": int(i > 0)})
        rows += [run_case(case, predictions, m, original[case["id"]]) for m in METHODS]
        if MODE == "gemini" and n % 20 == 0:
            print(f"   {n}/{len(cases)} conversations read")

    with open(f"reader_{MODE}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=reading[0].keys())
        writer.writeheader()
        writer.writerows(reading)
    with open(f"results_language_{MODE}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    pct = lambda rs, key: 100 * sum(r[key] for r in rs) / len(rs)
    changes = [r for r in reading if r["is_change"]]
    print(f"\nREADER ACCURACY ({MODE})")
    print(f"  whole turn right (values + confidence) : {pct(reading, 'all_ok'):5.1f}%   (n={len(reading)} sentences)")
    print(f"  values right                           : {pct(reading, 'values_ok'):5.1f}%")
    print(f"  confidence right, change-of-mind turns : {pct(changes, 'confidence_ok'):5.1f}%   (n={len(changes)})")
    for cat in CATEGORIES:
        rs = [r for r in changes if r["gold_confidence"] == cat]
        if rs:
            print(f"      {cat:7}: {pct(rs, 'confidence_ok'):5.1f}%   (n={len(rs)})")
    mistakes = [r for r in reading if not r["all_ok"]]
    if mistakes:
        print("  mistakes:")
        for r in mistakes[:10]:
            print(f"      \"{r['sentence']}\"  expected {r['expected']}  read {r['read']}")

    print(f"\nTABLE B - Change of mind, user writes sentences ({MODE} reader, {len(cases)} conversations)")
    print(f"{'method':20} {'correct':>9} {'stale':>7} {'exec_err':>9} {'broken':>7} {'avg_q':>6}")
    for m in METHODS:
        r = [x for x in rows if x["method"] == m]
        p = lambda key: f"{pct(r, key):6.1f}%"
        print(f"{m:20} {p('correct'):>9} {p('stale'):>7} {p('exec_error'):>9} {p('broken'):>7} "
              f"{sum(x['questions'] for x in r) / len(r):6.2f}")
    print(f"\nSaved: reader_{MODE}.csv, results_language_{MODE}.csv")
