#!/usr/bin/env python3
"""Translate the legacy Create mixin manifest to a flat native mod project.

This preserves the source files and IDs. The target Horizon SDK still decides
whether old module destinations and mixin targets remain valid.
"""

import argparse
import json
from pathlib import Path
import shutil
import tomllib


def toml_value(value):
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(
            f"{key} = {toml_value(item)}" for key, item in value.items()
        ) + " }"
    raise TypeError(f"unsupported TOML value: {value!r}")


def write_table(output, name, values):
    output.write(f"\n[[native.{name}]]\n")
    for key, value in values.items():
        output.write(f"{key} = {toml_value(value)}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--horizon", required=True)
    parser.add_argument("--mixins", required=True)
    parser.add_argument("--metadata", type=Path, default=Path("content"))
    parser.add_argument("--content", type=Path)
    parser.add_argument("--native", type=Path, default=Path("native"))
    parser.add_argument("--skip-mixin-prefix", action="append", default=[])
    parser.add_argument("--exclude-mixin-id", action="append", default=[])
    parser.add_argument("--skip-module-id", action="append", default=[])
    args = parser.parse_args()

    content = tomllib.loads((args.metadata / "horizon-mod.toml").read_text())
    legacy = tomllib.loads((args.native / "horizon-mixin.toml").read_text())
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"output directory is not empty: {out}")
    out.mkdir(parents=True, exist_ok=True)

    fields = ("id", "name", "version", "description", "authors", "api", "side", "capabilities")
    lines = [f"{key} = {toml_value(content[key])}" for key in fields if key in content]
    lines += ["", "[native]", 'game = "26.3"', f'horizon = {toml_value(args.horizon)}',
              f'mixins = {toml_value(args.mixins)}']
    (out / "horizon-mod.toml").write_text("\n".join(lines) + "\n")
    (out / "Cargo.toml").write_text(
        f'[package]\nname = "mod-{content["id"]}"\nversion = "{content["version"]}"\n'
        'edition = "2024"\n\n[dependencies]\n'
        'horizon-mod-api = { path = ".horizon/sdk/api/crates/horizon-mod-api" }\n'
    )

    modules_dir = out / "src/modules"
    mixins_dir = out / "src/mixins"
    modules_dir.mkdir(parents=True)
    mixins_dir.mkdir(parents=True)
    skipped_hooks = []
    skipped_mixins = []
    with (out / "horizon-mod.toml").open("a") as manifest:
        for module in legacy.get("module", []):
            if module["id"] in args.skip_module_id:
                continue
            source = module["source"]
            shutil.copy2(args.native / source, modules_dir / source)
            write_table(manifest, "module", {
                "id": module["id"], "file": module["file"], "name": module["name"],
                "source": f"src/modules/{source}",
            })
        for injection in legacy.get("injection", []):
            helper = injection["helper"]
            if "hook" in injection:
                skipped_hooks.append((injection["id"], injection["hook"], helper))
                continue
            if (injection["id"] in args.exclude_mixin_id or
                    any(injection["id"].startswith(prefix) for prefix in args.skip_mixin_prefix)):
                skipped_mixins.append((injection["id"], helper))
                continue
            shutil.copy2(args.native / helper, mixins_dir / helper)
            row = dict(injection)
            row["helper"] = f"src/mixins/{helper}"
            write_table(manifest, "mixin", row)

    if args.content:
        source = args.content.resolve()
        for directory in ("assets", "data"):
            original = source / directory
            if original.is_dir():
                shutil.copytree(original, out / directory)
    (out / "src/lib.rs").write_text(
        "//! Create's frozen-SDK native entry point.\n"
        "#[derive(Default)]\nstruct Mod;\n\n"
        "#[mod_api::horizon_mod]\nimpl mod_api::Hooks for Mod {}\n"
    )
    (out / ".gitignore").write_text("/.horizon/\n/target/\n")
    (out / "migration-exclusions.txt").write_text(
        "Excluded rows require Parts/native mixin translation or fall outside Stage 1.\n"
        + "\n".join(f"{row[0]}\t{row[1]}\t{row[2]}" for row in skipped_hooks)
        + "\n"
        + "\n".join(f"{row[0]}\tStage 1 exclusion\t{row[1]}" for row in skipped_mixins)
        + "\n"
    )


if __name__ == "__main__":
    main()
