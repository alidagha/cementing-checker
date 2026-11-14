# W2 — WINDOWS_NATIVE_NOT_VERIFIED — OWNER MACHINE UAT REQUIRED

This is a compatibility **review candidate**, not a Windows-ready installation,
release or engineering acceptance. Native Windows 10/11, offline restart and NTFS
security/session parity have not been tested. No Windows runner is available.
The Owner permits publication for review after final Linux gates; merge still
requires independent Architect review and separately authorized Windows UAT.

Baseline: `ed12777809d0193eb54687b6ac6e1bb23c648755`.
Branch: `feat/checker/w2-windows-offline-compatibility`.
Base tree: `0cf6a7cfc2b35a311d6f22be44d011a6970baf40`.
No App installation, package environment, engine formula, template, UI control,
CI workflow, test schedule or delivery authorization policy was changed.

## Migration and security boundary

| Existing site | Preserved draft change | Evidence boundary |
|---|---|---|
| C02 slash-prefix trace | Resolved component containment, exact manifest membership and byte hash; shared by engineering, narrative and Golden trace consumers | Linux containment/alias/foreign-source negatives and original accepted numerical/source-call oracle; Windows path models are not native execution |
| C03/C04 embedded C02 SHA | Mechanically dependent pins and exactly three accepted lock entries | Original -> revised identities below; other eight accepted identities and all accepted tests unchanged |
| G07 POSIX-only exclusive/private operations | Shared private-file helper, preserving POSIX no-follow/exclusive behavior | Linux full regression; owner-only Win32 DACL/NTFS behavior not kernel-verified |
| C10 POSIX descriptor-relative publication | Existing POSIX branch retained; separate Win32 ancestor handles, identity/readback and handle-based no-replace publication | Linux real selected-copy/security plus protocol models; no native NTFS race-equivalence claim |
| Provisioning | Byte-preserving UTF-8/LF manifest and source-alias rejection | Local bundled 143-file provisioning and hash/blob checks; no source fetch |
| Setup/daily launch | Separate Checker venv/runtime; approved `c10_delivery.py`, loopback 8502, max upload 32 MB, telemetry disabled | CMD scripts and Windows setup/offline execution NOT_RUN |
| Final two isolation repairs retained | Reject unsafe setup destinations before filesystem writes; reject nonlocal Windows volumes before opening filesystem paths | Fresh actual-filesystem setup control and Win32 protocol-model negative; native Windows NOT_VERIFIABLE |

The source route remains independent UI inputs -> immutable G07 revision/receipt ->
existing C02–C09 wrappers -> unchanged pinned source -> physical DOCX findings.
G06 previews and selected C10 ordinary Yield/Sacks retain their existing scope.
Pure Mix Water, Solution, preparation water, explicit DV and independent Client
Requested Volume remain separate. Original DOCX is never overwritten.

The Windows backend is intended to require owner-only DACLs, local NTFS,
no-reparse ancestors, restrictive sharing, staged identity/byte checks and
`SetFileInformationByHandle` no-replace publication. A replaced staging identity
is refused rather than deleted as owned. Native sharing/ACL inheritance,
junction/reparse/parent races, hard-link aliases and complete adversarial cleanup
remain **NOT_VERIFIABLE**. Models cannot certify these OS guarantees; an
unsupported security precondition must fail closed.

## Final-byte Linux verification recovery

**FRESH PASS (Linux only): 810 unique roots / 2,430 complete phases**:
A272/816, B273/819, C265/795. All 802 baseline roots remain, with exactly one
unchanged whole-module owner and no orphan/duplicate roots. Every phase passed;
zero warnings, errors, skips or xfails. The unchanged strict native certifier
accepted the actual discovery and all three audit identities/order/phase sets.
Its authority is **LOCAL_ONLY_NOT_CERTIFICATION**, with local uncommitted identity;
this is not a Hosted certificate.

The full native modules include all **13 permanent guards**, the four W2
migration additions, accepted C01R–C04, C05–C10/G06/G07 siblings, ledger mutation
controls and both final isolation fixes. The cheap-first gate independently
passed 59 roots/177 phases, including the complete 17-test migration module,
27 ledger tests, original accepted C02 source-call oracle and C10 stale/protocol
negatives. Functional/test/ledger bytes stayed identical throughout the recovery;
only evidence documentation changed afterward and its affected migration/ledger,
identity, whitespace and export checks are publication prerequisites.

Product runtime: Linux CPython **3.12.14**, all **51 exact pinned packages**,
Streamlit 1.64.0; browser Chromium **154.0.8037.57**.
The unchanged Hosted workflow specifies Python 3.12.15. Local results are not
Hosted certification or evidence that native Windows wheels are available.

Commands ran in separately provisioned, Git-free private runtimes:

```text
python -B tools/provision.py --destination NEW_PRIVATE_DIRECTORY
python -B tools/provision.py --seed
python -B -m pytest -p no:cacheprovider -vv <unchanged whole-module shard paths> --audit-file PRIVATE_AUDIT
python -B tools/ci.py collect --evidence PRIVATE_EVIDENCE
python -B tools/ci.py run --shard A --evidence PRIVATE_EVIDENCE
sha256sum -- tools/test-schedule.json
```

The initial complete A/B/C execution passed every test, but A's local harness
module order differed from native discovery. The unchanged strict aggregator
correctly rejected that A audit. The first audit/log is retained unchanged;
A was rerun through `tools/ci.py run` rather than sorting or editing evidence.
B/C already matched native discovery. This was a local runner-order defect,
not a product failure and not a reason to relax certification.

Fresh Linux Chromium (one approved single-process loopback `c10_delivery.py`
instance) used real entered/committed independent inputs, native Hardware cells,
current source receipt, selected Yield correction and immutable original bytes.
It proved owner POST **200**, independently isolated foreign context **403**,
selection-change revocation **403**, source-admitted Procedure/read-only
narrative evidence and changed invalid input/stale download **403**.
Bodies were recorded privately before assertions and compared by exact hashes.
No URL, credential, customer document, raw operator payload or screenshot is
published. The synthetic original SHA256 was
`70a6e79dbc6cdac9017701b4208d0f45502cbac89b63763059d73c89f7d3f5c2`;
authorized corrected copy SHA256
`c896aeb00d53d8b44e694055097d1f69b5ae02be38b14ae267de6f0f0a70f874`.
Original bytes remained identical. This proves Linux component/session behavior,
not native Windows or authentic Word/Golden acceptance.

## Immutable identities and protected hash chain

Original source: `60dffefb8c941ad90cb7caba0992126a35803717`, all **143**
resources verified against existing SHA256/Git blobs.
Bundle SHA256:
`2aee7c402ae0b6849bef38b71e8646fb3a92f152a3f1de874c1e642b2dbf97a5`.
Template SHA256:
`a1128b0e9352e1dd7c8768eecc9335c50858356cee80ed33c0ec275e26c4d08b`.
Requirements SHA256:
`1150bfa58cbf8020eaa86e11e8034259830886dff1be832ad14151bb846b09b2`.
Schedule command, executed from checkout root:

```text
sha256sum -- tools/test-schedule.json
a3e1689ff764c4ae46798fe0b590f335c5c8e7b79b5ca8b3db73531114d10ba9  tools/test-schedule.json
```

Schedule/digest diff is empty. No module was added or rebalanced.

| Authorized accepted wrapper | Original SHA256 | Revised SHA256 |
|---|---|---|
| `c02/c02_engine.py` | `b3327b430b37df45421d81f6bed7087c381eca02cf66dc12b0df6f4262ede6bd` | `6a1d9d28cdeb1fc1125b2a951ba06141dd96fee9cc6db46a0e364d7a3846cd4e` |
| `c03/c03_source.py` | `aca286244e1909e9112f04c3e938c701bd47b5b4954897a0d365d0e918feeea0` | `85ac0146d521b3bf0c81d7ea8d8c10e9400adc814ec215d6830459b579113ca5` |
| `c04/c04_runtime.py` | `da9cefa372c771885d52ffeba02eb90477bfd82aa1bb218b35a4dc790dc65a68` | `75f941c67d299cb2faaa33f3c6960d37462805d14a13ce15be9a9a3d6d1c0b06` |

C02 attribution is the substantive accepted-wrapper change. C03 embeds C02's
new hash; C04 embeds both resulting hashes. All eight remaining accepted
identities and every existing accepted test/assertion retain original bytes.
Existing nonaccepted test bodies also remain unchanged; W2 tests are additions.
The ledger only aligns producer SHA/AST references: original 406 candidate
patterns, J01–J15, X01–X22, 330 applicability cells, maturity and zero authentic
verified-claim counts remain unchanged.

## Exact 19-path candidate

```text
README.md
Run_Checker_Windows.cmd
Setup_Checker_Windows.cmd
accepted.lock.json
c02/c02_engine.py
c03/c03_source.py
c04/c04_runtime.py
c10_corrections.py
docs/coverage/W2-windows-native-offline.md
docs/coverage/claim-coverage-ledger.v1.json
engineering_source.py
g07_report.py
golden_source.py
narrative_source.py
private_files.py
tests/test_c10.py
tests/test_migration.py
tools/provision.py
tools/windows_checker.py
```

All functional/test/ledger bytes were preserved from the stopped draft during
this recovery. Only README and this evidence note were updated to disclose final
verification and the Windows boundary. Private preflight backups, per-file
SHA256 attestations, original diffs, full audit/phase logs, failed attempts,
browser evidence and final export scan remain outside Git. An empty historical
ignored pytest log was privately preserved/relocated, not committed.
No private fixtures, expanded source, DOCX, credentials or runtime logs enter Git.
Native CMD files deliberately use CRLF; a CRLF-aware whitespace check and
intentional trailing-space negative distinguish line endings from actual errors.

## Owner-machine UAT — not yet executed

First publish/review this branch; use the **exact PR head**, byte-preserving source
files and local NTFS outside every App/Checker checkout runtime. Do not reuse or
modify Cementing App's Python environment, directories, launcher or port.
Existing CPython 3.12 and Windows 10/11 are prerequisites. The commands below
are UAT instructions, **not a READY_OFFLINE claim**.

From CMD in the downloaded exact Checker candidate directory (paths may contain
spaces or Unicode):

```bat
py -3.12 --version
call Setup_Checker_Windows.cmd
```

Initial dependency installation may require internet once. Verify all 51 exact
packages, local bundle/template checks and a newly created private Checker
runtime/venv. Do not overwrite an existing runtime or upgrade App packages.
Disconnect internet, then:

```bat
call Run_Checker_Windows.cmd
```

Confirm only `http://127.0.0.1:8502`, approved `c10_delivery.py`, upload limit
32 MB and telemetry disabled; no pip/Git/source fetch during launch.
Repeat after shutdown and reboot with network disconnected. Stop only this
Checker with Ctrl+C in its console.

Run the following using the setup-selected **Checker venv Python**, from its
Git-free private runtime; these must execute the actual native OS branch:

```text
python -B -m pytest -p no:cacheprovider -vv tests/test_c10.py::test_selected_copy_independent_red_green_and_unselected_discrepancy tests/test_c10.py::test_stale_forged_or_implicit_selection_never_writes tests/test_c10.py::test_recheck_failure_cleans_staged_copy
```

Also perform actual typed/commit/readback UI with independent source inputs,
synthetic positive and invalid/stale controls, source attribution, G06-A/B,
admitted Lab/Hardware and C08/C09, selected-only new-private-copy readback/recheck,
own-session POST 200 and foreign/stale 403 with zero unauthorized DOCX bytes.
Record original/download hashes privately. Test drive/UNC/prefix/traversal
lookalikes, outside-snapshot imports, symlink/junction/reparse and hard-link
substitution, input mutation during a run, output-parent/staging swaps and
existing output collision. Prove refusal before unauthorized output.
Linux mocks do not substitute for those native NTFS tests.

Every native Windows item above remains **NOT_RUN / NOT_VERIFIABLE** until actual
evidence exists. No native MS Word or production-Golden claim is made.

## Historical failures, clocks and continuation authority

- Initial W2: **35m54s total**, **23m41s verification** against 20m:
  original limit **NOT MET**. First focused run failed (29 passed/5 failed);
  corrected fixture/AST controls passed 34 plus the accepted oracle, not full
  regression. These failures are retained, not reclassified as Windows proof.
- Prior renewal: **3h29m02s**, including an unexplained **2h45m44s** interval.
  The gap is not treated as idle. Earlier 808 roots/2,424 phases and Linux
  browser 200/403 preceded the final two repairs and are historical only.
  Two focused repair controls alone did not provide final-byte clearance.
- Owner-authorized final-byte recovery starts **2026-11-14 11:56:27 UTC**.
  Absolute verification deadline **12:56:27 UTC**; publication/execution deadline
  **13:26:27 UTC**. All wall time, interruptions and harness failures count;
  every command/action is journaled privately and bounded by the remaining
  deadline. No prior clock was reset or made retroactively compliant.
- At evidence-note finalization **2026-11-14 12:40:31 UTC**,
  new continuously charged elapsed time is **44m04s**.
  Final document-coupled audits/publication follow within the same deadlines;
  the final handoff/action journal records actual completion time, not a reset.

No new product repair was made in this recovery. Original first/second control
attempts remain historical; the aggregation-order harness correction is retained
as a distinct fresh verification attempt. No native Windows campaign was run.

The review PR must state **HOSTED CI PENDING — NOT YET VERIFIED**. Codex stops
immediately after confirming PR URL and exact remote head: no Hosted CI polling,
merge, deployment or next Batch. Independent Architect exact-head diff/full
Hosted A/B/C + regression review and separately authorized native Windows
acceptance/Owner merge decision remain necessary.

Seven exclusions retain zero credit: cover/document control, Survey,
Centralizer, pore/fracture pressure, IOD, figures/schematics, attachments/TOC.
Hardware remains in scope.
`whole_program_certification=false`. All genuine J01–J15/X01–X22 Goldens and
native Microsoft Word parity remain **NOT_RUN**.
