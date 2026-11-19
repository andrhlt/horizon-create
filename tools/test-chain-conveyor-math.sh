#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 /path/to/horizon-git-checkout" >&2
    exit 2
fi

root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
revision=$(sed -n 's/^revision=//p' "$root/tools/build-native.sh")
rustc=${RUSTC:-rustc}
tmp=$(mktemp -d)
trap 'rm -r "$tmp"' EXIT

mkdir "$tmp/geometry"
git -C "$1" show "$revision:crates/horizon-core/src/geometry/trig.rs" > "$tmp/geometry/trig.rs"
printf 'pub mod geometry { pub mod trig; }\n' > "$tmp/horizon_core.rs"
"$rustc" --edition=2021 --crate-type=rlib "$tmp/horizon_core.rs" --out-dir "$tmp"
"$rustc" --edition=2021 --test "$root/tools/test-chain-conveyor-math.rs" \
    --extern horizon_core="$tmp/libhorizon_core.rlib" -o "$tmp/replay"
"$tmp/replay" --nocapture
