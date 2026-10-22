"""Run the RAG test questions.

    python scripts/run_tests.py                      # phase picked from the content (auto)
    python scripts/run_tests.py --phase baseline     # before adding the new post
    python scripts/run_tests.py --phase fresh        # after adding release-2026-10 and re-ingesting
"""
import argparse
import json
import sys

from common import ROOT, ask, cited_urls, get_project, load_config, token_usage, tools_used


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["auto", "baseline", "fresh"], default="auto")
    parser.add_argument("--version")
    args = parser.parse_args()

    if args.phase == "auto":  # the fresh phase starts once the 2026.10 post is published
        args.phase = "fresh" if (ROOT / "content" / "posts" / "release-2026-10.md").exists() else "baseline"
    cfg = load_config()
    cases = [c for c in json.loads((ROOT / "tests" / "test_cases.json").read_text(encoding="utf-8"))
             if args.phase in c["phases"]]
    project = get_project()
    failures = 0
    for case in cases:
        expect = case["expect"][args.phase]
        try:
            response = ask(project, cfg["agent_name"], case["question"], version=args.version)
            answer = (response.output_text or "").lower().replace("\u2019", "'")
            ok = any(k.lower() in answer for k in expect)
            used, tokens, urls = tools_used(response), token_usage(response), cited_urls(response)
        except Exception as error:
            ok, used, tokens, urls, answer = False, [], None, [], f"error: {error}"
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] {case['id']}  tools={used}  tokens={tokens}  citations={len(urls)}")
        if not ok:
            print(f"        expected one of {expect}; answer: {answer[:300]}")
    print(f"\n{len(cases) - failures}/{len(cases)} passed ({args.phase})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
