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

NOT RUN/certified: 15-job goldens, complete Formula/Procedure/Lab parity, native Word/browser, full App regression, hosted CI/rulesets, corrected DOCX, UI/integration and C05. The workflow is a local draft and must not be activated without separate authority. See `docs/governance/authority.md`, `docs/specifications/bounded-contract.md`, and the private M00 review handoff for actual local evidence.
