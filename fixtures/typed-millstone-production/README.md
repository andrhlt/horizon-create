# APP-2163 production wheat recipe fixture

The test recipe mirrors the shipped production entry
`content/data/create/recipe/milling/wheat.json`. `tools/test-milling-lookup.py`
records wheat outputs of wheat flour ×1 at 100%, wheat flour ×2 at 25%, and
wheat seeds ×1 at 25%. The Java trace starts the Millstone timer at 150 ticks
(`fixtures/wheat_milling-java.csv`), so the production recipe keeps
`processing_time` at 150.

`tools/build-typed-millstone-production-pack.py` combines this recipe's block
and item resources with a base pack for the managed production fixture. The
synthetic bread recipe remains excluded from this flow.
