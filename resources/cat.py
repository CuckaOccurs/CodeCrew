"""Cat animations and ASCII art for CodeMAID."""

import random
import time

# ---------------------------------------------------------------------------
# ASCII Banners
# ---------------------------------------------------------------------------

# The exact banner as requested, using a raw string to prevent escape issues
BANNER = r"""  ___   ____ ______ ___   _    /\_/\
 / _ \ |  _ \| ___| |\ \ | |  ( o.o )
| | | || |_) |  _|  | \ \| |  (> ^ <)
| |_| ||  __/| |___ | |\   |  /|   |\
 \___/ |_|   |_____|| | \__| (_|   |_)"""

# Simple large cat
LARGE_CAT = """  /\\_/\\
 ( o.o )
 (> ^ <)
 /|   |\\
(_|   |_)"""

# Small cat for prompt
CAT_DEFAULT = "  /\\_/\\\n ( o.o )\n  > ^ <"

CAT_SITTING = "  /\\_/\\\n ( o.o )\n  > ^ <"

CAT_HAPPY = "  /\\_/\\\n ( ^.^ )\n  > <"

CAT_SLEEPING = "  /\\_/\\\n ( -.- ) zzz\n (_______)"

CAT_CONFUSED = "  /\\_/\\\n ( O.o )\n  > ? <"

CAT_LAYING = "  /\\_/\\\n ( -.- )\n(_______)"

# ---------------------------------------------------------------------------
# Animations
# ---------------------------------------------------------------------------

CAT_JOKES = [
    "Why did the cat sit on the keyboard? It wanted to keep an eye on the mouse.",
    "What do cats and code have in common? They both ignore you until they feel like responding.",
    "My cat's favorite programming language is scratch.",
    "Why don't cats like coding? Too many bugs.",
    "What's a cat's favorite data structure? A cat-alog.",
    "Why was the cat bad at debugging? It kept chasing the null mouse.",
    "What do you call a cat that loves to code? A purr-grammer.",
    "My cat's code review: *stares at screen* *knocks coffee off desk* *walks away*",
    "The cat sat on the 'delete' key. Now it's a feature, not a bug.",
    "Why did the cat join the dev team? Great at catching exceptions.",
    "Cat's testing approach: if it breaks, I'll stare at it until it works.",
    "What's a cat's favorite Git command? git commit -m 'meow'",
    "The cat's code always has 9 lives of error handling.",
    "My cat's code style: indent with codemaid, comment with purrs.",
    "Why do cats make good sysadmins? Always watching, always judging.",
    "What's a cat's favorite design pattern? The observer pattern.",
]

def random_cat_joke():
    return random.choice(CAT_JOKES)

def sitting_animation(duration=1.0):
    start = time.time()
    while time.time() - start < duration:
        print(f"\r{CAT_SITTING}", end="", flush=True)
        time.sleep(0.5)
    print()

def happy_animation(duration=0.8):
    frames = [CAT_HAPPY, CAT_HAPPY.replace("<", "♥"), CAT_HAPPY]
    start = time.time()
    idx = 0
    while time.time() - start < duration:
        print(f"\r{frames[idx % len(frames)]}", end="", flush=True)
        idx += 1
        time.sleep(0.25)
    print()

def confused_animation(duration=0.5):
    print(f"\r{CAT_CONFUSED}")
    time.sleep(duration)

def sleeping_animation(duration=2.0):
    frames = [CAT_SLEEPING, CAT_SLEEPING + "z", CAT_SLEEPING + "zz"]
    start = time.time()
    idx = 0
    while time.time() - start < duration:
        print(f"\r{frames[idx % len(frames)]}", end="", flush=True)
        idx += 1
        time.sleep(0.5)
    print()

def print_cat_joke():
    print(f"\n  {CAT_LAYING}")
    print(f"  🐱 {random_cat_joke()}\n")
