# LLM-03 Supply Chain Demo Walkthrough

This demo covers the three-tier supply chain harness for LLM-03. Each tier covers a different failure mode and stops the harness if it fails.

## Prerequisites

- Python 3.10 or newer
- a lab-tools environment with `cryptography`, `requests`, `pip-audit`, and `pip-licenses` installed with `python3 -m pip install -r requirements.txt`
- a separate target environment containing only the application dependencies being evaluated
- Ollama running locally with at least one model pulled (for Tier 3)
- A requirements file and target license inventory to scan (Tier 1 live mode)
- A model file to verify (Tier 2, optional for walkthrough)

## Tier 1: Static Code Checks

### What it tests
Dependency CVEs and license compliance before the model is touched.

### Run it

```bash
# Offline course fixture
python3 llm03/tier1_static/run_tier1.py \
    --pip-audit-json llm03/fixtures/tier1/pip_audit_pass.json \
    --license-inventory-json llm03/fixtures/tier1/license_inventory_pass.json

# Live scan against a target dependency inventory
python3 llm03/tier1_static/run_tier1.py \
    --requirements requirements.txt \
    --license-inventory-json ./target_license_inventory.json \
    --output ./tmp_results/tier1
```

### Generate a live target license inventory

macOS/Linux:

```bash
python3 -m venv .venv-llm03-tools
source .venv-llm03-tools/bin/activate
python3 -m pip install -r requirements.txt

python3 -m venv .venv-llm03-target
.venv-llm03-target/bin/python -m pip install -r requirements.txt

python3 llm03/tier1_static/generate_license_inventory.py \
    --requirements requirements.txt \
    --target-python .venv-llm03-target/bin/python \
    --output target_license_inventory.json
```

Windows PowerShell:

```powershell
py -3.10 -m venv .venv-llm03-tools
.\.venv-llm03-tools\Scripts\Activate.ps1
python -m pip install -r requirements.txt

py -3.10 -m venv .venv-llm03-target
.\.venv-llm03-target\Scripts\python.exe -m pip install -r requirements.txt

python llm03\tier1_static\generate_license_inventory.py `
    --requirements requirements.txt `
    --target-python .\.venv-llm03-target\Scripts\python.exe `
    --output target_license_inventory.json
```

The scanner runs from the lab-tools environment and inspects the target Python environment, so the inventory does not include `pip-licenses` merely because the scanner is installed.

### Fail signal
- A mapped Critical CVE is a hard block
- A known non-critical CVE is recorded as a warning and does not block
- An unknown CVE severity requires review
- An unapproved or expired restricted-license exception requires review
- A valid license exception clears the review gate but remains in the evidence

### Evidence produced
- `dep_scan.json` — full pip-audit output, findings, and exit code
- `license_scan.json` — target license inventory and restricted findings
- `review_gate.json` — only when human review is required

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
    --model-file llm03/fixtures/tier2/approved_artifact.txt \
    --manifest llm03/fixtures/tier2/release_manifest.fixture.json
```

### Fail signal
- Hash does not match the manifest entry
- Ed25519 signature verification fails
- No manifest entry exists for the file
- Manifest entry still has the placeholder hash

### Evidence produced
- `hash_check.json` — expected hash, actual hash, file size, signature status, match result

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
- A current response is below the prompt's configured `baseline_similarity_threshold`

### Evidence produced
- `baseline.json` — approved baseline responses
- `current.json` — current run responses
- `results.json` — per-prompt rule result, baseline similarity score, configured threshold, drift result, and final prompt result

---

## Full Tiered Run

### Pre-merge gate (Tier 1 only)

```bash
python3 llm03/run_llm03.py --gate pre-merge \
    --pip-audit-json llm03/fixtures/tier1/pip_audit_pass.json \
    --license-inventory-json llm03/fixtures/tier1/license_inventory_pass.json
```

### Pre-deployment gate (Tier 1 + Tier 2 + Tier 3)

```bash
python3 llm03/run_llm03.py --gate pre-deploy \
    --pip-audit-json llm03/fixtures/tier1/pip_audit_pass.json \
    --license-inventory-json llm03/fixtures/tier1/license_inventory_pass.json \
    --model-file llm03/fixtures/tier2/approved_artifact.txt \
    --manifest llm03/fixtures/tier2/release_manifest.fixture.json \
    --model fixture-model \
    --baseline llm03/fixtures/tier3/baseline_pass.json \
    --current-responses-json llm03/fixtures/tier3/current_pass.json
```

### Release gate (full suite)

```bash
python3 llm03/run_llm03.py --gate release \
    --pip-audit-json llm03/fixtures/tier1/pip_audit_pass.json \
    --license-inventory-json ./target_license_inventory.json \
    --model-file ./your_model.safetensors \
    --model llama3.2:3b \
    --baseline llm03/tier3_behavioral/baseline.json
```

### CI/CD integration

The harness exits with distinct codes for pass, review, hard block, and invalid configuration. Wire nonzero results into your pipeline policy instead of treating every nonzero result as the same failure.

```yaml
- name: LLM-03 pre-merge supply chain check
  run: >
    python3 llm03/run_llm03.py --gate pre-merge
    --pip-audit-json llm03/fixtures/tier1/pip_audit_pass.json
    --license-inventory-json llm03/fixtures/tier1/license_inventory_pass.json
```

Exit codes:

- `0` passed, including recorded non-critical CVE warnings
- `1` human review required
- `2` deterministic hard block
- `3` invalid configuration or tool failure

---

## Adding Your Own Prompts

Edit `llm03/tier3_behavioral/prompts.json`. Each prompt needs:

- `id` — unique identifier
- `prompt` — the exact text sent to the model
- `check_type` — `refusal` or `keyword_match`
- `baseline_similarity_threshold` — deterministic normalized-text similarity threshold from 0.0 to 1.0
- `failure_keywords` (refusal) or `required_keywords` (keyword_match)
- `pass_condition` — plain-language description of what passing looks like

---

## What This Does Not Prove

- A passing Tier 1 does not mean the model artifact is safe.
- A passing Tier 2 does not mean the model behaves correctly.
- A passing Tier 3 does not mean the supply chain is fully verified.

Each tier covers a different failure mode. All three need to pass for a release gate to hold.
