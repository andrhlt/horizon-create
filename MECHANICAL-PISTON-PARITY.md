# Mechanical piston comparison

Reference: Create 6.0.10, commit `ac0c444d9828da3453ae8cc65338e8de063286fb`.
The Java captures are generated GameTests, separate from the original four-tick
`ploughing` fixture. The capture patches and metadata are in `tools/` and
`fixtures/` with the prefix `mechanical-piston` (the Java patches begin
`java-mechanical-piston`).

The comparison covers 24 sampled ticks for each of six scenarios: the three
movement modes with an extended Sticker and attached stone; the non-sticky
piston; an immovable bedrock obstruction; and a glued payload including the
extended Sticker, stone, mechanical plough and harvester. The replay compares
piston offset, speed and state, nearby block states, moving payload names, and
Sticker extension and power; the actor scenario also compares the cells above
the piston. Run the named checks with `tools/test-parity.py --check
'mechanical-piston-*'` after supplying the usual binary and resource paths.

On November 19, the selected suite passed 13/13 checks on
`native-9f42064-a5156e57df79`, including all six 24-tick Java comparisons,
the original ploughing fixture, LAN state checks for the Sticker and multi-actor
payload, a Horizon reload, offscreen rendering on host and guest, and the
host/guest mode control board. The earlier build exposed a missing screen
registration; its failed result is retained in
`.local/mechanical-piston/suite-before-ui-fix.log`.

The LAN checks compare the authoritative host on each server step to Java and
wait for guest block states to converge on each step. They do not establish
Java network packet timing or client interpolation parity. The reload check
compares a restarted Horizon world to an uninterrupted Java trace; it is not
a Java save/reload comparison. A separate hidden offscreen rendering check
exercises the moving Sticker head. The control board uses Java's option labels;
its interaction and visual details have not been exhaustively compared to Java.

Full piston parity remains open: these six traces do not cover every
orientation, pole length, payload, block interaction, speed transition,
collision, lifecycle, sound, or multiplayer presentation. The existing
gearbox piston fixture uses vanilla pistons and is not evidence of mechanical
piston behavior.
