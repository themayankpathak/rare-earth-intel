# Measure the question box on 20 test questions with known answers (eval/chatbot_questions.csv).
# Usage: python scripts/evaluate_chatbot.py https://<your-worker>.workers.dev
# A question is correct when the box answers it if it should (with the right who, what and, where the test
# names them, material, part and year) or refuses it if it should. Blank fields in the test are not scored.
# The result is saved for the website: docs/data/chatbot_eval.json
import datetime
import json
import sys
import urllib.request

import pandas as pd

QUESTIONS = "eval/chatbot_questions.csv"
OUTPUT = "docs/data/chatbot_eval.json"
ORIGIN = "https://themayankpathak.github.io"   # the Worker only answers requests from the website
FIELDS = ["entity", "metric", "material", "segment", "year"]


def ask(url, question):
    # Send one question to the Worker, as the website does, and return its reply.
    request = urllib.request.Request(url, data=json.dumps({"question": question}).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "Origin": ORIGIN,
                                              "User-Agent": "Mozilla/5.0 (rare-earth-intel evaluation)"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())


def is_correct(expected, reply):
    # Right decision (answer or refuse), and for answers every field the test names matches.
    should_answer = expected["answerable"]
    if bool(reply.get("answerable")) != should_answer:
        return False
    return all(reply.get(f) == expected[f] for f in FIELDS if should_answer and expected[f])


def main(url):
    tests = pd.read_csv(QUESTIONS, dtype=str).fillna("")
    tests["answerable"] = tests["answerable"] == "TRUE"
    results, model = [], ""
    for _, t in tests.iterrows():
        reply = ask(url, t["question"])
        model = reply.get("model", model)
        ok = is_correct(t, reply)
        results.append({"question": t["question"], "correct": ok, "reply": reply})
        shown = {f: reply.get(f) for f in ["answerable"] + FIELDS + ["reason"] if reply.get(f) not in (None, "")}
        print(f"{'RIGHT' if ok else 'WRONG'}  {t['question']}\n       {shown}")
    correct = sum(r["correct"] for r in results)
    refusals = tests[~tests["answerable"]].index
    summary = {"model": model, "date": datetime.date.today().isoformat(), "correct": correct, "total": len(results),
               "refused_correctly": sum(results[i]["correct"] for i in refusals), "should_refuse": len(refusals),
               "results": results}
    with open(OUTPUT, "w") as f:
        json.dump(summary, f, indent=1)
    print(f"\n{correct} of {len(results)} correct ({summary['refused_correctly']} of {len(refusals)} refusals) "
          f"with {model} -> {OUTPUT}")


if __name__ == "__main__":
    main(sys.argv[1])
