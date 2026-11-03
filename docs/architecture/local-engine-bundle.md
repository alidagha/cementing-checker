# R1 — locally available pinned source engine

The Owner authorized packaging every one of the 143 resources enumerated by
`upstream.lock.json`, from source commit
`60dffefb8c941ad90cb7caba0992126a35803717`. The lock remains the sole file and
SHA256/Git-blob inventory. No formula, source test, resource or template is edited.

`checker_engine/60dffefb8c941ad90cb7caba0992126a35803717.tar.gz` is a deterministic
gzip/USTAR archive: lexically sorted `pinned/<locked path>` members, zero timestamps
and ownership, empty owner names, mode 0444, gzip timestamp zero and no gzip filename.
Its SHA256 is `2aee7c402ae0b6849bef38b71e8646fb3a92f152a3f1de874c1e642b2dbf97a5`.
The unchanged template SHA256 is
`a1128b0e9352e1dd7c8768eecc9335c50858356cee80ed33c0ec275e26c4d08b`.

The source bundle is deliberately opaque to native Checker test discovery. It
includes all locked upstream test/support resources without running their tests
as Checker tests. The public-inventory scanner permits only this exact package
path and verifies every member against the existing lock; arbitrary binary or
document exceptions are not permitted.

`tools/provision.py --destination NEW_PRIVATE_DIRECTORY` verifies the local bundle
before creating a destination and copies the source bytes into the existing
`snapshot/` layout. It rejects missing/extra/changed members, symlinks, traversal,
oversized input, overlapping runtimes and overwrites. The bundle is omitted from
the runtime copy to avoid storing both compressed and expanded source there.
Seeding and C01R–C10 consumers keep their existing private paths and isolated source
workers. There is no network retrieval or remote fallback in provisioning.

Python 3.12 and the 51 pinned Python distributions must already be installed;
offline wheel packaging belongs to a separate release gate. R1 preserves the
merged R0 session-authorized delivery, diagnostic controls and 60-minute CI policy
from main; the separate planning branch is not imported. Full original/corrected
Word coverage and the future full audit report remain separate work. No Golden,
whole-program or production-release certification is implied by local source
availability.
