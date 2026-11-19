#!/bin/sh
# Stage the pinned Horizon patches in a separate launcher directory.
set -eu

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 /path/to/horizon-launcher /path/to/launcher-data" >&2
    exit 2
fi

launcher=$1
data=$(CDPATH=""; cd -- "$2" && pwd)
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
# New launchers only accept SDK crates; this port still uses pinned source mixins.
# Keep the installed app intact and use the official compatible CLI separately.
if ! "$launcher" native-build --help 2>&1 | grep -q 'horizon-mixin.toml'; then
    echo "Installed launcher uses the newer SDK; selecting the pinned mixin launcher." >&2
    launcher=$(python3 "$root/tools/pinned-launcher.py")
fi
revision=9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0
base=nightly-2026-11-13-9f42064
work="$root/.local/patched-launcher"
source="$work/native/source/$revision"

mkdir -p "$work/native/source" "$work/versions"
set -- "$root"/patches/horizon-*.patch
patch_digest=$(cat "$@" | git hash-object --stdin)
if [ ! -f "$source/.create-patch-digest" ] ||
   [ "$(cat "$source/.create-patch-digest")" != "$patch_digest" ]; then
    prep=$(mktemp -d "$work/native/source/create-patches.XXXXXX")
    trap 'rm -r "$prep"' EXIT
    cp -pR "$data/native/source/$revision" "$prep/prepared"
    test "$(cat "$prep/prepared/.horizon-revision")" = "$revision"
    for patch do
        GIT_CEILING_DIRECTORIES="$work/native/source" git -C "$prep/prepared" apply "$patch"
    done
    printf '%s\n' "$patch_digest" > "$prep/prepared/.create-patch-digest"
    if [ -d "$source" ]; then
        mv "$source" "$prep/previous"
    fi
    if ! mv "$prep/prepared" "$source"; then
        if [ -d "$prep/previous" ]; then
            mv "$prep/previous" "$source"
        fi
        exit 1
    fi
    rm -r "$prep"
    trap - EXIT
fi
test "$(cat "$source/.horizon-revision")" = "$revision"

# The launcher hashes the mod bundle. Include the engine patches that it builds against.
staging=$(mktemp -d "$work/create-build.XXXXXX")
trap 'rm -r "$staging"' EXIT
cp -R "$root/native" "$staging/create"
printf '\n# Horizon patch digest %s\n' "$patch_digest" >> "$staging/create/horizon-mixin.toml"

for cache in cargo rust native/tools native/target "versions/$base"; do
    if [ ! -e "$work/$cache" ] && [ -d "$data/$cache" ]; then
        ln -s "$data/$cache" "$work/$cache"
    fi
done

export HORIZON_LAUNCHER_HOME="$work"
export HORIZON_HOME="$root/.local/patched-game"
if ! "$launcher" instance list | awk 'index($0, "Create Patched Build (") {found=1} END {exit !found}'; then
    "$launcher" instance create "Create Patched Build"
fi
# The isolated launcher reuses the normal build cache.
"$launcher" settings native-cache-gib 0
"$launcher" native-build "$staging/create" --instance "Create Patched Build" \
    --version "$base" --trust-native-code --profile performance
