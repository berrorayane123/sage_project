import json
import csv
import sys
import contextlib
import io
import os

CACHE_FILE = "reader_cache.json"

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

from reader import read_message, simple_reader
from agent import run_conversation

def load_cases():
    with open("language_cases.json", "r", encoding="utf-8") as f:
        return json.load(f)
    
def get_reader(mode):
    if mode == "simple":
        return simple_reader
    elif mode == "gemini":
        return read_message
    else:
        raise ValueError("Mode must be 'simple' or 'gemini'")

def read_sentence(reader, sentence, state=None, last_question=None):
    if reader == simple_reader:
        return reader(sentence, state)

    cache = load_cache()
    cache_key = json.dumps(
        {
            "sentence": sentence,
            "state": state,
            "last_question": last_question,
        },
        sort_keys=True,
    )

    if cache_key in cache:
        return cache[cache_key]

    result = reader(sentence, state, last_question)

    cache[cache_key] = result
    save_cache(cache)

    return result    
def evaluate_reader(case, reader):
    state = {}
    predictions = []

    for sentence in case["sentences"]:
        turn = read_sentence(reader, sentence, state)
        predictions.append(turn)

        for key, value in turn.items():
            if key != "confidence":
                state[key] = value

    return predictions 
 
def is_correct(predicted, expected):
    return predicted == expected  

def score_case(case, reader):
    predictions = evaluate_reader(case, reader)
    expected = case["expected_turns"]

    correct = 0

    for predicted, target in zip(predictions, expected):
        if is_correct(predicted, target):
            correct += 1

    return correct, len(expected), predictions

def run_agent(case, predictions, method):
    truth = case.get("truth")

    if truth is None: 
        return None

    with contextlib.redirect_stdout(io.StringIO()):
        result = run_conversation(
            "get_flight_cost",
            predictions,
            method,
            truth=truth
        )

    return result


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "simple"

    reader = get_reader(mode)
    cases = load_cases()

    total_correct = 0
    total_turns = 0
    
    agent_rows = []

    for case in cases:
        correct, total, predictions = score_case(case, reader)
        total_correct += correct
        total_turns += total

        print(f"{case['id']}: {correct}/{total}")
        print("Predictions:", predictions)
        if case.get("truth") is not None:
            sage_result = run_agent(case, predictions, "sage")
            ours_result = run_agent(case, predictions, "ours")

            print("SAGE result:", sage_result)
            print("OURS result:", ours_result)
            for method, result in [("sage", sage_result), ("ours", ours_result)]:
                    status, call, questions = result
                    correct_agent = status == "EXECUTED" and call == case["truth"]

                    agent_rows.append({
                        "id": case["id"],
                        "kind": case["kind"],
                        "method": method,
                        "status": status,
                        "correct": int(correct_agent),
                        "questions": questions
                    })

    accuracy = 100 * total_correct / total_turns
    print(f"\nREADER ACCURACY: {accuracy:.1f}%")
    print("\nAGENT ROWS:")
for row in agent_rows:
    print(row)
    
    with open(f"results_language_{mode}.csv", "w", newline="", encoding="utf-8") as f:
     writer = csv.DictWriter(f, fieldnames=agent_rows[0].keys())
     writer.writeheader()
     writer.writerows(agent_rows)
print("\nTABLE B2 — LANGUAGE EVALUATION")
for method in ["sage", "ours"]:
    rows = [r for r in agent_rows if r["method"] == method]
    correct = sum(r["correct"] for r in rows)
    accuracy_agent = 100 * correct / len(rows)
    avg_questions = sum(r["questions"] for r in rows) / len(rows)

    print(
        f"{method}: Correct={accuracy_agent:.1f}% | "
        f"Avg Questions={avg_questions:.2f}"
    )     
     
 
     