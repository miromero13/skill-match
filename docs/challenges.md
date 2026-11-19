# Evaluation challenges

SM-40 uses a generic **Challenge** domain. A challenge belongs to a catalog skill and level, has an evaluation modality, an execution profile, versioned cases, and a publication lifecycle.

## Current flow

1. ADMIN creates a draft at `/admin/challenges`.
2. ADMIN chooses a modality and execution profile. The first available evaluator is `SANDBOX` with `PYTHON_3_12`.
3. ADMIN adds any number of public and hidden cases.
4. ADMIN publishes the version. The previous published version for that skill and level is archived.
5. The MEMBER completes theory and opens `/evaluation/:id/code`.
6. The backend resolves the published challenge for the evaluation level and runs the profile-specific evaluator.

`/admin/capture` remains dataset collection. Its samples can support future challenge curation or local models, but samples are never exposed directly as exams.

## Modalities and profiles

| Modality | Profile | Status |
| --- | --- | --- |
| `SANDBOX` | `PYTHON_3_12` | Available |
| `SPREADSHEET` | Excel/XLSX evaluator | Reserved for a future evaluator |

A spreadsheet challenge must use a spreadsheet evaluator rather than pretending that Excel is a programming language. New evaluators should implement the same published Challenge contract without changing the MEMBER routing or ADMIN versioning flow.

## Sandbox controls

The Python runner uses a pre-pulled Docker image with no network, no capabilities, no privilege escalation, read-only source mount, temporary `/tmp`, CPU/memory/process limits, a timeout, and bounded stdout/stderr. The backend parses Python with `ast` before execution and rejects dangerous imports/calls. Correctness comes from exit status, timeout, bounded output, and normalized stdout equality.
