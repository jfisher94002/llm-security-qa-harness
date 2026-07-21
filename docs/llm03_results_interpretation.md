# LLM03 Results Interpretation

This guide explains how to read the Supply Chain Security Automation Lab artifacts.

Passing the lab does not prove a model, dependency set, artifact, or deployment pipeline is secure. It only means the configured checks reached a passing decision for the supplied inputs.

## Exit Codes

| Code | Meaning | Typical action |
|------|---------|----------------|
| 0 | Passed, including recorded non-critical CVE warnings | Preserve evidence and continue |
| 1 | Human review required | Review `review_gate.json` before proceeding |
| 2 | Deterministic hard block | Stop the release until the blocking condition is fixed |
| 3 | Invalid configuration or tool failure | Fix inputs, missing files, malformed JSON, or unavailable tools |

## Gate Result

Every `llm03/run_llm03.py` run writes:

```text
gate_result.json
```

Use it first. It records:

- gate mode: `pre-merge`, `pre-deploy`, or `release`
- expected tier order
- tiers actually executed
- stop point, when any tier stopped the gate
- final exit code
- paths to tier evidence

## Tier 1: Static Checks

Tier 1 writes:

- `dep_scan.json`
- `license_scan.json`
- `tier1_result.json`
- `review_gate.json`, only when human review is required

Dependency findings are interpreted with `llm03/policies/vulnerability_severity.json`.

- mapped Critical CVE: hard block
- mapped non-critical CVE: warning, exit 0
- unmapped CVE severity: review required

License findings are interpreted with `llm03/policies/license_exceptions.json`.

- no restricted license: pass
- restricted license with valid exception: pass, but keep evidence
- restricted license without a valid exception: review required
- expired exception: review required

The license scan must use a target dependency inventory. A scan of the wrong Python environment is not useful release evidence.

## Generating A Target License Inventory

Use two environments:

- `lab-tools`: contains the harness and scanners from `requirements.txt`
- `target`: contains only the application dependencies being evaluated

Run `pip-licenses` from `lab-tools` with `--target-python` pointing at the target environment. This keeps scanner dependencies such as `pip-licenses` out of the target license inventory.

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
python3 llm03/run_llm03.py --gate pre-merge \
    --requirements requirements.txt \
    --license-inventory-json target_license_inventory.json
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
python llm03\run_llm03.py --gate pre-merge `
    --requirements requirements.txt `
    --license-inventory-json target_license_inventory.json
```

The generator records the requirements filename, requirements SHA-256, generator path, lab-tools Python version, target Python executable name, generation timestamp, and package list. It does not record absolute local paths.

## Tier 2: Asset Identity

Tier 2 writes:

```text
hash_check.json
```

Hard-block examples:

- no manifest entry for the artifact
- placeholder hash in the manifest
- SHA-256 mismatch
- configured Ed25519 signature does not verify

The fixture artifact under `llm03/fixtures/tier2/` is fake training data. Do not treat it as a model.

## Tier 3: Behavioral Regression

Each prompt in `llm03/tier3_behavioral/prompts.json` has a `baseline_similarity_threshold`. The comparator normalizes whitespace/case and uses `difflib.SequenceMatcher`; a prompt must pass both its configured rule and its similarity threshold.

Tier 3 writes:

- current response artifact, unless supplied with `--current-responses-json`
- `results.json`

Behavioral drift exits `1` because it needs human review. The comparator does not prove the new model is unsafe; it shows that the configured rule or baseline similarity checks changed enough to require review.

If `run_probes.py` fails, the gate stops before comparison. A failed probe run is a tool/configuration failure, not behavioral evidence.

## Review Gate

When a gate exits `1`, read:

```text
review_gate.json
```

It should answer:

- what stopped the gate
- which tier produced the review item
- which finding or comparison requires review
- what evidence file supports the decision

Approval records should be explicit, time-bounded when appropriate, and tied to a ticket. Sample records are in `sample_outputs/llm03_supply_chain/review_examples/approval_records/`.

## Confirmed Failure To Regression Test

When a real review confirms that a failure matters:

1. Keep the failing evidence.
2. Add or tighten a fixture, prompt, policy mapping, or license exception test.
3. Add a unittest that reproduces the failure offline.
4. Re-run the gate and keep the passing regression evidence.

See `sample_outputs/llm03_supply_chain/confirmed_failure_to_regression_test/` for a fake example of this loop.
