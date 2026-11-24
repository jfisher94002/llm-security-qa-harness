# Course 5: Excessive agency automation

This is a draft contribution for review. It reuses the refund application from
the Course 5 Demo C recording package and adds a small set of readable examples.
The examples exercise scripted application requests against a local SQLite
database with synthetic data. No AI model or payment service is used.

## Run the student examples

From the repository root, with Python 3.12:

```sh
python3 -m unittest discover -s tests -p 'test_course05_student_examples.py' -v
```

Each test creates a fresh database. The tests check the offered tool catalog,
cross-tenant access, a missing approval, an approved refund, a revised proposal
and a retry. The refund tests check relevant responses, recorded decisions and
independently read ledger state. The retry also checks the original receipt. The
cross-tenant test checks the denial, recorded access decision and delivered
content. The catalog test checks the offered tools for a restricted task. It
only establishes what this fixture offers, not what every feature needs.

For the full imported lab test suite and fixture verification:

```sh
python3 -m unittest discover -s tests -p 'test_course05_lab2.py' -v
python3 -m course05.lab2 verify
```

Fixture verification includes intentional failing and error scenarios. A PASS
summary means their observed outcomes matched expectations. It does not mean
every simulated application was secure. Verification writes local files under
`tmp_results/course05-lab2/`.

To reproduce the recorded missing-approval example:

```sh
python3 -m course05.lab2 run --case missing
```

The command executes a scripted case, saves evidence and displays a summary.
The local ledger is a simulation. This package does not demonstrate live-model
behavior, actual payment delivery or production authorization. It does not prove
concurrency safety or durability across real process crashes.

## Provenance and scope

The `course05` application, its original test module and `lab2-tools` were copied
from `Course05_DemoC_Recording_v3.zip`, Lab2. The original repository base was
`1b2c375c5f7aca1340bb308ce5e534e8cc569a99`. The six tests in
`test_course05_student_examples.py` are new teaching examples. The separate
Demo A and Demo B packages are not included here. Concurrency and delegated
count exercises remain to be designed, implemented and tested.
