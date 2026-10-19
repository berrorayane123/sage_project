# ===== demo_runner.py: replays chat.py conversations with fixed messages (for slides / report) =====
#   python demo_runner.py                      -> runs ALL 7 demos and saves them in the demo/ folder
#   python demo_runner.py 1                    -> PRESENTER MODE: plays demo 1 live, press Enter for each user message
#   python demo_runner.py ours "msg 1" "msg 2" -> runs ONE conversation with your own messages
import builtins, sys, os, io, runpy, contextlib

START = "I want to fly from San Francisco to New York on 2026-11-05"
DEMOS = [
    ("demo1_sage_breaks",           "sage",   [START, "Economy. Actually, make it Los Angeles"]),
    ("demo2_ours_sure",             "ours",   [START, "Economy. Actually, make it Los Angeles"]),
    ("demo3_ledger_unsure_guesses", "ledger", [START, "Economy. Maybe Los Angeles? not sure"]),
    ("demo4_ours_unsure_confirms",  "ours",   [START, "Economy. Maybe Los Angeles? not sure", "Yes, Los Angeles"]),
    ("demo5_ours_unsure_goes_back", "ours",   [START, "Economy. Maybe Los Angeles? not sure", "No, keep New York"]),
    ("demo6_ledger_domino_error",   "ledger", [START, "Business. Actually I will leave from Chicago"]),
    ("demo7_ours_domino",           "ours",   [START, "Business. Actually I will leave from Chicago", "Los Angeles"]),
]


def run(method, messages, live=False):
    """Runs chat.py once, typing the messages for the user, and returns everything it printed.
    live=True: prints directly to the screen and waits for Enter before each user message."""
    remaining = iter(list(messages) + ["quit"])
    real_input = builtins.input
    def fake_input(prompt=""):
        message = next(remaining, "quit")
        if live and message != "quit":
            real_input("\n   [press Enter to send the next user message]")
        print(prompt + message)                      # show the user's message, like a real chat
        return message
    real_argv = sys.argv
    builtins.input, sys.argv = fake_input, ["chat.py", method]
    output = io.StringIO()
    try:
        with (contextlib.nullcontext() if live else contextlib.redirect_stdout(output)):
            print(f"$ python chat.py {method}")
            runpy.run_path("chat.py", run_name="__main__")
    finally:
        builtins.input, sys.argv = real_input, real_argv
    return output.getvalue()


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1].isdigit():  # presenter mode: one numbered demo, live
        name, method, messages = DEMOS[int(sys.argv[1]) - 1]
        print(f"===== {name} =====")
        run(method, messages, live=True)
    elif len(sys.argv) >= 3:                           # one conversation, given on the command line
        print(run(sys.argv[1], sys.argv[2:]))
    else:                                            # no messages given -> all 7 demos
        os.makedirs("demo", exist_ok=True)
        for name, method, messages in DEMOS:
            text = run(method, messages)
            with open(os.path.join("demo", name + ".txt"), "w", encoding="utf-8") as f:
                f.write(text)
            last = [l for l in text.splitlines() if l.startswith(("AGENT", "TOOL", "   BROKEN"))][-1]
            print(f"{name:30} -> {last}")
        print("\nSaved 7 demos in the demo/ folder.")