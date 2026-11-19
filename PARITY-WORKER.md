# Independent feature-family workers

Own the entire Linear issue's feature family through implementation, reference
comparison, review, and integration. The issue's matrix row is the starting
state; retain existing working code and evidence. Do not restart the port.

## Reference and efficient implementation

- Read README.md, FEATURE-MATRIX.md, PARITY.md, and the family-specific notes.
- Java reference: Creators-of-Create/Create at
  ac0c444d9828da3453ae8cc65338e8de063286fb (Create 6.0.10,
  Minecraft 1.21.1, NeoForge 21.1.219). Horizon pin:
  9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0, Minecraft 26.3.
- Inspect the actual Java classes and callbacks first. Translate their state,
  algorithms, ordering, defaults and transitions directly into the existing Rust
  modules. Use a small pure production module only where it enables fast checks;
  avoid a framework or a parallel implementation solely for tests.
- Enumerate the family's applicable paths: variants, placement/orientation,
  settings, recipes/drops, interaction, redstone/kinetics, errors, rendering,
  sounds, persistence and host/guest behavior. Compare this list to existing
  fixtures; implement and verify uncovered behavior in batches.
- Reproduce a mismatch before changing existing behavior. Capture a real Java
  trace, including transitions and negative cases, then compare Horizon to it.
  Do not generate expected values from the Rust implementation. Confirm each
  fixture actually exercises the intended running behavior; a stationary rig
  is not evidence for movement.

## Local environment and isolation

The repository excludes .local, runtime resources, compiled clients, imported
Java checkouts and Gradle caches. A fresh worker must locate or provision these
before claiming runnable checks. On the original machine the Java checkout is
in the primary repository's .local/java-reference; clone it at the pinned commit
into the worktree's .local/java-reference if using capture scripts that expect
that path. Obtain the pinned upstream checkout if that local copy is absent.
Java captures use JDK 21; --offline Gradle requires populated dependencies.
Do not modify a shared Java reference checkout: apply capture patches to a
disposable clone (see tools/capture-mechanical-piston-modes-java.py).

Build command (paths depend on machine):

    sh tools/build-native.sh /path/to/horizon-launcher /path/to/launcher-data

IMPORTANT: this script has a worktree-local .local/patched-launcher but symlinks
native/target to the supplied launcher-data compilation cache. Concurrent workers
must use separately provisioned writable launcher/cache data, or serialize builds
through the coordinator. Do not assume separate git worktrees alone isolate
builds. Do not change another worker's selected instance, game installation or
normal Create Parity Lab. Runtime paths must be verified locally, not guessed.

The current port is a source-mixin build, not a current-SDK native crate.
Launcher 0.2.82 rejects that format. The build script detects this and selects
the official launcher 0.2.67 in the worktree's `.local/toolchains/` instead.
`tools/pinned-launcher.py` downloads its macOS arm64 ZIP and checks SHA256SUMS
through `gh` when absent; it does not replace the installed Horizon app.
This restores the existing build route. It does not migrate the port to
`horizon-mod.toml` or prove compatibility with the latest Horizon SDK.
Do not rename the manifest or independently migrate shared integration code
as part of a gameplay ticket. Coordinate the SDK migration separately.
The modern SDK supports native mixins/modules/bridges, so migration is possible
in principle. It must translate the current 202 support modules and 378
injections, validate the separate engine patches, and use the exact SDK/build
contract. Merely adding Cargo.toml/src or renaming the manifest is insufficient.
Reference: https://github.com/horizon-rust/horizon/blob/main/docs/modding/src/concepts/native-route.md

The script prints a native build identifier. Use that exact build's horizon-ctl,
horizon-client and prepared .local/horizon-client/26.3 resources. Run:

    python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --jobs 2 --check 'SELECTED-NAME'

Read CHECKS in tools/test-parity.py for actual names; repeat --check as needed.
Use the included fixture_world and test-multiplayer helpers for isolated worlds.
Run simulations with --headless and visual/interaction checks with hidden
--offscreen clients. Never open or control the user's desktop game. Use unique
worlds, ports, logs and outputs. Register new repeatable checks in the runner.
Use tools/prepare.py --help for upstream asset/fixture preparation; inspect the
arguments and output paths before running it so existing evidence is preserved.

## Evidence and completion

Prefer a fast Java-derived check of production logic while iterating, then batch
real Horizon checks on one identified build. Compare every sampled tick, with a
stated tick origin, observable fields, tolerance (zero for exact discrete state)
and source revision. Cover solo, LAN host and guest; distinguish authoritative
server timing from guest eventual replication and interpolation. A wait for
replication does not prove Java network arrival timing. Compare actual Java
save/reload where claiming reload parity. Source-matched render parameters alone
do not prove identical pixels or sound timing.

Preserve failed captures/results and label invalid fixtures rather than silently
replacing evidence. Record capture patch hashes, reference metadata, build and
pack identity, elapsed time, test commands, per-case outcomes and unresolved gaps.
Commit portable fixtures and summaries; keep bulky runtime logs in .local and
attach or otherwise make essential evidence available to reviewers.

Use a branch/worktree per ticket from a committed main baseline. Coordinate
changes to shared native/machines.rs, native/horizon-mixin.toml, engine patches,
preparation scripts, runner and matrix. Make narrow edits; do not reformat whole
shared files. Push the branch and open a PR referencing the Linear issue.
Update the family row and evidence notes in that PR. A passing representative
fixture does not justify marking the whole family Full 1:1. If any applicable
path is unimplemented or unverified, keep that gap explicit and do not close the
issue as fully verified. Describe concrete environment blockers in Linear.

The coordinator reviews/merges PRs, resolves overlapping changes and reruns the
affected checks on the combined build before treating integration as complete.
