# LLM03 Lab Quickstart

Python 3.10 or newer is required.

Install lab-tool dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Run the offline pre-merge gate:

```bash
python3 llm03/run_llm03.py --gate pre-merge \
    --pip-audit-json llm03/fixtures/tier1/pip_audit_pass.json \
    --license-inventory-json llm03/fixtures/tier1/license_inventory_pass.json \
    --output ./tmp_results/llm03-pre-merge
```

Run the offline pre-deploy gate:

```bash
python3 llm03/run_llm03.py --gate pre-deploy \
    --pip-audit-json llm03/fixtures/tier1/pip_audit_pass.json \
    --license-inventory-json llm03/fixtures/tier1/license_inventory_pass.json \
    --model-file llm03/fixtures/tier2/approved_artifact.txt \
    --manifest llm03/fixtures/tier2/release_manifest.fixture.json \
    --model fixture-model \
    --baseline llm03/fixtures/tier3/baseline_pass.json \
    --current-responses-json llm03/fixtures/tier3/current_pass.json \
    --output ./tmp_results/llm03-pre-deploy
```

For live license inventory generation, use two environments: a lab-tools environment with this package and scanners installed, and a separate target environment containing only the application dependencies being evaluated. The target environment installs the application requirements file, not this package requirements file.

macOS/Linux:

```bash
TARGET_REQUIREMENTS=/path/to/application/requirements.txt

python3 -m venv .venv-llm03-tools
source .venv-llm03-tools/bin/activate
python3 -m pip install -r requirements.txt

python3 -m venv .venv-llm03-target
.venv-llm03-target/bin/python -m pip install -r "$TARGET_REQUIREMENTS"

python3 llm03/tier1_static/generate_license_inventory.py \
    --requirements "$TARGET_REQUIREMENTS" \
    --target-python .venv-llm03-target/bin/python \
    --output target_license_inventory.json

python3 llm03/run_llm03.py --gate pre-merge \
    --requirements "$TARGET_REQUIREMENTS" \
    --license-inventory-json target_license_inventory.json
```

Windows PowerShell:

```powershell
$TARGET_REQUIREMENTS = "C:\path\to\application\requirements.txt"

py -3.10 -m venv .venv-llm03-tools
.\.venv-llm03-tools\Scripts\Activate.ps1
python -m pip install -r requirements.txt

py -3.10 -m venv .venv-llm03-target
.\.venv-llm03-target\Scripts\python.exe -m pip install -r $TARGET_REQUIREMENTS

python llm03\tier1_static\generate_license_inventory.py `
    --requirements $TARGET_REQUIREMENTS `
    --target-python .\.venv-llm03-target\Scripts\python.exe `
    --output target_license_inventory.json

python llm03\run_llm03.py --gate pre-merge `
    --requirements $TARGET_REQUIREMENTS `
    --license-inventory-json target_license_inventory.json
```

Tier 3 prompts include per-prompt `baseline_similarity_threshold` values. A prompt passes only when its rule check passes and its current response remains similar enough to the approved baseline.
