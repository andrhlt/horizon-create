# Gameplay completion standard

This standard supersedes earlier issue descriptions and comments that required
exhaustive full-family parity before delivering a ticket. It applies to current
Create-port work and new Linear issues. Keep existing fixes and valid evidence.
Do not restart a worker's pass or rerun unchanged checks just because this policy
changed. The goal is reliable gameplay for experienced survival/LAN players.

## Finite acceptance gates

Agree a concrete, bounded case list for the ticket, using its existing comparison
matrix as the default. Record that list in the issue/PR. Do not expand it forever
because another untested combination exists. Add cases when source review or a
failure identifies a consequential gap; document broader follow-up work.

| Gate | Required evidence |
| --- | --- |
| Gameplay | The scoped ordinary functions and configurations work. No known defect in that scope prevents or materially changes normal use. |
| Important interactions | The family's relevant direction, speed, power, connection, inventory or limit boundaries pass the recorded case matrix. Compare consequential state/timing to pinned Java; reuse valid existing references. |
| Multiplayer | A host and guest can perform representative relevant actions and agree on the resulting state. Distinguish guest convergence from proven network arrival/interpolation parity. |
| Persistence | Save and reopen representative idle and active setups, retaining applicable settings, contents, connections and operation. For instantaneous/static features, use the meaningful before/after state and record why an active case is not applicable. |
| Regression | Affected existing checks and justified neighboring regressions pass on an identified final build. No entire-suite reruns per edit. |
| Delivery | Commit, push, and open a reviewable PR linked to Linear. Include commands, reference/build/pack identity, case/tick counts, outcomes, remaining gaps and the updated matrix/evidence notes. |

A source-aligned save/reopen gameplay check is sufficient for this baseline.
Run actual Java reload comparisons where uncertainty or a mismatch warrants them;
claim exact Java reload parity only with that evidence. Do not require a new
end-to-end trace for every translated source branch. Cosmetic equivalence is
not a prerequisite: models, visible movement and usable UI must be correct enough
to operate the machinery, while exact animation curves/phases, cosmetic sound
timing, exhaustive cross-products and Java-equivalent packet timing may remain
explicitly unverified.

Missing core functionality, wrong consequential power/motion/processing behavior,
crashes, lost items, duplication, broken guest interaction or corrupt/lost saves
are blockers, not cosmetic follow-ups. A known blocker owned by another worker
must be linked as a concrete dependency. Do not label the family gameplay
verified or the ticket Done until it is resolved and checked. Deliver a partial
reviewable PR rather than withholding all fixes while waiting; clearly label
which gates remain blocked.

## Status and evidence are different

- In Progress: implementation, a required gate, or a consequential blocker remains.
- In Review: baseline gates pass and the PR is ready for review. A partial PR with
  blockers may be submitted, but does not establish baseline completion.
- Done: reviewed, merged, and affected checks pass on the combined build.

The feature matrix's Full 1:1 column may remain Open after a gameplay ticket is
Done. Record gameplay baseline results and exact sampled Java comparisons in the
existing comparison/evidence fields; do not turn a scoped pass into an exhaustive
parity claim. Do not keep an otherwise complete gameplay ticket In Progress only
because a cosmetic or additional untested combination exists.

## Efficient worker loop

Read the applicable Java behavior paths, translate whole rules into the existing
Rust code, and reproduce concrete mismatches before repairing existing behavior.
Use parameterized action tables and existing capture/replay helpers. Fast checks
should exercise production logic; build and run real Horizon only for integration
that needs it. Batch fixes and focused verification. Use headless simulations and
hidden offscreen UI clients; never move the user's desktop pointer. Follow
PARITY-WORKER.md for pinned runtimes, cache isolation and the recovered launcher.
Record setup/capture, coding, build, fast-check, integration and debugging time.

## New issue template and priority

New issues describe a finite gameplay delivery pass, not an unbounded promise to
prove all possible equivalence. Include:

1. Player outcome and why a failure would block or disrupt a survival factory.
2. Existing implementation and evidence; preserve completed work.
3. Explicit required case list, relevant Java paths and dependencies.
4. Applicable gates above, with any justified not-applicable cases.
5. Commands/environment and PR deliverables; separate nonblocking follow-ups.

After the current workers finish, prioritize survival progression and multiplayer
blockers: materials/crafting; power and processing; item movement; fluids; and
crash, duplication, item-loss, guest and save/rejoin reliability. Exact cosmetic
parity follows functional completion.
