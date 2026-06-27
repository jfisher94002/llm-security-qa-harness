# LLM-03 Supply Chain Demo Walkthrough

This demo covers the three-tier supply chain harness for LLM-03. Each tier covers a different failure mode and stops the harness if it fails.

## Prerequisites

- Python 3.9+
- `pip-audit` and `pip-licenses` installed: `pip install pip-audit pip-licenses`
- Ollama running locally with at least one model pulled (for Tier 3)
- A requirements file to scan (Tier 1)
- A model file to verify (Tier 2, optional for walkthrough)

## Tier 1: Static Code Checks

### What it tests
Dependency CVEs and license compliance before the model is touched.

### Run it

```bash
# Scan your requirements file
python3 llm03/tier1_static/run_tier1.py --requirements requirements.txt

# Write artifacts to a specific directory
python3 llm03/tier1_static/run_tier1.py --requirements requirements.txt --output ./tmp_results/tier1
```

### Fail signal
- Any CVE with a fix available in a production dependency
- Any GPL or AGPL license in a production dependency without documented approval

### Evidence produced
- `dep_scan.json` — full pip-audit output, findings, and exit code
- `license_scan.json` — full pip-licenses report and restricted findings

---

## Tier 2: Asset Identity Check

### What it tests
Whether the local model file matches the approved artifact in the release manifest.

### Setup
1. Add your approved model to `llm03/release_manifest.json`
2. Compute the SHA-256 hash of the exact file the pipeline will load:

```bash
python3 -c "
import hashlib
with open('your_model.safetensors', 'rb') as f:
    print(hashlib.sha256(f.read()).hexdigest())
"
```

3. Add that hash to the manifest entry.

### Run it

```bash
python3 llm03/tier2_identity/run_tier2.py \
    --model-file ./your_model.safetensors \
    --manifest llm03/release_manifest.json
```

### Fail signal
- Hash does not match the manifest entry
- No manifest entry exists for the file
- Manifest entry still has the placeholder hash

### Evidence produced
- `hash_check.json` — expected hash, actual hash, file size, match result

---

## Tier 3: Behavioral Regression

### What it tests
Whether the current model still behaves within the approved release baseline.

### Step 1: Record a baseline

```bash
python3 llm03/tier3_behavioral/run_probes.py \
    --model llama3.2:3b \
    --output llm03/tier3_behavioral/baseline.json
```

### Step 2: Run current probes after a change

```bash
python3 llm03/tier3_behavioral/run_probes.py \
    --model llama3.2:3b \
    --output llm03/sample_outputs/current.json
```

### Step 3: Compare

```bash
python3 llm03/tier3_behavioral/compare_responses.py \
    --baseline llm03/tier3_behavioral/baseline.json \
    --current llm03/sample_outputs/current.json \
    --output llm03/sample_outputs/tier3/results.json
```

### Fail signal
- A refusal prompt now produces a response containing failure keywords
- A keyword-match prompt is missing required keywords

### Evidence produced
- `baseline.json` — approved baseline responses
- `current.json` — current run responses
- `results.json` — per-prompt comparison, overall pass/fail

---

## Full Tiered Run

### Pre-merge gate (Tier 1 only)

```bash
python3 llm03/run_llm03.py --gate pre-merge --requirements requirements.txt
```

### Pre-deployment gate (Tier 1 + Tier 2)

```bash
python3 llm03/run_llm03.py --gate pre-deploy \
    --requirements requirements.txt \
    --model-file ./your_model.safetensors
```

### Release gate (full suite)

```bash
python3 llm03/run_llm03.py --gate release \
    --requirements requirements.txt \
    --model-file ./your_model.safetensors \
    --model llama3.2:3b \
    --baseline llm03/tier3_behavioral/baseline.json
```

### CI/CD integration

The harness exits 0 on pass and 1 on any failure. Wire it into your pipeline as a blocking step.

```yaml
# GitHub Actions example
- name: LLM-03 pre-merge supply chain check
  run: python3 llm03/run_llm03.py --gate pre-merge --requirements requirements.txt
```

---

## Adding Your Own Prompts

Edit `llm03/tier3_behavioral/prompts.json`. Each prompt needs:

- `id` — unique identifier
- `prompt` — the exact text sent to the model
- `check_type` — `refusal` or `keyword_match`
- `failure_keywords` (refusal) or `required_keywords` (keyword_match)
- `pass_condition` — plain-language description of what passing looks like

---

## What This Does Not Prove

- A passing Tier 1 does not mean the model artifact is safe.
- A passing Tier 2 does not mean the model behaves correctly.
- A passing Tier 3 does not mean the supply chain is fully verified.

Each tier covers a different failure mode. All three need to pass for a release gate to hold.
