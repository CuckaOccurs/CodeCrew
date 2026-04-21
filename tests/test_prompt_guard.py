"""
Quick test for the prompt guard — run with: python tests/test_prompt_guard.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from codemaid.prompt_guard import analyze_prompt, LOOP_RISK, HALLUCINATION_RISK, CONTEXT_GAP, CONTRADICTION

def check(prompt, expected_type=None):
    issues = analyze_prompt(prompt)
    types  = [i.type for i in issues]
    status = "✓" if (expected_type in types if expected_type else not issues) else "✗"
    label  = issues[0].description if issues else "clean"
    print(f"  {status}  [{expected_type or 'clean':20}]  '{prompt[:55]}'")
    if status == "✗":
        print(f"       got: {types or 'nothing'}")
    return status == "✓"

def run():
    passed = failed = 0
    tests = [
        # Loop risk
        ("keep fixing until it works",                   LOOP_RISK),
        ("repeat this for all files",                    LOOP_RISK),
        ("do this for every function",                   LOOP_RISK),
        ("fix everything",                               LOOP_RISK),
        ("try again until it passes",                    LOOP_RISK),
        ("continuously check the output",                LOOP_RISK),

        # Hallucination
        ("you said this would work last time",           HALLUCINATION_RISK),
        ("as we discussed, update the config",           HALLUCINATION_RISK),
        ("remember when you fixed the vault?",           HALLUCINATION_RISK),
        ("fill in the rest",                             HALLUCINATION_RISK),
        ("what were we working on?",                     HALLUCINATION_RISK),

        # Context gap
        ("fix it",                                       CONTEXT_GAP),
        ("do the rest",                                  CONTEXT_GAP),
        ("change the thing",                             CONTEXT_GAP),

        # Contradiction
        ("never use sudo but always run as root",        CONTRADICTION),
        ("don't edit the file but update the config",    CONTRADICTION),

        # Should be clean
        ("read skills_loader.py and explain it",         None),
        ("add a /loaded command to commands.py",         None),
        ("run the tests",                                None),
    ]

    print("\n── Prompt Guard Tests ──────────────────────────────────────")
    for prompt, expected in tests:
        if check(prompt, expected):
            passed += 1
        else:
            failed += 1

    print(f"\n  {passed} passed  {failed} failed\n")

if __name__ == "__main__":
    run()
