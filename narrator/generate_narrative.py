"""Part 3 — GenAI-powered insight narrator (SCR structure).

Reads narrator/findings.json (written by analysis/clean_and_eda.py) and turns
it into a Situation–Complication–Resolution narrative for Mamaearth's regional
ops and finance heads.

  * Online path : Gemini via the google-genai client (free Google AI Studio key).
  * Offline path: deterministic f-string template — no key, no network.

Usage (from the repo root):
  python narrator/generate_narrative.py                 # Gemini if a key is set, else offline
  python narrator/generate_narrative.py --offline       # force the offline template
  python narrator/generate_narrative.py --check narrator/sample_output.txt

Set a key with:  export GEMINI_API_KEY="your-free-ai-studio-key"
"""
import argparse
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")  # silence third-party Python 3.9 / SSL deprecation noise
from pathlib import Path

HERE = Path(__file__).resolve().parent
FINDINGS_PATH = HERE / "findings.json"
SAMPLE_PATH = HERE / "sample_output.txt"
OFFLINE_PATH = HERE / "offline_output.txt"

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
# Explicit, not the API default. Gemini 3 "thinking" models count their hidden
# reasoning against this limit, so it must cover thinking + the ~250-word answer.
MAX_OUTPUT_TOKENS = 4096
THINKING_BUDGET = 1024     # cap on reasoning tokens, leaving ~3000 for the narrative
TIMEOUT_MS = 30_000        # HttpOptions timeout is in milliseconds (30 s, above the 10 s minimum)

SYSTEM_INSTRUCTION = (
    "You are a senior data analyst writing for Mamaearth's regional ops and finance heads. "
    "Write a concise business narrative of about 250 words in exactly three labeled sections, "
    "in this order: 'Situation:', 'Complication:', 'Resolution:'. "
    "Every number you write must come from the supplied findings and must appear with exactly "
    "the same value (you may add thousands separators and the ₹ symbol). Do not invent, "
    "estimate, round differently, or derive any new statistic. Name months by their full name "
    "(e.g. 2026-03 is March). Use plain text only, no markdown tables."
)


def _api_key():
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def _month_name(ym):
    import datetime
    return datetime.datetime.strptime(ym, "%Y-%m").strftime("%B %Y")


def build_user_prompt(findings: dict) -> str:
    """Interpolate every figure from the findings dict — nothing is hardcoded."""
    f = findings
    rates = f["return_rate_by_payment"]
    seg = f["highest_risk_segment"]
    peak = f["true_peak_month"]
    infl = f["outlier_inflated_month"]
    rate_lines = "\n".join(f"  - {pm}: {r}%" for pm, r in rates.items())
    return (
        "Write the SCR narrative from these verified findings (Jan–Jun 2026 order data):\n\n"
        f"- Cleaned total revenue: INR {f['cleaned_total_revenue_inr']:,.2f}\n"
        f"- Raw total revenue (before cleaning): INR {f['raw_total_revenue_inr']:,.2f}\n"
        f"- Difference explained entirely by duplicate (double-submitted) orders removed: "
        f"INR {f['duplicate_reconciliation_delta_inr']:,.2f}\n"
        f"- Return rate by payment method:\n{rate_lines}\n"
        f"- Highest-risk segment: {seg['payment_method']} orders in Tier-{seg['city_tier']} "
        f"cities, return rate {seg['return_rate_pct']}%\n"
        f"- True peak revenue month (bulk outliers excluded): {_month_name(peak['month'])} "
        f"({peak['month']}), INR {peak['revenue_inr']:,.2f}\n"
        f"- Outlier-inflated month: {_month_name(infl['month'])} ({infl['month']}) looked like "
        f"INR {infl['apparent_revenue_inr']:,.2f} but is INR {infl['corrected_revenue_inr']:,.2f} "
        "once two bulk orders are excluded\n\n"
        "Situation: the revenue picture after cleaning. Complication: where returns are really "
        "concentrated and why the blended rate and the raw monthly trend mislead. Resolution: "
        "concrete actions for ops and finance."
    )


def generate_scr_narrative(findings: dict, fallback: bool = True) -> dict:
    """Generate the SCR narrative with Gemini.

    Returns {"status": "success", "narrative": str, "tokens": int, ...} or
    {"status": "error", "narrative": None, "message": str}. The caller never
    receives a raw exception. With fallback=True (default), a missing key or an
    API error falls back to generate_scr_narrative_offline().
    """
    api_key = _api_key()
    if not api_key:
        if fallback:
            result = generate_scr_narrative_offline(findings)
            result["fallback_reason"] = "No GEMINI_API_KEY / GOOGLE_API_KEY set"
            return result
        return {"status": "error", "narrative": None, "message": "No API key configured"}

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=TIMEOUT_MS),
        )
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            # temperature 0.0: this is a factual business report, not creative writing —
            # we want the most deterministic, number-faithful output the model can give.
            temperature=0.0,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            thinking_config=types.ThinkingConfig(thinking_budget=THINKING_BUDGET),
        )
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=build_user_prompt(findings),
            config=config,
        )
        finish = response.candidates[0].finish_reason if response.candidates else None
        if finish == types.FinishReason.MAX_TOKENS:
            raise RuntimeError("Gemini response was cut off at max_output_tokens (truncated narrative)")
        # Join only the visible answer parts (skip thought/signature parts).
        parts = response.candidates[0].content.parts or []
        text = "".join(p.text for p in parts if p.text and not getattr(p, "thought", False))
        if not text:
            raise RuntimeError("Gemini returned an empty response")
        usage = getattr(response, "usage_metadata", None)
        tokens = getattr(usage, "total_token_count", None) if usage else None
        return {"status": "success", "narrative": text.strip(), "tokens": tokens,
                "source": f"gemini:{GEMINI_MODEL}"}
    except Exception as err:  # noqa: BLE001 — caller must never see a raw exception
        error = {"status": "error", "narrative": None, "message": str(err)}
        if fallback:
            result = generate_scr_narrative_offline(findings)
            result["fallback_reason"] = f"Gemini call failed: {err}"
            return result
        return error


def generate_scr_narrative_offline(findings: dict) -> dict:
    """Deterministic, keyless SCR narrative built only from the findings dict."""
    f = findings
    rates = f["return_rate_by_payment"]
    seg = f["highest_risk_segment"]
    peak = f["true_peak_month"]
    infl = f["outlier_inflated_month"]
    prepaid = {k: v for k, v in rates.items() if k != seg["payment_method"]}
    prepaid_txt = " and ".join(f"{k} at {v}%" for k, v in prepaid.items())

    narrative = (
        "Situation:\n"
        f"Across January–June 2026, Mamaearth's verified net revenue is ₹{f['cleaned_total_revenue_inr']:,.2f}. "
        f"The raw order table reported ₹{f['raw_total_revenue_inr']:,.2f}, but ₹{f['duplicate_reconciliation_delta_inr']:,.2f} "
        "of that came from double-submitted duplicate orders, which have been removed. "
        f"Revenue genuinely peaked in {_month_name(peak['month'])} at ₹{peak['revenue_inr']:,.2f}.\n\n"
        "Complication:\n"
        f"Returns are concentrated in Cash-on-Delivery: COD orders come back at {rates['COD']}%, "
        f"versus {prepaid_txt}. The blended COD rate still hides the worst pocket — "
        f"{seg['payment_method']} orders in Tier-{seg['city_tier']} cities return at {seg['return_rate_pct']}%, "
        "more than one in two. The raw monthly trend is also misleading: "
        f"{_month_name(infl['month'])} appears to lead at ₹{infl['apparent_revenue_inr']:,.2f}, "
        "but only because two bulk orders landed that month; without them it is "
        f"₹{infl['corrected_revenue_inr']:,.2f}.\n\n"
        "Resolution:\n"
        f"1. Ops: target {seg['payment_method']} in Tier-{seg['city_tier']} cities first — add order "
        "confirmation calls, prepaid-conversion incentives, or a COD fee for repeat returners.\n"
        "2. Finance: plan and forecast on the cleaned revenue base, and fix the double-submit bug "
        "at checkout so duplicates stop inflating reported sales.\n"
        f"3. Growth: benchmark campaigns against {_month_name(peak['month'])} as the true peak, and "
        "report bulk orders separately so they do not distort monthly trends."
    )
    return {"status": "success", "narrative": narrative, "tokens": 0, "source": "offline-template"}


def check_numeric_accuracy(narrative: str, findings: dict) -> bool:
    """Assert the five key figures appear in the narrative; print pass/fail per figure."""
    text = narrative.replace(",", "")
    peak = findings["true_peak_month"]
    peak_month_name = _month_name(peak["month"]).split()[0]

    def num(x, dp=1):
        # "97358.3" also matches "97358.30"; "44.4" stays "44.4".
        return f"{x:.{dp}f}".rstrip("0").rstrip(".") if dp > 1 else f"{x:.{dp}f}"

    checks = [
        ("Cleaned total revenue", [num(findings["cleaned_total_revenue_inr"], 2)]),
        ("COD return rate", [num(findings["return_rate_by_payment"]["COD"])]),
        ("Highest-risk segment rate", [num(findings["highest_risk_segment"]["return_rate_pct"])]),
        ("Duplicate reconciliation delta", [num(findings["duplicate_reconciliation_delta_inr"], 2)]),
        ("True peak month + revenue", [peak_month_name, num(peak["revenue_inr"], 2)]),
    ]
    all_ok = True
    print("\nNumeric accuracy checklist:")
    for label, needles in checks:
        ok = all(n in text for n in needles)
        all_ok &= ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}: {' + '.join(needles)}")
    print(f"Overall: {'PASS' if all_ok else 'FAIL'}")
    return all_ok


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--offline", action="store_true", help="force the keyless offline template")
    parser.add_argument("--check", metavar="FILE", help="only run the checker against a saved narrative")
    args = parser.parse_args()

    if not FINDINGS_PATH.exists():
        sys.exit("narrator/findings.json not found — run analysis/clean_and_eda.py first.")
    findings = json.loads(FINDINGS_PATH.read_text(encoding="utf-8"))

    if args.check:
        check_path = Path(args.check)
        if not check_path.exists():
            sys.exit(f"{check_path} not found — run with GEMINI_API_KEY set to create it.")
        ok = check_numeric_accuracy(check_path.read_text(encoding="utf-8"), findings)
        sys.exit(0 if ok else 1)

    result = generate_scr_narrative_offline(findings) if args.offline else generate_scr_narrative(findings)
    print(f"Source: {result.get('source')}  |  status: {result['status']}  |  tokens: {result.get('tokens')}")
    if result.get("fallback_reason"):
        print(f"(Fell back to offline path — {result['fallback_reason']})")
    if result["status"] != "success":
        sys.exit(f"Narrative generation failed: {result.get('message')}")

    print("\n" + "-" * 72 + "\n" + result["narrative"] + "\n" + "-" * 72)

    # Save the output so the checker can be run against a file, not just live output.
    out_path = SAMPLE_PATH if result["source"].startswith("gemini") else OFFLINE_PATH
    out_path.write_text(result["narrative"] + "\n", encoding="utf-8")
    print(f"Saved narrative to {out_path.relative_to(HERE.parent)}")

    ok = check_numeric_accuracy(result["narrative"], findings)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
