# Create port project guidance

- Read README.md, FEATURE-MATRIX.md, PARITY-WORKER.md and
  COMPLETION-STANDARD.md before starting a gameplay ticket.
- COMPLETION-STANDARD.md defines the finite gameplay completion gates and
  supersedes older requirements for exhaustive parity before ticket delivery.
  Preserve current work and valid evidence; do not restart or expand scope forever.
- Translate the pinned Java rules directly. Fix consequential gameplay and
  multiplayer/save failures; document cosmetic and untested follow-ups honestly.
- A ticket can be Done after integration while Full 1:1 remains Open in the matrix.
  Do not claim exhaustive parity from representative tests.
- Use headless/offscreen clients, isolated worlds/outputs and the documented
  compatible launcher. Coordinate shared code and writable compilation caches.
  Preserve other workers' code, uncommitted changes, worlds and evidence.
- Commit, push and open a linked PR when the agreed pass is ready. Do not wait
  for a separate close command merely because older comments suggested one,
  unless the user has explicitly imposed that restriction on this worker.
- New Linear issues must use the finite template and progression priorities in
  COMPLETION-STANDARD.md. Prioritize blockers to survival/LAN factory gameplay.
