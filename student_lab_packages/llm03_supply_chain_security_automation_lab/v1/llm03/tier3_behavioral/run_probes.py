#!/usr/bin/env python3
"""
LLM-03 Tier 3: Behavioral Layer — Probe Runner
Sends fixed prompts to the target model at temperature 0 in fresh sessions.
Saves responses as a baseline or current run artifact.

Usage:
    # Record baseline
    python3 llm03/tier3_behavioral/run_probes.py --model llama3.2:3b --output llm03/tier3_behavioral/baseline.json

    # Record current run for comparison
    python3 llm03/tier3_behavioral/run_probes.py --model llama3.2:3b --output llm03/tier3_behavioral/current.json

Requires Ollama running locally. For other backends, replace the query_model function.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    print("requests not installed. Run: pip install requests")
    sys.exit(3)


OLLAMA_URL = "http://localhost:11434/api/generate"


def query_model(model, prompt, temperature=0):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature}
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        print(f"  ERROR — Cannot reach Ollama at {OLLAMA_URL}")
        print("  Ensure Ollama is running: ollama serve")
        sys.exit(3)
    except Exception as e:
        print(f"  ERROR — {e}")
        sys.exit(3)


def main():
    parser = argparse.ArgumentParser(description="LLM-03 Tier 3: Behavioral probe runner")
    parser.add_argument("--model", required=True, help="Ollama model tag (e.g. llama3.2:3b)")
    parser.add_argument("--prompts", default="llm03/tier3_behavioral/prompts.json", help="Path to prompts file")
    parser.add_argument("--output", required=True, help="Output path for run artifact (e.g. baseline.json)")
    parser.add_argument("--temp", type=float, default=0, help="Model temperature (default: 0)")
    args = parser.parse_args()

    if not os.path.exists(args.prompts):
        print(f"Prompts file not found: {args.prompts}")
        sys.exit(3)

    with open(args.prompts) as f:
        prompt_data = json.load(f)

    prompts = prompt_data.get("prompts", [])
    if not prompts:
        print("ERROR — Prompts file contains zero configured prompts.")
        sys.exit(3)
    print(f"Running {len(prompts)} probe(s) against model: {args.model}")
    print(f"Temperature: {args.temp} | Fresh sessions: yes\n")

    results = []
    for p in prompts:
        print(f"  Probing: {p['id']}")
        response = query_model(args.model, p["prompt"], temperature=args.temp)
        if not isinstance(response, str) or not response.strip():
            print(f"  ERROR — Model returned an empty response for prompt: {p['id']}")
            print("  Treating this as a tool/model failure; no valid response artifact will be saved.")
            sys.exit(3)
        results.append({
            "id": p["id"],
            "prompt": p["prompt"],
            "response": response,
            "check_type": p.get("check_type"),
            "model": args.model,
            "temperature": args.temp,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        print(f"    Response length: {len(response)} chars")

    if not results:
        print("ERROR — No probe results were produced.")
        sys.exit(3)

    artifact = {
        "model": args.model,
        "temperature": args.temp,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt_count": len(results),
        "results": results
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(artifact, f, indent=2)

    print(f"\nArtifact saved: {args.output}")


if __name__ == "__main__":
    main()
