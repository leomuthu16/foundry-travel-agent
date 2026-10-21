"""Run the test questions against the agent and fail if any answer is wrong.

Usage:
    python scripts/run_tests.py                 # test the latest version
    python scripts/run_tests.py --version 4     # test a specific version

This is the pipeline's quality gate: a new version is only promoted if it passes.
Each question runs in its own request with no chat history, so results are repeatable.
"""
import argparse
import json
import os
import sys

from foundry_common import ROOT, ask, get_project, load_config, token_usage, tools_used


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", help="Agent version to test (default: latest)")
    args = parser.parse_args()

    config = load_config()
    cases = json.loads((ROOT / "tests" / "test_cases.json").read_text(encoding="utf-8"))
    project = get_project()

    rows, failures = [], 0
    for case in cases:
        try:
            response = ask(project, config["agent_name"], case["question"], version=args.version)
            answer = (response.output_text or "").strip()
            used = tools_used(response)
            text_ok = any(k.lower() in answer.lower() for k in case["must_contain_any"])
            tools_ok = all(t in used for t in case.get("expected_tools", []))
            passed = text_ok and tools_ok
            reason = "" if passed else ("missing expected text" if not text_ok else f"expected tools {case['expected_tools']}")
            tokens = token_usage(response)
        except Exception as error:  # report the error and keep testing the other cases
            passed, used, tokens, answer, reason = False, [], None, "", f"error: {error}"
        failures += 0 if passed else 1
        rows.append((case["id"], "PASS" if passed else "FAIL", ", ".join(used) or "-", tokens or "-", reason))
        print(f"[{'PASS' if passed else 'FAIL'}] {case['id']}  tools={used}  tokens={tokens}  {reason}")
        if not passed and answer:
            print(f"        answer: {answer[:300]}")

    print(f"\n{len(cases) - failures}/{len(cases)} tests passed")

    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(f"### Agent tests – version {args.version or 'latest'}\n\n")
            f.write("| Test | Result | Tools used | Tokens | Note |\n|---|---|---|---|---|\n")
            for row in rows:
                f.write("| " + " | ".join(str(c) for c in row) + " |\n")
            f.write(f"\n**{len(cases) - failures}/{len(cases)} passed**\n")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
