"""Score the agent's answers for accuracy and citations.

    python scripts/evaluate.py                 # phase picked from the content, latest agent version
    python scripts/evaluate.py --version 3     # a specific agent version

For every question in tests/eval_set.json:
  * correctness (1-5): a judge model compares the answer with a reference answer
  * citation recall: share of the expected source posts the answer cites
  * citation precision: share of cited blog posts that are expected sources (reported, not gated)
The run fails (exit code 1) when the averages are below the thresholds in rag.config.json,
so a pipeline can use it as a quality gate. A JSON report is saved in eval_results/.
"""
import argparse
import json
import re
import sys
import time

from common import ROOT, ask, cited_urls, get_project, load_config, openai_client, write_summary

BLOG_URL = re.compile(r"https://blog\.contoso-datahub\.example/([a-z0-9-]+)")

JUDGE_INSTRUCTIONS = """You grade answers from a blog reader assistant.
Compare the ANSWER with the REFERENCE answer for the QUESTION and give a correctness score:
5 = all key facts of the reference are present and correct, nothing contradicts it
4 = correct, but a minor detail is missing
3 = partly correct: an important fact is missing or vague
2 = mostly wrong or outdated (for example an older value that a newer post replaced)
1 = wrong, or invents information the reference says is not covered
If the reference says the topic is not covered, an answer that clearly says so scores 5.
Ignore style, length and the list of sources.
Reply with JSON only: {"score": <1-5>, "reason": "<one short sentence>"}"""


def judge(client, model: str, question: str, reference: str, answer: str) -> tuple[int, str]:
    response = client.responses.create(
        model=model,
        instructions=JUDGE_INSTRUCTIONS,
        input=f"QUESTION:\n{question}\n\nREFERENCE:\n{reference}\n\nANSWER:\n{answer}",
    )
    match = re.search(r"\{.*\}", response.output_text or "", re.S)
    try:
        verdict = json.loads(match.group(0)) if match else {}
        return int(verdict.get("score", 1)), str(verdict.get("reason", ""))
    except (ValueError, TypeError):
        return 1, f"could not read the judge's reply: {(response.output_text or '')[:120]}"


def cited_posts(response, answer: str) -> set[str]:
    """Post ids cited, from citation annotations and from URLs written in the answer."""
    urls = cited_urls(response) + [m.group(0) for m in BLOG_URL.finditer(answer)]
    return {m.group(1) for u in urls for m in [BLOG_URL.search(u)] if m}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["auto", "baseline", "fresh"], default="auto")
    parser.add_argument("--version")
    args = parser.parse_args()
    if args.phase == "auto":
        args.phase = "fresh" if (ROOT / "content" / "posts" / "release-2026-10.md").exists() else "baseline"

    cfg = load_config()
    min_correct = cfg.get("eval_min_correctness", 4.0)
    min_recall = cfg.get("eval_min_citation_recall", 0.8)
    cases = [c for c in json.loads((ROOT / "tests" / "eval_set.json").read_text(encoding="utf-8")) if args.phase in c["phases"]]
    project, client = get_project(), openai_client()

    results = []
    for case in cases:
        try:
            response = ask(project, cfg["agent_name"], case["question"], version=args.version)
            answer = response.output_text or ""
            cited = cited_posts(response, answer)
        except Exception as error:  # a failed call scores zero rather than stopping the run
            answer, cited = f"error: {error}", set()
        score, reason = judge(client, cfg.get("judge_model", cfg["model"]), case["question"], case["reference"], answer)
        expected = set(case["sources"])
        recall = len(expected & cited) / len(expected) if expected else 1.0
        precision = len(expected & cited) / len(cited) if cited else (1.0 if not expected else 0.0)
        results.append({"id": case["id"], "correctness": score, "citation_recall": round(recall, 2),
                        "citation_precision": round(precision, 2), "cited": sorted(cited),
                        "expected": sorted(expected), "judge_reason": reason, "answer": answer})
        print(f"{case['id']:<28} correctness={score}  recall={recall:.2f}  precision={precision:.2f}  {reason}")

    avg = lambda key: sum(r[key] for r in results) / len(results)
    summary = {"phase": args.phase, "agent": cfg["agent_name"], "version": args.version or "latest",
               "correctness": round(avg("correctness"), 2), "citation_recall": round(avg("citation_recall"), 2),
               "citation_precision": round(avg("citation_precision"), 2)}
    passed = summary["correctness"] >= min_correct and summary["citation_recall"] >= min_recall
    print(f"\nAverage correctness {summary['correctness']} (min {min_correct}), citation recall "
          f"{summary['citation_recall']} (min {min_recall}), citation precision {summary['citation_precision']}"
          f"  ->  {'PASS' if passed else 'FAIL'}")

    out_dir = ROOT / "eval_results"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"eval-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps({"summary": summary, "passed": passed, "results": results}, indent=2), encoding="utf-8")
    print(f"Report: {out.relative_to(ROOT)}")

    rows = "\n".join(f"| {r['id']} | {r['correctness']} | {r['citation_recall']} | {r['citation_precision']} | {r['judge_reason']} |" for r in results)
    write_summary(f"## Evaluation ({args.phase}): {'PASS' if passed else 'FAIL'}\n\n"
                  f"Correctness **{summary['correctness']}** / 5 (min {min_correct}) · Citation recall **{summary['citation_recall']}** "
                  f"(min {min_recall}) · Citation precision {summary['citation_precision']}\n\n"
                  f"| Question | Correctness | Recall | Precision | Judge |\n|---|---|---|---|---|\n{rows}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
