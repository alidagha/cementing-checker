# Cementing Checker — partial source-backed findings

Independent First · Integration Optional · Simplicity Always.

This public repository contains the independent Cementing Program Checker, its implemented-scope regression checks, and the Owner-authorized, byte-verified engine/template bundle pinned by `upstream.lock.json`. Python libraries, original customer fixtures and recovery archives are not bundled. Publication is not production acceptance or a new license grant.

C01R extracts ordered DOCX claims. C02 calls the original automatic App engine for selected numeric comparisons. C03 attributes preparation-water notes/tanks and reports inferred allowance intervals. C04 previews an explicit selected ordinary-slurry Dead Volume proposal without editing Word. Results remain `PARTIAL_FINDINGS_ONLY`; CLI exit 0 is not program approval.

## Local engine and private runtime

Python 3.12 and the exact externally installed versions in `requirements.txt` are required. Use an isolated virtualenv outside any App/accepted worktree:

```sh
mkdir -p /YOUR/SCRATCH/checker-temp /YOUR/SCRATCH/checker-cache
export PYTHONDONTWRITEBYTECODE=1 TMPDIR=/YOUR/SCRATCH/checker-temp XDG_CACHE_HOME=/YOUR/SCRATCH/checker-cache PIP_CACHE_DIR=/YOUR/SCRATCH/checker-cache/pip
python3.12 -m venv /YOUR/SCRATCH/checker-env
/YOUR/SCRATCH/checker-env/bin/python -m pip install -r requirements.txt
. /YOUR/SCRATCH/checker-env/bin/activate
```

The lock records observed working versions, including transitive imports. Package availability on another index/platform and a fresh pip installation are separate verification gates; no Python libraries are vendored. Package acquisition may require network or a separately prepared wheelhouse. Provisioning, seeding and calculations require no App network access or App checkout.

From the repository checkout, using that environment's Python:

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

The fresh runtime must be outside this checkout and all Git worktrees. Provision reads `checker_engine/60dffefb8c941ad90cb7caba0992126a35803717.tar.gz` locally and verifies all 143 SHA256/Git-blob identities against the unchanged lock, including the template. There is no remote fallback. The versioned archive retains every locked upstream resource; its upstream tests are not Checker discovery inputs. Only the private runtime contains the expanded `snapshot/` and generated synthetic fixtures; the archive is not duplicated there. See [local engine packaging](docs/architecture/local-engine-bundle.md). R1 provides standalone source availability, not a complete offline Python distribution, Golden UAT, secure-delivery certification or final release.

`--seed` generates new structural equivalents needed by unchanged tests. Files historically named `red-baseline.json` or `c03-baseline.json` are fresh runtime controls here, never evidence of a historical RED. Accepted historical files remain private and unchanged. No sanitized replacement or byte identity of original customer DOCX is asserted. The only packaged DOCX is the exact locked template inside the verified source archive.

## Selected-DV example

From provisioned runtime `c04/`, use independent operator JSON, an original local DOCX and separate edit JSON:

```sh
python -B c04_preview.py fixtures/operator-main.json fixtures/synthetic-main.docx fixtures/edit-main.json
```

The synthetic control proposes Main DV 10 bbl: preparation water displays 44.2 bbl; gross powder 206.8 lb. The prior inferred interval remains nonunique. Operator/DOCX are never rewritten. Input files must resolve inside the corresponding module directory. Never infer operator references from Word.

Unsupported roles, conflicting/duplicate notes, unproved fields and malformed data fail closed or remain unverified. `Solution` is not pure Mix Water. Dead Volume is not a measured tank heel or physical minimum. No new mandatory fluid exists.

Not certified: authentic 15-job Golden UAT, complete Formula/Procedure/Lab parity, native Word verification, full App regression or production readiness. Existing implemented-scope CI and bounded browser controls do not certify an entire engineering program.

PRs to `main` run Fast Gate, complete native A/B/C shards and the required `regression` evidence gate. A push to `main` runs Fast Gate plus the fast-only required status; full A/B/C is intentionally skipped. Verify each candidate's exact-head evidence rather than treating historical CI as a fresh PASS.

## One-page Checker UI

After provisioning and seeding the private Git-free runtime above, launch there:

```sh
python -B -m streamlit run c10_delivery.py --server.address 127.0.0.1 --server.headless true --server.maxUploadSize 32 --browser.gatherUsageStats false
```

The single page accepts DOCX only, gathers independent engineering inputs, and runs compatible implemented checks only when their source-valid prerequisites are supplied. It shows English traceable partial findings and an editable, run-bound engineer message with native copy. Missing or unsupported coverage remains explicitly NOT_RUN / NOT_VERIFIABLE. See the [G07 contract](docs/specifications/g07-ui-report.md) for historical implementation evidence; current behavior also includes the separately approved later bindings.

After a current admitted C02/C03 run, the optional [G06-A client-volume preview](docs/specifications/g06a-client-volume.md) accepts one eligible active ordinary slurry and an independently proposed positive volume. It displays a separate source-reference impact: the authoritative client request, baseline findings, engineer message and original Word bytes remain unchanged. C09 Dead Volume is not carried into G06-A.

The separate optional [G06-B explicit-DV preview](docs/specifications/g06b-dead-volume.md) requires fresh physical NOTE/gross eligibility and an independently entered finite nonnegative DV (zero is valid). It displays the original claims/locators, nonunique historical interval, unchanged pure Mix Water, proposed source preparation water and gross displays, and unresolved dependencies. It never measures historical DV, changes client volume, corrects Word or supplies an exact historical delta. Gross full precision remains null where the source API exposes only display values. Changing DV controls invalidates only DV evidence; baseline/input changes invalidate all previews. C09 and G06-A proposals remain independent. All outcomes remain `PARTIAL_FINDINGS_ONLY`, without Golden or whole-program certification.

The optional [C10 selective safe-copy](docs/specifications/C10-safe-copy.md) requires fresh source/physical proposal inspection, individual Yield/Sacks selections (none by default), explicit confirmation and creation. Only unchanged C10 applies/rechecks the exact source replacements in a new private DOCX. After transient files are removed, its verified bytes are delivered through an authorized native browser POST attachment, without registering a Streamlit media download. Changing selection/confirmation invalidates the copy; changing inputs/upload/run invalidates all C10 evidence. The uploaded original, baseline message and G06/C09 state stay unchanged. Unselected and dependent items remain manual/unverified; this is not full-program correction, review or certification.

### C10 delivery boundary and historical privacy incident

**Historical FAIL (G08-A6, 2 November 2026):** A fresh browser session given another session's corrected-DOCX media URL received HTTP 200 and byte-identical DOCX without an uploaded program, Checker receipt or download control. URL guessing or enumeration was not demonstrated. The Owner accepted publication with a warning; that warning was disclosure, not a remedy. The original DOCX remained unchanged.

**G08-A7/S1 remedy, 3 November 2026:** The documented entrypoint uses supported Streamlit 1.64.0 `st.App` routes/middleware. Each delivery requires an HttpOnly, SameSite cookie plus a separate per-copy proof delivered only in the owning session's static HTML POST form, never in the URL. The endpoint revalidates the current session, source-admitted receipt, original document, selected findings, consent and corrected-copy SHA under the same lock used for invalidation. Corrected bytes never enter the unguarded media registry; DOCX media responses are also refused. Responses use `Cache-Control: no-store`. A URL or shared browser cookie alone does not authorize delivery.

Real Chromium and direct HTTP controls denied DOCX delivery to a fresh process/context, a tab sharing the cookie without the owning form proof, a bare HTTP client and the historical media locator. A GET may return HTTP 200 with the generic HTML application shell; recorded MIME, body size/hash and content comparison, rather than status alone, establish that no DOCX was delivered. Explicit selection changes, consent withdrawal, committed independent-input changes, a different uploaded DOCX and a fresh Run Check each revoked the old delivery authority, including replay after later admitted runs. Saved files and already authorized in-flight transfers cannot be recalled. These are synthetic component/security controls, not authentic Golden UAT or whole-program certification.

Use the documented entrypoint in one process at the root URL. A legacy direct `checker_ui.py` launch fails closed for C10 delivery. Loopback HTTP was browser-tested; nonloopback HTTP is refused, and direct HTTPS sets Secure cookies. A restart is required when upgrading from the old native-media implementation. External deployment, reverse-proxy/multiworker integration, full browser-credential compromise and native Word/production-Golden parity are not certified by these tests. No external authentication service, custom JavaScript, component or new dependency is used.

Known limit: the original pinned-template control is refused by G06-A with `PLAIN_RUN_REQUIRED`; G07 admission alone does not prove eligible physical Yield/Sacks claims. The positive preview control uses a distinct source-valued literal-table synthetic layout, not an authentic App-generated Golden. In this client-volume preview, operational DV, total preparation water/gross-with-DV, narrative, timing, measured Lab, geometry and CT/Spacer dependencies retain their source-reported unresolved status.

## Current governance and historical records

Current work follows v5.4 rev1 and the [governance references](docs/governance/authority.md); the [Codex operative card](docs/codex_operative_card_v5_4_rev1.md) is a derived summary. The complete Charter remains private. Older specifications retain their dated v5.3 references and SHA/baseline evidence as historical technical records, not current governance or fresh acceptance. The original M00 migration instructions are historical, not a new publication authorization.

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
# Selective safe-copy correction (C10)

The bounded C10 library/CLI can propose and explicitly apply source-proved ordinary
cement Yield/Sacks cell replacements to a new private DOCX, then re-parse/recompare.
Original bytes and unselected discrepancies remain intact; unsupported dependencies
remain manual/unverified. See [C10 contract](docs/specifications/C10-safe-copy.md).
This is partial functional checking, not authentic Golden UAT or whole-program PASS.
