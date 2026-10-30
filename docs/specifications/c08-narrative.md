# C08 Executive Summary — partial narrative evidence

Owner G02 authorizes this additive Checker feature branch only. Main, original App,
accepted C01R–C07 and private recovery remain unchanged. The 143-file source lock is
60dffefb8c941ad90cb7caba0992126a35803717; its template blob remains
1d77ebb7140e1bf0fa3d7cbd092f215290a187c0. No new engineering/text rules or tolerances.

Run in the established provisioned, Git-free private runtime:
`python -B c08_summary.py input.docx operator.json`.
The JSON result retains every C01R record, document SHA, physical locator and order,
independent input digest, source module hashes/calls, complete exact reference text,
and MATCH/DISCREPANCY/NOT_VERIFIABLE. Status remains PARTIAL_FINDINGS_ONLY.

Automatic independent inputs (see the synthetic factory in tests/test_c08.py):
canonical job_type; fluids with source volume/density/pump_rate; canonical hardware;
placement_config; the unchanged C02 cement_operator; per-active-slurry tops with
explicit top_job_type/top_mode/top_depth; current executive_summary_config with
explicit placement_context_rows and per-slurry volume_basis; explicit geo_md.
No input is taken from Word. Source validators reject contradictory identities,
unsupported material properties and incomplete placement/metadata. Optional fluid
absence is not a failure. Client volumes are never replaced by geometry. Qualifier
quantities/tokens use original placement validators/resolvers. Source placeholders
cannot become a verified reference. CT's additional full-project admission is not
implemented, and is rejected rather than bypassed.

The original generate_executive_summary runs inside the installed Streamlit
AppTest's genuine ScriptRunner/SessionStateProxy. No App source, session-state
proxy, source function, CT gate or approval flag is patched/replaced. The fresh
ordinary-job session contains no approval inputs. This is an isolated execution
context, not a live App session, UI feature or export-readiness certification.
Existing C02, fluid and placement authorities validate/calculate independent inputs;
the bridge does not relax engineering_source.py's existing state prohibition.
Original source functions and origins are recorded and source hashes verified before
and after. Network is denied and writes restricted to runtime tmp/cache.

Alternatively provide only job_type and manual_summary={text, approval_reference,
text_sha256}. This explicitly independent approved text is the reference; no App
approval/cache flag is created and automatic generation is not claimed. Approval
provenance must be supplied independently, never inferred from the candidate Word.

The pinned template renders the whole summary in one physical paragraph containing
internal breaks. C08 proves one semantic section envelope and one physical paragraph;
only the C01R-proven excluded TOC may be skipped. Repeated/split paragraphs, unknown
headings, tables and unproved wrappers fail closed. Split runs are retained.
Only horizontal whitespace is normalized; case, numbers, units, punctuation and
line/break order remain significant. Missing/dash/N/A retain their original states.
Document-control metadata and other sections remain indexed but unverified.

Verification: the starting main run 41035710035 independently authenticated 261 tests
(A107/B63/C91), all 783 phases and source/attempt artifacts. C08 adds one whole-module
shard A assignment because observed main A took 170 seconds, versus B331/C499.
Focused local estimate <2 minutes; hosted suite estimate <10 minutes, C08 cumulative
<20 minutes. Early controls rejected an accidental checkout invocation before source
execution; generated files were moved out. A genuine structural control then exposed
the intervening TOC and was corrected using its existing proven exclusion. Assertions
and accepted files were not weakened. Local preliminary results are not hosted authority.
Existing migration tests cover routing gaps/overlap, final-byte digest mutation,
missing/duplicate phases, skip/xfail/warnings and stale run/attempt certificates.

NOT RUN/NOT CLAIMED: 15-job goldens, complete exceptional-job/manual export parity,
whole-program narrative/engineering parity, original App regression, native Word/browser,
corrected DOCX, UI, integration, release or deployment.
