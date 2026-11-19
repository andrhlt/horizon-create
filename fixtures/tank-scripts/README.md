# Shared tank scenarios

Each JSON file is an ordered action script. The generic Java runner and both
Rust/Horizon adapters consume it; a new scenario needs data, not another patch.

Supported operations:

- `place`, `remove`: a relative three-coordinate `pos`; placement accepts `block: "creative"`.
- `fill`: `pos`, registry `fluid`, nonnegative `amount`, optional `components` and `simulate`.
- `drain`: `pos`, `amount`, optional requested `fluid`/`components` and `simulate`.
- `configure`: creative tank `pos`, `fluid`, `amount`, and optional `components`.
- `wrench`: `pos`, invokes the production wrench interaction with a held wrench; integration only.
- `setblock`: `pos` and a vanilla command `state`; integration only.
- `clone`: relative `from`, `to`, `dest` and `mode: "copy"` or `"move"`; integration only.
- `tick`: nonnegative integer `count`.
- `probe`: string `label` and a list of relative `positions`.

Logical time starts at zero. Non-tick actions retain file order. A probe after
mutation is immediate, before the next block-entity tick. Fill is fixture setup;
it does not prove player inventory or bucket behavior. Top-level
`include_components: true` includes component identity in probe and drain records. `include_shape` and
`include_signals` opt into shape and actual light/comparator probe fields for
integration scenarios.
Scripts marked `integration_only: true` exercise actual world lifecycle and are
excluded from the default core suite; the core rejects unsupported operations.
Column and wider-group removal both use the production split implementation.

Java JSONL and provenance are in `java/`. All records, including actual controller
positions and accepted fill amounts, are compared. Stale script or recorded patch hashes
fail the comparison. Each capture archives its exact Java runner under
`java/runners/<sha256>.patch`; adding an optional observer does not force
recapturing unchanged scripts whose original oracle runner remains available. Captures use pinned Create `ac0c444d9828da3453ae8cc65338e8de063286fb`.

Run the fast checks (cached Rust dependencies required for `--offline`):

```sh
python3 tools/test-tank-script.py --backend core
```

Run one real headless integration scenario:

```sh
python3 tools/test-tank-script.py /path/to/horizon-ctl /path/to/horizon-client /path/to/26.3 --script fixtures/tank-scripts/flat-split.json
```

Capture new Java references with one patch and a fresh disposable world per case:

```sh
python3 tools/capture-tank-script-java.py fixtures/tank-scripts/new-case.json --output fixtures/tank-scripts/java
```

Add `--jobs 2` to `tools/test-tank-script.py` to run independent isolated
worlds in parallel. The command completes all scenarios and lists every failure,
so one red case does not hide later results.

The capture tool requires Java 21 and populated offline Gradle caches. Repeated
core timing is available through `tools/run-tank-script.py core ... --repeat N`;
repetitions measure cost and do not expand scenario coverage. See
[the audit](../../ARCHITECTURE-AUDIT.md) for measurements and limitations.
