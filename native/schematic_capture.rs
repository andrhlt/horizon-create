// Schematic and Quill world capture. The caller supplies the selected corners.
use super::*;
use crate::items::ItemStack;
use horizon_client::{first_person::Hand, text::Text};
use horizon_world::nbt::{Compound, Tag};
use std::cell::Cell;
use std::path::{Path, PathBuf};

const QUILL: &str = "create:schematic_and_quill";
const QUILL_SELECTION: &str = "create:schematic_selection";
const MAX_CAPTURE_BLOCKS: i64 = 1_000_000;

thread_local! {
    static EXPORTING_QUILL: Cell<bool> = const { Cell::new(false) };
}

fn bounds(first: [i32; 3], second: [i32; 3]) -> Option<([i32; 3], [i32; 3])> {
    let origin = std::array::from_fn(|i| first[i].min(second[i]));
    let mut size = [0; 3];
    for i in 0..3 {
        size[i] = first[i]
            .max(second[i])
            .checked_sub(origin[i])?
            .checked_add(1)?;
    }
    Some((origin, size))
}

fn safe_segment(value: &str) -> Option<String> {
    if value.is_empty()
        || value.len() > 48
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'_' | b'-'))
    {
        return None;
    }
    Some(value.to_ascii_lowercase())
}

fn capture_size(first: [i32; 3], second: [i32; 3]) -> Option<([i32; 3], [i32; 3])> {
    let bounds = bounds(first, second)?;
    let volume = bounds
        .1
        .iter()
        .try_fold(1i64, |volume, size| volume.checked_mul(i64::from(*size)))?;
    (volume <= MAX_CAPTURE_BLOCKS).then_some(bounds)
}

fn quill_capture(game: &mut Game<'_>, pos: [i32; 3], stack: &ItemStack) -> bool {
    if stack.item.as_ref() != QUILL || game.hand != Hand::Main {
        return false;
    }
    if !game.native_authoritative() {
        return true;
    }
    let Some(player) = game.native_acting_player() else {
        return true;
    };
    if !game.may_build() || player.game_mode == 2 || player.game_mode == 3 {
        return true;
    }
    if game.native_sneaking() {
        if let Some(held) = game.held_mut() {
            if let Some(data) = held.custom_data().cloned() {
                let mut data = data;
                data.remove(&QUILL_SELECTION.into());
                held.data_mut().set_other(
                    "minecraft:custom_data",
                    Some(horizon_world::nbt::Tag::Compound(data)),
                );
            }
        }
        game.native_action_bar(player.uuid, Text::literal("Schematic selection cleared"));
        return true;
    }
    let first = stack
        .custom_data()
        .and_then(|data| match data.get(&QUILL_SELECTION.into()) {
            Some(horizon_world::nbt::Tag::IntArray(first)) => {
                <[i32; 3]>::try_from(first.as_slice()).ok()
            }
            _ => None,
        });
    let Some(first) = first else {
        if let Some(held) = game.held_mut() {
            let mut data = held.custom_data().cloned().unwrap_or_default();
            data.insert(
                QUILL_SELECTION.into(),
                horizon_world::nbt::Tag::IntArray(pos.to_vec()),
            );
            held.data_mut().set_other(
                "minecraft:custom_data",
                Some(horizon_world::nbt::Tag::Compound(data)),
            );
        }
        game.native_action_bar(
            player.uuid,
            Text::literal("Schematic first corner selected"),
        );
        return true;
    };
    let Some((origin, size)) = capture_size(first, pos) else {
        game.native_action_bar(
            player.uuid,
            Text::literal("Schematic selection is invalid or exceeds 1,000,000 blocks"),
        );
        return true;
    };
    let requested = super::super::create_item_filters::structured_name(stack);
    let has_custom_name = stack.custom_name().is_some_and(|name| {
        !name
            .trim_matches(|c: char| c.is_ascii_whitespace())
            .is_empty()
    });
    let label = if !has_custom_name {
        Some("schematic".to_owned())
    } else {
        safe_segment(&requested)
    };
    let Some(label) = label else {
        game.native_action_bar(
            player.uuid,
            Text::literal("Rename the Schematic and Quill in an anvil before exporting"),
        );
        return true;
    };
    let Some(owner) = safe_segment(&player.name) else {
        game.native_action_bar(
            player.uuid,
            Text::literal("Player name cannot be used for export"),
        );
        return true;
    };
    let mut name = format!("create:schematics/{owner}/{label}");
    if game.template_entry(&name).is_some() {
        let base = name.clone();
        let Some(unique) = (2..=10_000).find_map(|suffix| {
            let candidate = format!("{base}_{suffix}");
            game.template_entry(&candidate)
                .is_none()
                .then_some(candidate)
        }) else {
            game.native_action_bar(
                player.uuid,
                Text::literal("No available schematic filename"),
            );
            return true;
        };
        name = unique;
    }
    EXPORTING_QUILL.with(|exporting| exporting.set(true));
    let saved = game.save_structure_area(&name, origin, size, false, &player.name, true, true);
    EXPORTING_QUILL.with(|exporting| exporting.set(false));
    if !saved {
        game.native_action_bar(player.uuid, Text::literal("Schematic export failed"));
        return true;
    }
    let mut schematic = ItemStack::new("create:schematic", 1);
    let mut data = Compound::new();
    data.insert(
        "Template".into(),
        horizon_world::nbt::Tag::String(name.as_str().into()),
    );
    schematic.data_mut().set_other(
        "minecraft:custom_data",
        Some(horizon_world::nbt::Tag::Compound(data)),
    );
    schematic.data_mut().custom_name = Some(horizon_world::nbt::Tag::String(label.as_str().into()));
    game.give_or_drop(schematic);
    if let Some(held) = game.held_mut() {
        if let Some(data) = held.custom_data().cloned() {
            let mut data = data;
            data.remove(&QUILL_SELECTION.into());
            held.data_mut().set_other(
                "minecraft:custom_data",
                Some(horizon_world::nbt::Tag::Compound(data)),
            );
        }
    }
    game.native_action_bar(
        player.uuid,
        Text::literal(format!(
            "Saved schematic {}",
            name.rsplit('/').next().unwrap_or("")
        )),
    );
    true
}

pub(super) fn add_void_as_air(
    game: &Game<'_>,
    origin: [i32; 3],
    size: [i32; 3],
    mut template: Tag,
) -> Tag {
    if !EXPORTING_QUILL.with(Cell::get) {
        return template;
    }
    let Some(_air) = game.pack.assets.registry.default_state("minecraft:air") else {
        return template;
    };
    let Some(void) = game
        .pack
        .assets
        .registry
        .default_state("minecraft:structure_void")
    else {
        return template;
    };
    let Tag::Compound(mut data) = template else {
        return template;
    };
    let Some(Tag::List(palette)) = data.get_mut(&"palette".into()) else {
        return Tag::Compound(data);
    };
    let air_index = palette.iter().position(|entry| {
        matches!(entry.get("id"), Some(Tag::String(id)) if id.to_string_lossy() == "minecraft:air")
    });
    let air_index = air_index.unwrap_or_else(|| {
        let mut state = Compound::new();
        state.insert("id".into(), Tag::String("minecraft:air".into()));
        palette.push(Tag::Compound(state));
        palette.len() - 1
    }) as i32;
    let Some(Tag::List(blocks)) = data.get_mut(&"blocks".into()) else {
        return Tag::Compound(data);
    };
    for y in 0..size[1] {
        for z in 0..size[2] {
            for x in 0..size[0] {
                let pos = [x, y, z];
                let world_pos = [origin[0] + x, origin[1] + y, origin[2] + z];
                if game.world.block(world_pos[0], world_pos[1], world_pos[2]) == void {
                    let mut block = Compound::new();
                    block.insert(
                        "pos".into(),
                        Tag::List(vec![Tag::Int(x), Tag::Int(y), Tag::Int(z)]),
                    );
                    block.insert("state".into(), Tag::Int(air_index));
                    blocks.push(Tag::Compound(block));
                    continue;
                }
                let Some(Tag::Compound(mut block_entity)) = game.block_entity_nbt(world_pos) else {
                    continue;
                };
                for key in ["x", "y", "z", "keepPacked"] {
                    block_entity.remove(&key.into());
                }
                if let Some(Tag::Compound(block)) = blocks.iter_mut().find(|block| {
                    block.get("pos").is_some_and(|value| {
                        matches!(value, Tag::List(coordinates) if coordinates == &vec![Tag::Int(x), Tag::Int(y), Tag::Int(z)])
                    })
                }) {
                    block.insert("nbt".into(), Tag::Compound(block_entity));
                }
            }
        }
    }
    Tag::Compound(data)
}

impl Game<'_> {
    /// Capture the inclusive selection as a compressed vanilla structure NBT file.
    /// The caller chooses a filename and handles any existing-file policy.
    pub(in crate::game) fn capture_schematic(
        &mut self,
        first: [i32; 3],
        second: [i32; 3],
        file: &Path,
    ) -> std::io::Result<PathBuf> {
        let (origin, size) = bounds(first, second).ok_or_else(|| {
            std::io::Error::new(std::io::ErrorKind::InvalidInput, "selection is too large")
        })?;
        let registry = self.pack.assets.registry;
        let air = registry
            .default_state("minecraft:air")
            .ok_or_else(|| std::io::Error::other("air state is missing"))?;
        let void = registry.default_state("minecraft:structure_void");
        let mut blocks = Vec::new();
        for y in 0..size[1] {
            for z in 0..size[2] {
                for x in 0..size[0] {
                    let at = (origin[0] + x, origin[1] + y, origin[2] + z);
                    let state = self.world.block(at.0, at.1, at.2);
                    if state == air {
                        continue;
                    }
                    let nbt = match self.block_entity_nbt([at.0, at.1, at.2]) {
                        Some(Tag::Compound(mut data)) => {
                            for key in ["x", "y", "z", "keepPacked"] {
                                data.remove(&key.into());
                            }
                            Some(Box::new(data))
                        }
                        _ => None,
                    };
                    blocks.push(BlockInfo {
                        pos: [x, y, z],
                        state: if Some(state) == void { air } else { state },
                        nbt,
                    });
                }
            }
        }
        let entities = self.template_entities(origin, size);
        let transforms = self
            .state_transforms()
            .ok_or_else(|| std::io::Error::other("structure block table is missing"))?;
        let tag = save_nbt(
            registry,
            transforms,
            size,
            blocks,
            &entities,
            horizon_core::version::DATA_VERSION,
        );
        let raw = nbt::write_named(
            &NamedTag {
                name: "".into(),
                tag,
            },
            Limits::templates(),
        )
        .map_err(|e| std::io::Error::other(format!("{e:?}")))?;
        let compressed = Compression::Gzip
            .encode(&raw)
            .map_err(|e| std::io::Error::other(format!("{e:?}")))?;
        if let Some(parent) = file.parent() {
            std::fs::create_dir_all(parent)?;
        }
        std::fs::write(file, compressed)?;
        Ok(file.to_path_buf())
    }
}

pub(in crate::game) fn use_item(game: &mut Game<'_>, pos: [i32; 3], stack: &ItemStack) -> bool {
    quill_capture(game, pos, stack)
}

#[cfg(test)]
mod tests {
    use super::{bounds, capture_size, safe_segment};

    #[test]
    fn corners_are_inclusive_and_order_independent() {
        assert_eq!(bounds([7, -2, 4], [5, 1, 4]), Some(([5, -2, 4], [3, 4, 1])));
        assert_eq!(bounds([5, 1, 4], [7, -2, 4]), Some(([5, -2, 4], [3, 4, 1])));
        assert_eq!(bounds([2, 2, 2], [2, 2, 2]), Some(([2, 2, 2], [1, 1, 1])));
        assert_eq!(bounds([i32::MIN, 0, 0], [i32::MAX, 0, 0]), None);
    }

    #[test]
    fn capture_rejects_oversized_volumes_and_unsafe_names() {
        assert!(capture_size([0, 0, 0], [999, 999, 0]).is_some());
        assert_eq!(capture_size([0, 0, 0], [1000, 999, 0]), None);
        assert_eq!(safe_segment("MyBlueprint"), Some("myblueprint".into()));
        assert_eq!(safe_segment("../escape"), None);
        assert_eq!(safe_segment("name.nbt"), None);
        assert_eq!(safe_segment(""), None);
    }
}
