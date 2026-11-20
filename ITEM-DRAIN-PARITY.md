# Item Drain gameplay baseline — APP-1988

This pass preserves the existing Item Drain implementation and Java comparisons.
It covers the finite gameplay cases below; mounted drains, all container types,
exact render/audio equivalence and Java packet/reload timing remain follow-ups.
Full 1:1 remains Open.

## Reference and scope

Create reference: `ac0c444d9828da3453ae8cc65338e8de063286fb` (6.0.10,
Minecraft 1.21.1, NeoForge 21.1.219). Horizon pin:
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, Minecraft 26.3.
Base: `be02d33b1331352ed5a69cba28d93e6f04fafeb7`.
Fluid Pipe / Glass Fluid Pipe / Smart Fluid Pipe prerequisite
[APP-1972](https://linear.app/appstu/issue/APP-1972) is Done, integrated in
[PR #16](https://github.com/andrhlt/horizon-create/pull/16).

Reviewed pinned `ItemDrainBlock`, `ItemDrainBlockEntity`, `ItemDrainItemHandler`,
`GenericItemEmptying` and `FluidHelper.tryEmptyItemIntoBE`. Java falls through
to cargo collection when a held item cannot be emptied, except ordinary block
items, which retain placement priority. Horizon previously required an empty
hand, preventing collection while holding a stick. The family-owned change
retains block placement and fluid exchange while permitting that collection.

## Finite case matrix

| Case | Evidence and boundary |
| --- | --- |
| Survival acquisition and placement | Craft one drain from iron bars above copper casing in the player grid, place it, and verify component/product consumption. Starting components are supplied; their full production chains are outside this ticket. |
| Ordinary automatic emptying | Existing 105 Java samples cover honey bottle, water bucket and three iron ingots, center approach, tick-19 conversion and blocked exit. Existing Honey/Chocolate bucket checks cover 1,000 mB and returned buckets. |
| Collection and placement priority | Cobblestone places above the drain without collecting cargo; stick and empty-hand collection deliver three ingots once. A real Java interaction capture checks five block/stick/empty-hand collection and repeat cases. |
| Rejection and recovery | After 40 ticks a honey bottle remains stalled at the center against 250 mB water or a full 1,500 mB honey tank. Direct pours retain both inventory and cargo. Clearing stored fluid allows exactly one bottle/250 mB conversion. |
| Item handoff | Existing west hopper retains two bottles while feeding one. A solid exit retains three ingots; replacing it with a drain transfers that whole stack exactly once. |
| Pipe extraction | Existing survival pour/plumbing check transfers all 250 mB honey to a tank. Affected fluid-pipe transfer/startup checks guard the established prerequisite. |
| Host and guest | Both survival players pour honey and receive bottles, sharing 500 mB. Host empty-hand and guest stick collection clear authoritative cargo and deliver exactly three ingots to the acting inventory; repeated actions do not duplicate it. Guest convergence is checked, not exact packet timing. |
| Persistence | Cold reopen an idle drain with 250 mB honey; reopen partway through emptying another bottle; then reopen its completed state. Exactly one glass bottle and 500 mB survive. Startup may advance simulation before freeze; this checks gameplay conservation and operation, not exact Java restart timing. |

## Reproduction and artifacts

The first collection attempt was an invalid fixture: synthetic `HeldItem` data
had no serialized item before the first tick. The helper now ticks and verifies
its seeded cargo before interaction. The original failure remains in
`.local/baseline-repro/collection.log` and
`collection-invalid-seed-client.log`.

The corrected fixture reproduced the actual stick-collection failure on
preserved client `native-9f42064-342fc62b27be`: expected no cargo after clicking,
observed three iron ingots still on the drain. Logs:
`.local/baseline-repro/collection-valid-seed.log` and
`collection-valid-seed-client.log`.

## Interaction diagnosis and rebuilt verification

The instrumented interaction run used `horizon-ctl interact 4 97 -9 up`, which
aims the player and sends the normal right-click input. On client
`native-9f42064-4e90ea97e8c9` (binary SHA-256
`5a0ae25103e9cc1e91f07d727655a0ba839379771eef29f5ed39d9a4f689b93d`), the
dispatcher received target `[4,97,-9]`, top face `[0,1,0]`, uncancelled state,
and held cobblestone / then stick in the main hand. The Item Drain handler was
entered for each with the same target and held stack. The handler was therefore
reached through normal player interaction; this was not a test API shortcut.
The original handler rejected every nonempty hand before collection. The fix
now lets ordinary block items pass through to placement and collects cargo for
non-fluid items, matching pinned Java `ItemDrainBlock.useItemOn` behavior.

The trace build's gameplay assertions passed block placement, stick collection,
repeated-click nonduplication, empty-hand collection and item conservation.
The LAN run passed host empty-hand and guest stick collection against server
state and each actor's inventory, preserving shared fluid. Trace-only logging
was removed before the clean final build; the checks are rerun on that clean
client. `native-mods.json`'s mod SHA identifies the unpacked native mixin bundle
including its manifest; it is distinct from the `.hmod` archive checksum. Each
fixture verifies the copied pack bytes, SHA-256
`fb4bcdfdcf9b1c1f7c0e00f0f8f06941ef8b65b20ddd03cecf466dd84c5db82a`, and
enables it with `mod.create:true`.

Runtime assets, private compilation caches, isolated worlds and raw logs stay
under this worktree's `.local/`. No desktop game or shared writable build cache
is used. No paid action is involved.

## Clean final build and checks

After integrating `origin/main` at `7145d9e` in merge commit `1576553`, the clean build
selected client `native-9f42064-623167a8ed31` from pinned Horizon
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`; client SHA-256
`239cc6928ac97a84b620c0fbb3a1040840ed80c2351dd6329a24d47f53805ef8`.
Its `native-mods.json` records native mixin bundle SHA-256
`b024817954cd3fca050fd03b8beebd33764400411c54c5d13de9b0b40464f93c`.
The selected test pack is `.local/create.hmod`, copied into every isolated
world with SHA-256
`fb4bcdfdcf9b1c1f7c0e00f0f8f06941ef8b65b20ddd03cecf466dd84c5db82a`; loader
logs report one mod's content and the Create gameplay fixtures load its block,
items and block entity successfully.

Final command:

```sh
python3 tools/test-parity.py \
  .local/patched-launcher/versions/native-9f42064-623167a8ed31/horizon-ctl \
  .local/patched-launcher/versions/native-9f42064-623167a8ed31/horizon-client \
  .local/patched-launcher/versions/native-9f42064-623167a8ed31/.local/horizon-client/26.3 \
  --jobs 1 --check item-drain-gameplay --check item-drain-lan \
  --check item-drain --check depot-comparator
```

All four checks passed on that clean build. Gameplay verified survival
acquisition, block placement priority, stick and empty-hand collection, repeat
clicks, conservation, rejection/recovery, handoff and reopen behavior. LAN
verified host and guest collection against server and acting-player inventories.
The Item Drain checks retained all 105 Java samples, hopper behavior, liquid
render samples and survival plumbing; the shared depot comparator retained its
17-tick Java match. Source syntax passed for 477 JSON/JSONL/Python/shell/TOML
files; Python byte-compilation and `git diff --check` passed.

Logs are under `.local/parity/` and `.local/horizon-*.log`; private generated
worlds, builds, runtime assets and logs remain ignored from version control.

## Java collection capture provenance

The disposable pinned checkout passed one required GameTest and produced the
five rows in `fixtures/item-drain-collection-java.csv`; metadata is in
`fixtures/item-drain-collection-java.metadata.json`. This calls the actual
`BlockState.useItemOn` with a NeoForge FakePlayer and asserts cargo, inventory,
held-tool counts and interaction results. All observations occur synchronously
in one test callback; this is not an elapsed processing-tick comparison.

| Case | Java result | Drain ingots | Inventory ingots | Held tool count |
| --- | --- | --- | --- | --- |
| block_pass | PASS_TO_DEFAULT_BLOCK_INTERACTION | 3 | 0 | 1 |
| stick_collect | SUCCESS | 0 | 3 | 1 |
| stick_repeat | SUCCESS | 0 | 3 | 1 |
| empty_collect | SUCCESS | 0 | 3 | 0 |
| empty_repeat | SUCCESS | 0 | 3 | 0 |

Patch: `tools/java-item-drain-collection.patch`, SHA-256
`e50e6a0882c98e1a2f86e6e053e6862350e38bdd071bab354f2df9175b11ff33`.
Java 21.0.13.1 (Homebrew, aarch64), Minecraft 1.21.1 and NeoForge 21.1.219.
Gradle completed in 8m 32s including first-time NeoForge artifact preparation;
the GameTest itself took 1.983s. Raw successful log:
`.local/java-drain-collection/capture-private-approved.log`.

The Java block-item row stops after the callback returns
`PASS_TO_DEFAULT_BLOCK_INTERACTION`, so its cobblestone remains held. The Horizon
check follows through normal placement, places cobblestone above the drain and
consumes it. Only the pass-through/retained-cargo rule is compared for that row;
these observations do not claim identical consumed block-item counts.

The initial restricted launches could not create the shared wrapper lock or a
local Gradle lock socket. Their logs are retained as `capture.log` and
`capture-private.log`. The successful launch used an approved local socket and
an APFS copy of populated Gradle caches under the worktree, leaving the shared
Java checkout and writable Gradle cache untouched. Exact successful command,
from this worktree:

```sh
JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home GRADLE_USER_HOME="$PWD/.local/java-drain-collection/gradle-home" ./.local/java-drain-collection/create/gradlew --offline -p .local/java-drain-collection/create runGameTestServer > .local/java-drain-collection/capture-private-approved.log 2>&1
```

For a fresh disposable capture using the portable driver and the existing
private populated cache:

```sh
python3 tools/capture-item-drain-collection-java.py --source /Users/andrewholt/dev/horizon-create/.local/java-reference --gradle-home .local/java-drain-collection/gradle-home
```

The driver clones and patches a disposable checkout, retains a unique raw log,
and writes the five portable observations only after Gradle succeeds. An empty
private cache cannot satisfy `--offline`; populate or copy it first. This
capture does not establish Java save/reload or network timing equivalence.
