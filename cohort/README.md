# APP-2137 cohort preparation

This directory records the preparation-only deployment cohort for the five
scoped Horizon repositories. It is intentionally not a final release
certificate: Create migration lanes and Naturalist integration still gate the
combined candidate.

The supported Create owner path is the APP-2136 launcher 0.2.105 route. The
manifest records the immutable engine, SDK, mixin, Rust, launcher, source and
known artifact identities without changing any other worker's checkout or
cache.

Run the small compatible-install check with isolated output paths:

```sh
python3 tools/check-cohort-install.py \
  --carry-on /path/to/horizon-carry-on \
  --wildlife-tuning /path/to/horizon-wildlife-tuning \
  --huge-trees /path/to/horizon-huge-trees \
  --stage /private/tmp/app-2137-cohort-install
```

The checker validates source commits, package SHA-256 values and native
manifest pins where applicable, then writes the same companion packages to
isolated `client/` and `server/` inputs plus `INSTALL-MANIFEST.json`. It does
not launch Minecraft, consume account state, or certify Create/Naturalist
gameplay, guest joining, persistence or cross-mod behavior.
