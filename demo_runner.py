# ===== demo_runner.py: plays a demo script from the demo/ folder; the chatbot answers LIVE =====
# Each file in demo/ contains only the USER's messages. The chatbot's answers are produced live by chat.py.
#   python demo_runner.py          -> lists the demos
#   python demo_runner.py 5        -> plays demo 5 (press Enter to send each user message)
#   python demo_runner.py 5 auto   -> plays demo 5 without waiting for Enter
#   python demo_runner.py 2 8 5    -> plays several demos one after another (e.g. the 3 confidence weights)
import builtins, sys, os, glob, runpy

DEMO_DIR = "demo"


def load(path):
    """A demo file: '# description' lines, one 'version: <name>' line, then one user message per line."""
    description, version, messages = "", "ours", []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            description += line[1:].strip() + " "
        elif line.lower().startswith("version:"):
            version = line.split(":", 1)[1].strip()
        else:
            messages.append(line)
    return description.strip(), version, messages


def demo_files():
    files = glob.glob(os.path.join(DEMO_DIR, "demo*.txt"))
    number = lambda p: int("".join(ch for ch in os.path.basename(p).split("_")[0] if ch.isdigit()))
    return {number(p): p for p in files}


def play(path, wait=True):
    description, version, messages = load(path)
    print(f"===== {os.path.basename(path)} =====")
    print(f"{description}\n$ python chat.py {version}")
    remaining = iter(messages + ["quit"])
    real_input = builtins.input
    def fake_input(prompt=""):
        message = next(remaining, "quit")
        if wait and message != "quit":
            real_input("\n   [press Enter to send the next user message]")
        print(prompt + message)                      # the user's message; chat.py then answers live
        return message
    real_argv = sys.argv
    builtins.input, sys.argv = fake_input, ["chat.py", version]
    try:
        runpy.run_path("chat.py", run_name="__main__")
    finally:
        builtins.input, sys.argv = real_input, real_argv


if __name__ == "__main__":
    demos = demo_files()
    if len(sys.argv) < 2:
        print("Available demos (run: python demo_runner.py <number>):")
        for n in sorted(demos):
            print(f"  {n:2}  {os.path.basename(demos[n]):32} {load(demos[n])[0]}")
    else:
        args = sys.argv[1:]
        wait = "auto" not in args
        chosen = [a for a in args if a != "auto"]
        for i, arg in enumerate(chosen):
            path = demos.get(int(arg)) if arg.isdigit() else arg
            if not path or not os.path.exists(path):
                sys.exit(f"Demo '{arg}' not found. Run 'python demo_runner.py' to see the list.")
            if i > 0:
                print("\n" + "=" * 70)
                if wait:
                    input("   [press Enter to start the next demo]")
            play(path, wait=wait)