# Interpreting Results

The reports are designed for fast triage, not final security certification.

## run_log.csv

This file has one row per case run. Use it to compare repeated runs and inspect raw responses.

Important columns:

- `case_id`
- `owasp_id`
- `repeat_index`
- `adapter`
- `model`
- `pass`
- `evaluator_mode`
- `matched_indicators`
- `prompt_template`
- `rendered_prompt`
- `response`

## failures.json

This file contains only failed runs and includes the expected safe behavior, evaluator mode, prompt template, rendered prompt, and response for each failed case. Use it as the first stop for debugging.

## summary.md

This file gives aggregate pass/fail counts by OWASP category.

## What A Pass Means

A pass means no configured failure indicator appeared in the response. It does not mean the application is secure, and it does not cover attack variants that are not represented in the test cases.

## What A Failure Means

A failure means at least one configured indicator appeared in the response. Review the full prompt, asset, response, and indicator before deciding whether the issue is a true security regression or an evaluator false positive.

The checked-in `sample_outputs/mock_failure_demo/` folder shows fake failed runs so students can see the evidence shape before connecting a real model or application.
