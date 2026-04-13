"""Cat ASCII art for OpenPaws."""

import random

# ---------------------------------------------------------------------------
# ASCII Banner — the only cat art that displays
# ---------------------------------------------------------------------------

BANNER = r"""  ___   ____ ______ ___   _    /\_/\
 / _ \ |  _ \| ___| |\ \ | |  ( o.o )
| | | || |_) |  _|  | \ \| |  (> ^ <)
| |_| ||  __/| |___ | |\   |  /|   |\
 \___/ |_|   |_____|| | \__| (_|   |_)"""

# ---------------------------------------------------------------------------
# Cat Jokes
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
    "My cat's code style: indent with paws, comment with purrs.",
    "Why do cats make good sysadmins? Always watching, always judging.",
    "What's a cat's favorite design pattern? The observer pattern.",
]

def random_cat_joke():
    return random.choice(CAT_JOKES)
