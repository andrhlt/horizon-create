# Two-train signal junction evidence

Pinned Java: Create `ac0c444d9828da3453ae8cc65338e8de063286fb` (Create 6.0.10, Minecraft 1.21.1), JDK 21.0.13.1. The bounded GameTest patch is `tools/java-two-train-signal-junction-trace.patch`; its 108 per-tick signal samples are in `two-train-signal-junction-java.csv`.

The first fixture attempt put its track at the GameTest template's existing edgepoint. Station discovery reported `OCCUPIED`, so the targeting click failed before station placement. This was an invalid fixture, not an assembly defect. Moving the same straight track into a clear area made both station targeting clicks valid. The station logs showed both assembly modes enabled and both bogeys accepted for each station. The second station's bogeys are placed in its runtime-discovered assembly direction.

The bounded trace starts with all four heads GREEN (tick 13), protects all conflicting approaches RED while both trains occupy the section (tick 80), then clears the two shared-section heads GREEN once both trains leave that section (tick 90). The remaining outer RED heads protect the trains in the next blocks. The GameTest asserts each checkpoint and passes on the pinned Java runtime.

The candidate was already built from the matching final production sources. Host probe evidence on that candidate used the validated two-station assembly setup: both trains assembled; the heads changed from all GREEN to occupied RED states, then the shared section cleared as trains moved into the next block. Existing LAN evidence independently showed the guest's local lamp states matching the host at five occupancy-transition checkpoints (seven reads per checkpoint). This is representative two-train coverage, not exhaustive railway parity.

Candidate pack SHA-256: `e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
