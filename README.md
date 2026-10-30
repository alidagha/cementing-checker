# Cementing Checker — bounded C01R–C04

Independent First · Integration Optional · Simplicity Always.

Local unpublished genesis proposal, subject to independent review and Owner rights/privacy and publication decisions. No license grant is implied. This tree contains accepted Checker code and unchanged focused tests; it does not distribute the upstream App, Word template, libraries, original fixtures or recovery archives.

C01R extracts ordered DOCX claims. C02 calls the original automatic App engine for selected numeric comparisons. C03 attributes preparation-water notes/tanks and reports inferred allowance intervals. C04 previews an explicit selected ordinary-slurry Dead Volume proposal without editing Word. Results remain `PARTIAL_FINDINGS_ONLY`; CLI exit 0 is not program approval.

## External runtime prerequisite

Python 3.12 and the exact externally installed versions in `requirements.txt` are required. Use an isolated virtualenv outside any App/accepted worktree:

```sh
mkdir -p /YOUR/SCRATCH/checker-temp /YOUR/SCRATCH/checker-cache
export PYTHONDONTWRITEBYTECODE=1 TMPDIR=/YOUR/SCRATCH/checker-temp XDG_CACHE_HOME=/YOUR/SCRATCH/checker-cache PIP_CACHE_DIR=/YOUR/SCRATCH/checker-cache/pip
python3.12 -m venv /YOUR/SCRATCH/checker-env
/YOUR/SCRATCH/checker-env/bin/python -m pip install -r requirements.txt
. /YOUR/SCRATCH/checker-env/bin/activate
```

The lock records observed working versions, including transitive imports. Package availability on another index/platform and a fresh pip installation are separate verification gates; no libraries are vendored. Network is needed for package acquisition and the explicitly pinned external source download. Calculations themselves are local.

From this candidate root, using that environment's Python:

```sh
PYTHONDONTWRITEBYTECODE=1 python -B tools/provision.py --destination /YOUR/SCRATCH/checker-runtime
cd /YOUR/SCRATCH/checker-runtime
export PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/tmp" XDG_CACHE_HOME="$PWD/cache" XDG_CONFIG_HOME="$PWD/cache/config" MPLCONFIGDIR="$PWD/cache/mpl"
python -B tools/provision.py --seed
python -B tools/ci.py collect
python -B tools/ci.py run --shard A
python -B tools/ci.py run --shard B
python -B tools/ci.py run --shard C
python -B tools/ci.py certify
```

The fresh runtime must be outside this candidate and all Git worktrees. Provision downloads `alidagha/cementing-test` at the exact `upstream.lock.json` commit and verifies all 143 SHA256/Git-blob identities, including the template. Availability is not guaranteed, and download instructions are not redistribution permission. Only the private runtime contains `snapshot/` and generated source-rendered synthetic fixtures. It is not an offline/self-contained public distribution.

`--seed` generates new structural equivalents needed by unchanged tests. Files historically named `red-baseline.json` or `c03-baseline.json` are fresh runtime controls here, never evidence of a historical RED. Accepted historical files remain private and unchanged. No sanitized replacement or byte identity of original DOCX is asserted; no DOCX is proposed for Git.

## Selected-DV example

From provisioned runtime `c04/`, use independent operator JSON, an original local DOCX and separate edit JSON:

```sh
python -B c04_preview.py fixtures/operator-main.json fixtures/synthetic-main.docx fixtures/edit-main.json
```

The synthetic control proposes Main DV 10 bbl: preparation water displays 44.2 bbl; gross powder 206.8 lb. The prior inferred interval remains nonunique. Operator/DOCX are never rewritten. Input files must resolve inside the corresponding module directory. Never infer operator references from Word.

Unsupported roles, conflicting/duplicate notes, unproved fields and malformed data fail closed or remain unverified. `Solution` is not pure Mix Water. Dead Volume is not a measured tank heel or physical minimum. No new mandatory fluid exists.

NOT RUN/certified: 15-job goldens, complete Formula/Procedure/Lab parity, native Word/browser, full App regression, corrected DOCX and UI/integration. The original M00 handoff describes migration evidence; subsequent owner-authorized hosted runs certify only the currently implemented Checker test scope.

## G01 engineering extensions

The owner-authorized G01 feature branch adds independent partial comparisons without changing accepted C01R–C04 bytes. In a provisioned private runtime, use `python -B c05_fluids.py operator.json input.docx`; see [C05 inputs, mappings and exclusions](docs/specifications/c05.md). These findings do not certify an entire program. GitHub Actions, with complete native A/B/C discovery and final `regression`, is the current implemented-scope regression authority.

For unique Hardware/temperature claims and informational source geometry, use `python -B c06_well.py operator.json input.docx`; [C06](docs/specifications/c06.md) defines its independent inputs and 15-job source-support matrix. Geometry never substitutes for Client Requested Volume.

For independent measured Lab/Rheology data and automatic source recipe masses, use `python -B c07_lab.py operator.json input.docx`; [C07](docs/specifications/c07.md) distinguishes observations, source-derived values, reference confirmation and unsupported fields. Recipe calculations never predict measured laboratory outcomes.

## G02 narrative extensions

Use `python -B c08_summary.py input.docx operator.json` for exact source-backed
Executive Summary evidence ([C08 contract](docs/specifications/c08-narrative.md)).
Use `python -B c09_procedure.py input.docx operator.json` for official Procedure and
ordered NOTE evidence ([C09 contract](docs/specifications/c09-narrative.md)).
References require complete independent facts or explicit independently approved
manual text. Unproved Word numbering/fields/hidden text and incomplete source
contexts fail closed. These commands produce partial JSON findings, never Word
edits or whole-program approval.

## G03 production-DOCX admission

[The admission contract](docs/uat/G03-admission-contract.md), [15-job inventory](docs/uat/job-manifest.json)
and [X01–X22 matrix](docs/uat/cross-case-matrix.json) separate component regression,
source generation and Golden UAT. In a provisioned private runtime,
`python -B golden_admission.py reference.json` attempts the unchanged full App export
with its real gates. Synthetic controls and self-asserted receipts never qualify as
production Goldens; no G03 path grants `GOLDEN_PASS` or performs Word correction.
