# Quickstart

This quickstart runs the harness locally with the default mock adapter.

## 1. Check Python

Python 3.10 or newer is required.

```bash
python3 --version
```

## 2. Install Requirements

The default harness uses only the Python standard library. This command is still safe and keeps the workflow familiar:

```bash
python3 -m pip install -r requirements.txt
```

## 3. Run The Starter Cases

```bash
python3 runner/run_tests.py
```

Expected outputs:

```text
sample_outputs/run_log.csv
sample_outputs/failures.json
sample_outputs/summary.md
```

## 4. Repeat Each Case

Repeated runs help expose nondeterministic failures when you connect a real model.

```bash
python3 runner/run_tests.py --runs 5
```

## 5. Try A Real Adapter

Ollama example:

```bash
cp config/ollama.example.yaml config/ollama.local.yaml
python3 runner/run_tests.py --config config/ollama.local.yaml
```

OpenAI example:

```bash
cp config/openai.example.yaml config/openai.local.yaml
export OPENAI_API_KEY="replace-with-your-key"
python3 runner/run_tests.py --config config/openai.local.yaml
```

Never commit real API keys, tokens, private prompts, customer records, or production retrieval documents.

## 6. Read Results Carefully

A pass means the response did not contain the configured failure indicators. It does not prove the system is secure, robust, compliant, or safe against variants of the same attack.
