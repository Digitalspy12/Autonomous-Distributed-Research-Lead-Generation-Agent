"""Integration test: verify full fallback chain via LLM client."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Disable cloud providers to force Ollama fallback
os.environ["GEMINI_ENABLED"] = "false"
os.environ["GROQ_ENABLED"] = "false"
os.environ["SKIP_ON_NO_LLM"] = "true"

from src.core.llm_client import call_llm

prompt = """You are an operations analyst specializing in B2B automation opportunities.

Analyze this job posting and generate a "Pain Hypothesis".

Job Title: Data Entry Clerk
Company: TestCo
Location: Pune
Description: Manual data entry position, involves spreadsheet reconciliation and reporting.

Output ONLY valid JSON (no markdown, no backticks, no extra text):
{
  "pain_hypothesis": "A 2-sentence inference about what operational pain this hire reveals",
  "primary_process": "The main business process this role supports",
  "tech_stack": ["tools/platforms mentioned or implied"],
  "integration_gaps": ["gaps between systems that cause manual work"],
  "automatibility_score": 8,
  "confidence": 7,
  "verdict": "PASS"
}"""

print("Testing Ollama-only fallback via LLM client...")
try:
    result = call_llm(
        prompt=prompt,
        node="analyst",
        required_keys=["pain_hypothesis", "automatibility_score", "verdict"],
    )
    print(f"\nSUCCESS!")
    print(f"Provider: {result.provider}")
    print(f"Model: {result.model}")
    print(f"Latency: {result.latency_ms}ms")
    if result.parsed:
        print(f"Parsed keys: {list(result.parsed.keys())}")
        print(f"Verdict: {result.parsed.get('verdict')}")
        print(f"Score: {result.parsed.get('automatibility_score')}")
        print(f"Pain: {str(result.parsed.get('pain_hypothesis', ''))[:100]}")
    else:
        print("WARNING: parsed is None")
except RuntimeError as e:
    print(f"FAILED: {e}")

# Check log file
from pathlib import Path
log_file = Path("data/llm_calls.jsonl")
if log_file.exists():
    lines = log_file.read_text().strip().split("\n")
    print(f"\nLog file has {len(lines)} entries (last entry below):")
    print(lines[-1][:200])
else:
    print("\nWARNING: Log file not created")

print("\nTest complete!")
