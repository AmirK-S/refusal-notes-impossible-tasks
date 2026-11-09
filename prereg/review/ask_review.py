"""Adversarial review of PLAN-EXPERIENCE.md by other lineages through Adaption (Responses format).
Usage: python3 prereg/review/ask_review.py <model> <out.json>   (reads ADAPTION_API_KEY from the environment; never prints it)"""
import json, os, sys, urllib.request

model, out = sys.argv[1], sys.argv[2]
B = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
plan = open(os.path.join(B, "prereg/PLAN-EXPERIENCE.md")).read()
power = open(os.path.join(B, "analyse/power_out.txt")).read()
prompt = f"""You are a hostile but fair methods reviewer for an AI safety hackathon (Apart Research). Judges score
"quality of execution": rigorous method, convincing validation, results that support the conclusions.
Below is a pre-registered analysis plan, and the output of the exact power script it cites.

Your job: list the methodological flaws of this plan, ranked from most to least serious, and for each one say
(a) why it would lower the execution score or invalidate a conclusion, and (b) the smallest concrete change that
fixes it before data collection, given that runs start within the hour and the deadline is the next day at noon.
Cover at least: the definition of laundering and the judge combination rule; selection effects (laundering is
measured among violators); pooling across packages and tasks; the monitor design and blinding; the tests chosen
for H1, H2, H3, H-D and the Holm family; power; exclusions and the fallback rules; the defense notes' matching;
anything a judge would call p-hacking, garden of forking paths, or overclaiming. Be specific; no generic advice.
Answer in English, plain text, at most 900 words.

=== PLAN ===
{plan}

=== power_out.txt ===
{power}
"""
body = json.dumps({"model": model, "input": prompt, "max_output_tokens": 6000}).encode()
req = urllib.request.Request("https://api.prod.adaptionlabs.ai/api/v1/responses", data=body, method="POST",
                             headers={"Content-Type": "application/json",
                                      "Authorization": "Bearer " + os.environ["ADAPTION_API_KEY"]})
with urllib.request.urlopen(req, timeout=600) as r:
    resp = json.load(r)
text = ""
for item in resp.get("output", []):
    for c in item.get("content", []) or []:
        if c.get("type") in ("output_text", "text"):
            text += c.get("text", "")
json.dump({"model": model, "returned_model": resp.get("model"), "usage": resp.get("usage"), "text": text},
          open(out, "w"), indent=1, ensure_ascii=False)
open(out.replace(".json", ".txt"), "w").write(text)
print(model, "->", out, len(text), "chars")
