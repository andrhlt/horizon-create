# APP-2163 production wheat recipe fixture

This scoped datapack entry mirrors the existing Java-backed Create Millstone
evidence. `tools/test-milling-lookup.py` records wheat outputs of wheat flour ×1
at 100%, wheat flour ×2 at 25%, and wheat seeds ×1 at 25%. The Java trace starts
the Millstone timer at 150 ticks (`fixtures/wheat_milling-java.csv`), so this
fixture keeps `processing_time` at 150.

The integration owner should stage this directory as a test datapack for the
production fixture. It is intentionally separate from the synthetic bread
recipe and must not be combined with that override.
