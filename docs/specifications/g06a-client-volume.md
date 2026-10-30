# G06-A — client-volume reference impact (local candidate)

Owner Issue #7 / G06-A authorizes local implementation only on
`feat/checker/g06a-client-volume-impact`. No commit/push/PR/hosted trigger is inferred
from G05's separate authority or time approval. No G06-B/G07, DOCX mutation or UI.

Verified baseline: main `2c2198790814d2ea28049c1e1bd84f51a7cb0874`, tree
`8e28acaff152bdc77c549c15976437d46dcef02a`. Post-merge run
[41092296875](https://github.com/alidagha/cementing-checker/actions/runs/41092296875),
attempt 1, independently authenticated: A/B/C + regression SUCCESS, 394 tests
(A177/B126/C91), 1182 phases; certificate SHA256
`8c45e94014cdbc6a10d06209066075e0a43361ef6d891d5824d3728199b589ff`.
This prior baseline is not a G06 hosted pass or Golden UAT.

## Input, output and trust boundary

In the established separate Git-free runtime, use the existing source-valid C02
operator object and a DOCX under `tmp/`. No source value comes from Word. First
inspect exactly one active ordinary placement slurry to obtain fresh bindings:

```python
from g06a_client_volume import inspect_reference, volume_impact
before = inspect_reference(docx, operator, "Main")
edit = {"schema": "g06a.1", "bindings": before["bindings"],
        "slurry": "Main", "client_volume_bbl": new_positive_volume}
result = volume_impact(docx, operator, edit)
```

CLI (stdout is private structured evidence):

```sh
python -B g06a_client_volume.py tmp/operator.json tmp/original.docx --slurry Main
python -B g06a_client_volume.py tmp/operator.json tmp/original.docx --edit tmp/edit.json
```

The worker recomputes original reference, selected identity, document/input/reference
SHA256, source/template/manifest/accepted locks and exact request. Bindings are stale
data guards, not qualified-review authentication. A forged hash/locator/approval cannot
replace source execution. Exact request shape rejects extra measurements, density,
formulation, DV, job/active-fluid changes, no/duplicate selection and nonpositive or
nonfinite volume. Input JSON must have unique keys/finite values. Paths/symlinks/Git
worktree escapes are refused. Original operator, JSON bytes and DOCX stay unchanged.

Only selected `client_volume_bbl` changes in a deep in-memory operator copy. The old
and edited C02 comparisons are both retained, as are all original/unmapped claims.
Per-claim output preserves raw text/locator, old/new source values/displays, deltas,
original tolerance and comparison statuses. Classification is one of SOURCE_CHANGED,
SOURCE_UNCHANGED, MANUAL_REVIEW_REQUIRED, NOT_VERIFIABLE. A full-precision change can
be invisible at authentic display precision; unknown display is null, not invented.
MATCH after a reference edit is not repaired Word. Top-level PARTIAL_FINDINGS_ONLY,
`docx_written=false`, `word_modified=false` always remain on success.

## Source/dependency and permission preflight

Current Checker/App AGENTS/zero-regression contracts, complete unchanged rev8 Charter,
G03, C02–C10 contracts, v3.3 and exact v3.0 §B/v3.1 §4 excerpts in
[Issue #5](https://github.com/alidagha/cementing-checker/issues/5#issuecomment-6526366847)
govern. Older broad matrix rows are not this increment's authorization.

Two-pass review: (1) trace input → original engine → source display → immutable Word
comparison; (2) independently recheck selection/identity, invariants, DV ambiguity,
transitive byte consumers, native routing, isolation, error/privacy boundaries and
unrun dependencies. This executor preflight is not independent architect acceptance.

| Surface / authority | Effect and scope |
|---|---|
| `g06a_client_volume.execute` → accepted `c02_compare.compare_document` → `c02_engine.reference:27` | Fresh before/after automatic references; only one client volume differs. Original process/cache wrapper alone is replaced in the private worker by the accepted direct pure-reference bridge; no source function/state/gate is patched. |
| Locked `phase_5_cement.py:174,219,240` / `engineering_tools.py:665,765` | Original component normalization, mass balance and base field tables. No copied formula, physics or tolerance. |
| `phase_10_procedure._word_program_quantities:43` | Authentic Yield/Sacks/pure-water/Solution displays. Solution remains distinct from pure water. |
| `phase_7_lab.build_lab_df_from_phase5:220` / original Lab projection | Calculated 600-mL recipe only; fixed recipe/density Yield/Lab invariance is actually checked. No measured Lab prediction/review. |
| `materials_db.PLACEMENT_SLURRIES:61`, `project_state.available_fluid_types:191` | Exact active ordinary role; source WBM/OBM sensitivity probes prove selected-role eligibility without assuming actual mud. Unselected-fluid eligibility remains unverified. CT/Squeeze and nonordinary selected roles are unsupported in this increment, not new App rules. |
| Accepted C10 `identities`, `private_path`, `target`, JSON guards | Reused read-only lock/path/physical-cell proof only. No C10 correction transaction is invoked. Unique literal Yield/Sacks groups prove the selected printed slurry; duplicate/hidden/merged/split/unknown structures fail closed. |

Read-only: original App/Git/worktrees, all C01R–C10 files/tests/locks, source/template,
recovery, original DOCX and measurements. New local writes: one helper, one test
module, this contract and mechanical schedule/digest only; all fixtures/temp/cache/
evidence live in separate private runtime. All 143 source files/blobs and template
SHA are checked; source remains `60dffefb8c941ad90cb7caba0992126a35803717`, template
blob `1d77ebb7140e1bf0fa3d7cbd092f215290a187c0`, SHA256
`a1128b0e9352e1dd7c8768eecc9335c50858356cee80ed33c0ec275e26c4d08b`.
Network/outside-temp/cache writes are denied in the source worker. No new dependency.

## Impact / unsupported coverage

| Source-backed effects | Explicit unresolved dependencies |
|---|---|
| Client volume, Sacks, pure mix water, Solution and base field additive/salt quantities | Operational total water and gross-with-DV need explicit independent DV; no allowance is inferred or carried from rounded Word. C02's internal zero-DV base bookkeeping is not actual engineer DV. |
| Density, Yield, base formulation and calculated 600-mL recipe remain source-proved invariants; unselected slurry source/findings unchanged | Mixing tank/NOTE/Procedure/Summary need full independent C03/C08/C09 context; no sentences/numbering regenerated. |
| Existing uniquely mapped C02 Word claims are recomputed against both references | C05 timing needs independent rates/train inputs; geometry/excess is informational and absent independent geometry stays unverified. |
| Full precision and actual source display are separate | Measured Lab/rheology observations are not supplied, modified, predicted or refreshed; CT/Spacer cascades remain unsupported. |

Synthetic oracle: neat 104-pcf/SG3.2 Main, client 50 → 55 bbl; authentic Sacks display
154.4 → 169.9, water 34.8 → 38.3, Yield 1.818 and calculated cement mass 582.0 g remain
invariant. Unchanged Word Sacks 154.4 becomes discrepant; a separate negative Word
mutation remains discrepant. This is reference-impact verification, not a historical
Checker bug or authentic App-generated Golden. Source-rendered/hand-declared controls
are synthetic; no client/Lab/program data enters public files or artifacts.

## Tests, routing and cost

One new native module `tests/test_g06a.py` → B only. Verified main native phase times:
A ~581s, B ~401s, C ~415s. Estimated new local module <3 minutes, final focused checks
<5 minutes cumulative; no heavy hosted/full regression is authorized here. Existing
394-test hosted main evidence is reused only with unchanged code/test/lock proof.
Focused controls cover independent oracles, source display precision, before/after
discrepancies, two-slurry isolation, additives/liquid/dry/salt, stale/forged bindings,
invalid values/selection, ambiguous/hidden/corrupt Word, paths and CLI unique JSON.
Permanent parser/migration sentinels and relevant unchanged C02 tests run locally;
actual commands/results and cost are recorded in the issue/local execution evidence.

Observed local results: `python -B -m pytest -p no:cacheprovider tests/test_g06a.py
c02/test_c02.py test_checker_parser.py tests/test_migration.py -x -q` passed **99**
tests in **231.40s**, with 297 complete phases/no warnings. After the final display
qualification, the independent-oracle and precision controls passed **2** tests in
**13.19s**; unchanged cases reuse the preceding focused evidence. Initial cheap
controls passed 3 in 22.34s; the private direct-source demo took 8.49s. Recorded
verification is approximately **4m35s**, with a conservative five-minute local charge.
Final ordinary collection: **427 tests**, A177/B159/C91; **33** new G06-A cases,
all owned only by B. Collection is not full execution or hosted certification.

Final-byte command, cwd feature repository root:

```text
sha256sum -- tools/test-schedule.json
88e71f41b5e58b29876bb8a7dd85dee79e1ba12064544dba34ca74bc5e883ec6  tools/test-schedule.json
```

Reviewed diff appends only the new module to B; coupled digest updated from that
actual output (old `f9c32c621b37bfc3eb741cd9367bfdbaa3d2ea68b413c1b03432fe54f88cff80`).
No old assignment, test assertion, runner or discovery/CI policy changed. Final
ordinary collection and unique routing must independently match these final bytes.

NOT RUN: G06 hosted regression/PR, original App full regression, authenticated
15-job Golden/Word/browser UAT, full geometry/timing/narrative/measurement parity,
DOCX repair, complete cascades, G06-B/G07, release/deployment. Next increment needs
its own bounded requirements/inputs; publication/time authority is separately required.
