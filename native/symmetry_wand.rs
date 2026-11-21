use horizon_client::first_person::Hand;
use horizon_core::position::BlockPos;
use horizon_world::level::{LevelAccess, flags};
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;
use horizon_world::worldgen::structure::{Mirror, Rotation};

use super::Game;
use super::create_machines::{int, string};
use crate::items::ItemStack;

const ITEM: &str = "create:wand_of_symmetry";
const MIRROR: &str = "create:symmetry_wand";
const ENABLED: &str = "create:symmetry_wand_enable";
const SIMULATE: &str = "create:symmetry_wand_simulate";

pub(super) fn register(types: &mut Vec<String>) {
    types.extend([MIRROR.into(), ENABLED.into(), SIMULATE.into()]);
}

fn position(values: [f64; 3]) -> Tag {
    Tag::List(
        values
            .into_iter()
            .map(|value| Tag::Double(value.to_bits()))
            .collect(),
    )
}

fn mirror_data(kind: &str, origin: [f64; 3], orientation: i32, enabled: bool) -> Tag {
    Tag::Compound(Compound::from([
        ("type".into(), Tag::String(kind.into())),
        ("position".into(), position(origin)),
        ("orientation_index".into(), Tag::Int(orientation)),
        ("enable".into(), Tag::Byte(i8::from(enabled))),
    ]))
}

fn bool_component(game: &Game<'_>, stack: &ItemStack, key: &str) -> bool {
    matches!(game.native_component(stack, key), Ok(Some(Tag::Byte(value))) if *value != 0)
}

fn update_held(
    game: &mut Game<'_>,
    mut stack: ItemStack,
    mirror: Option<Tag>,
    enabled: bool,
) -> bool {
    if let Some(mirror) = mirror
        && game
            .native_set_component(&mut stack, MIRROR, mirror)
            .is_err()
    {
        return false;
    }
    if game
        .native_set_component(&mut stack, ENABLED, Tag::Byte(i8::from(enabled)))
        .is_err()
    {
        return false;
    }
    *game.held_mut() = Some(stack);
    game.guest_inventory_resend |= game.lan_acting.is_some();
    true
}

pub(super) fn activate(
    game: &mut Game<'_>,
    stack: &ItemStack,
    pos: [i32; 3],
    face: [i32; 3],
) -> bool {
    if super::create_symmetry_screen::open(game, stack) {
        return true;
    }
    if stack.item.as_ref() != ITEM || !game.native_authoritative() || game.native_sneaking() {
        return false;
    }
    let existing = match game.native_component(stack, MIRROR) {
        Ok(Some(Tag::Compound(mirror))) => Some(mirror.clone()),
        Ok(None) => None,
        _ => return true,
    };
    if game.hand != Hand::Main {
        if existing.is_none() {
            let _ = update_held(
                game,
                stack.clone(),
                Some(mirror_data("empty", [0.0; 3], 0, true)),
                false,
            );
        }
        return true;
    }
    let Some(player) = game.player.as_ref() else {
        return true;
    };
    let Some(anchor) = (0..3)
        .map(|i| pos[i].checked_add(face[i]))
        .collect::<Option<Vec<_>>>()
    else {
        return true;
    };
    let direction = ((f64::from(player.yaw) / 90.0 + 0.5).floor() as i32).rem_euclid(4);
    let orientation = if direction % 2 == 0 { 0 } else { 1 };
    let kind = existing
        .as_ref()
        .and_then(|data| string(data, "type"))
        .filter(|kind| matches!(kind.as_str(), "plane" | "cross_plane" | "triple_plane"))
        .unwrap_or_else(|| "plane".into());
    let enabled = existing
        .as_ref()
        .and_then(|data| int(data, "enable"))
        .unwrap_or(1)
        != 0;
    let orientation = if kind == "cross_plane" {
        let angle = (player.yaw % 90.0).abs();
        i32::from(angle > 22.0 && angle < 67.0)
    } else if kind == "triple_plane" {
        0
    } else {
        orientation
    };
    let origin = [
        f64::from(anchor[0]),
        f64::from(anchor[1]),
        f64::from(anchor[2]),
    ];
    let _ = update_held(
        game,
        stack.clone(),
        Some(mirror_data(&kind, origin, orientation, enabled)),
        true,
    );
    true
}

pub(super) fn deactivate(game: &mut Game<'_>, stack: &ItemStack) -> bool {
    if super::create_symmetry_screen::open(game, stack) {
        return true;
    }
    if stack.item.as_ref() != ITEM || !game.native_authoritative() || game.native_sneaking() {
        return false;
    }
    let mirror = match game.native_component(stack, MIRROR) {
        Ok(None) => Some(mirror_data("empty", [0.0; 3], 0, true)),
        Ok(Some(_)) => None,
        Err(_) => return true,
    };
    let _ = update_held(game, stack.clone(), mirror, false);
    true
}

fn mirror(game: &Game<'_>, wand: &ItemStack) -> Option<([f64; 3], String, i32)> {
    if !bool_component(game, wand, ENABLED) || bool_component(game, wand, SIMULATE) {
        return None;
    }
    let Tag::Compound(mirror) = game.native_component(wand, MIRROR).ok()?? else {
        return None;
    };
    let kind = string(mirror, "type")?;
    let orientation = int(mirror, "orientation_index")?;
    if !matches!(kind.as_str(), "plane" | "cross_plane" | "triple_plane")
        || !(0..=1).contains(&orientation)
    {
        return None;
    }
    let Tag::List(values) = mirror.get(&"position".into())? else {
        return None;
    };
    let [Tag::Double(x), Tag::Double(y), Tag::Double(z)] = values.as_slice() else {
        return None;
    };
    let at = [*x, *y, *z].map(f64::from_bits);
    at.iter()
        .all(|value| value.is_finite())
        .then_some((at, kind, orientation))
}

// Each sequence is applied right to left in the upstream nested flip calls.
// Diagonal flips rotate the state counterclockwise before mirroring it.
fn targets(
    game: &Game<'_>,
    kind: &str,
    orientation: i32,
    anchor: [f64; 3],
    pos: [i32; 3],
    state: BlockStateId,
) -> Vec<([i32; 3], BlockStateId)> {
    let sequences: &[&[u8]] = match (kind, orientation) {
        ("plane", 0) => &[&[2]],
        ("plane", 1) => &[&[0]],
        ("cross_plane", 0) => &[&[0], &[2], &[2, 0]],
        ("cross_plane", 1) => &[&[3], &[4], &[4, 3]],
        ("triple_plane", _) => &[&[0], &[2], &[2, 0], &[3], &[0, 3], &[2, 3], &[2, 0, 3]],
        _ => return Vec::new(),
    };
    let Some(transforms) = game.state_transforms() else {
        return Vec::new();
    };
    let mut result = Vec::new();
    for sequence in sequences {
        let mut target = pos.map(i64::from);
        let mut transformed = state;
        for &flip in *sequence {
            let dx = (target[0] as f64 - anchor[0]) as i64;
            let dz = (target[2] as f64 - anchor[2]) as i64;
            match flip {
                0 => target[0] -= 2 * dx,
                2 => target[2] -= 2 * dz,
                3 => {
                    target[0] -= dx + dz;
                    target[2] -= dz + dx;
                }
                4 => {
                    target[0] += dz - dx;
                    target[2] += dx - dz;
                }
                _ => unreachable!(),
            }
            if flip >= 3 {
                transformed = transforms.rotate(transformed, Rotation::Counterclockwise90);
            }
            transformed = transforms.mirror(
                transformed,
                if flip == 0 || flip == 3 {
                    Mirror::FrontBack
                } else {
                    Mirror::LeftRight
                },
            );
        }
        let [Ok(x), Ok(y), Ok(z)] = target.map(i32::try_from) else {
            continue;
        };
        let target = [x, y, z];
        if target == pos {
            continue;
        }
        // Java's result map collapses targets on a symmetry axis.
        if let Some(entry) = result
            .iter_mut()
            .find(|entry: &&mut ([i32; 3], BlockStateId)| entry.0 == target)
        {
            entry.1 = transformed;
        } else {
            result.push((target, transformed));
        }
    }
    // Java HashMap uses 16 buckets for these at-most-eight positions. Match
    // its BlockPos hash traversal when a survival inventory runs out mid-group.
    result.sort_by_key(|(pos, _)| {
        let hash = pos[1]
            .wrapping_add(pos[2].wrapping_mul(31))
            .wrapping_mul(31)
            .wrapping_add(pos[0]) as u32;
        (hash ^ (hash >> 16)) & 15
    });
    result
}

fn extra_slot(game: &Game<'_>, item: &str) -> Option<usize> {
    let held = game.held_slot();
    std::iter::once(held)
        .chain(0..game.inventory.len())
        .chain(std::iter::once(super::shield::OFFHAND_SLOT))
        .find(|&slot| {
            game.stack_in(slot).is_some_and(|stack| {
                stack.item.as_ref() == item && stack.count > u32::from(slot == held)
            })
        })
}

pub(super) fn placed(
    game: &mut Game<'_>,
    source_stack: &ItemStack,
    pos: [i32; 3],
    state: BlockStateId,
) {
    if !game.native_authoritative() {
        return;
    }
    for wand_slot in 0..9 {
        let Some(wand) = game
            .stack_in(wand_slot)
            .filter(|stack| stack.item.as_ref() == ITEM)
            .cloned()
        else {
            continue;
        };
        let Some((anchor, kind, orientation)) = mirror(game, &wand) else {
            continue;
        };
        let distance = (0..3)
            .map(|i| (f64::from(pos[i]) - anchor[i]).powi(2))
            .sum::<f64>();
        if distance > 50.0_f64.powi(2) {
            continue;
        }
        for (target, state) in targets(game, &kind, orientation, anchor, pos, state) {
            let Some(slot) = (if game.creative {
                Some(0)
            } else {
                extra_slot(game, &source_stack.item)
            }) else {
                continue;
            };
            let replaceable = game.creative
                || game
                    .res
                    .behaviours()
                    .is_replaceable(game.world.block(target[0], target[1], target[2]));
            if !replaceable
                || !game.with_level(|_, level, _| {
                    level.is_unobstructed(BlockPos::new(target[0], target[1], target[2]), state)
                })
            {
                continue;
            }
            if !game.native_set_block(game.native_dimension(), target, state, flags::UPDATE_ALL) {
                continue;
            }
            if !game.creative {
                if let Some(stack) = game.stack_in_mut(slot) {
                    stack.count -= 1;
                    if stack.count == 0 {
                        *game.stack_in_mut(slot) = None;
                    }
                }
                game.guest_inventory_resend |= game.lan_acting.is_some();
                let mut wand = wand.clone();
                if game
                    .native_set_component(&mut wand, SIMULATE, Tag::Byte(0))
                    .is_ok()
                {
                    *game.stack_in_mut(wand_slot) = Some(wand);
                }
            }
        }
    }
}

/// BreakEvent fires before the original block is removed. Java's plane mirror
/// drops the reflected block's loot at that original position.
pub(super) fn broken(game: &mut Game<'_>, pos: [i32; 3], state: BlockStateId) {
    if !game.native_authoritative() {
        return;
    }
    let original = game.res.facts().get(state).name.clone();
    let Some(air) = game.pack.assets.registry.default_state("minecraft:air") else {
        return;
    };
    for wand_slot in 0..9 {
        let Some(wand) = game
            .stack_in(wand_slot)
            .filter(|s| s.item.as_ref() == ITEM)
            .cloned()
        else {
            continue;
        };
        let Some((anchor, kind, orientation)) = mirror(game, &wand) else {
            continue;
        };
        let distance = (0..3)
            .map(|i| (f64::from(pos[i]) - anchor[i]).powi(2))
            .sum::<f64>();
        if distance > 50.0_f64.powi(2) {
            continue;
        }
        for (target, _) in targets(game, &kind, orientation, anchor, pos, state) {
            let target_state = game.world.block(target[0], target[1], target[2]);
            let facts = game.res.facts().get(target_state).clone();
            if game.res.behaviours().is_air(target_state)
                || (!game.creative && facts.name != original)
            {
                continue;
            }
            if !game.native_set_block(game.native_dimension(), target, air, flags::UPDATE_ALL) {
                continue;
            }
            if !game.creative {
                game.mine_block_with_held(&facts.name, facts.hardness);
                let held = game.held().cloned();
                for drop in game.block_loot_at(pos, target_state, held.as_ref(), None) {
                    if drop.item.as_ref() != "minecraft:air" {
                        game.pop_break_drop(pos, drop);
                    }
                }
                game.guest_inventory_resend |= game.lan_acting.is_some();
            }
        }
    }
}
