# LLM03 Supply Chain Security Automation Lab v1

This package is a standalone teaching subset for the OWASP LLM-03 Supply Chain Security Automation Lab.

It contains fake, reproducible fixtures only. It does not contain real credentials, real customer data, real private prompts, real model files, or real vulnerability records.

## Start

Install dependencies:

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

Then read:

- `QUICKSTART.md`
- `demos/llm03_supply_chain_demo.md`
- `docs/llm03_results_interpretation.md`

Passing the lab checks does not prove a model, dependency set, artifact, or deployment pipeline is secure.
