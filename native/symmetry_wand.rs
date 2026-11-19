use horizon_client::first_person::Hand;
use horizon_core::position::BlockPos;
use horizon_world::level::{LevelAccess, flags};
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;
use horizon_world::worldgen::structure::Mirror;

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
    let enabled = match &existing {
        Some(data) if string(data, "type").as_deref() == Some("plane") => {
            int(data, "enable").unwrap_or(1) != 0
        }
        Some(data) if string(data, "type").as_deref() != Some("empty") => return true,
        _ => true,
    };
    let origin = [
        f64::from(anchor[0]),
        f64::from(anchor[1]),
        f64::from(anchor[2]),
    ];
    let _ = update_held(
        game,
        stack.clone(),
        Some(mirror_data("plane", origin, orientation, enabled)),
        true,
    );
    true
}

pub(super) fn deactivate(game: &mut Game<'_>, stack: &ItemStack) -> bool {
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

fn plane(game: &Game<'_>, wand: &ItemStack) -> Option<([f64; 3], usize)> {
    if !bool_component(game, wand, ENABLED) || bool_component(game, wand, SIMULATE) {
        return None;
    }
    let Tag::Compound(mirror) = game.native_component(wand, MIRROR).ok()?? else {
        return None;
    };
    if string(mirror, "type").as_deref() != Some("plane") {
        return None;
    }
    let axis = match int(mirror, "orientation_index")? {
        0 => 2,
        1 => 0,
        _ => return None,
    };
    let Tag::List(values) = mirror.get(&"position".into())? else {
        return None;
    };
    let [Tag::Double(x), Tag::Double(y), Tag::Double(z)] = values.as_slice() else {
        return None;
    };
    let at = [*x, *y, *z].map(f64::from_bits);
    at.iter()
        .all(|value| value.is_finite())
        .then_some((at, axis))
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
        let Some((anchor, axis)) = plane(game, &wand) else {
            continue;
        };
        let distance = (0..3)
            .map(|i| (f64::from(pos[i]) - anchor[i]).powi(2))
            .sum::<f64>();
        if distance > 50.0_f64.powi(2) {
            continue;
        }
        // Java casts the offset to an integer before reflection.
        let reflected = i64::from(pos[axis]) - 2 * ((f64::from(pos[axis]) - anchor[axis]) as i64);
        let Ok(reflected) = i32::try_from(reflected) else {
            continue;
        };
        let mut target = pos;
        target[axis] = reflected;
        if target == pos {
            continue;
        }
        let Some(slot) = (if game.creative {
            Some(0)
        } else {
            extra_slot(game, &source_stack.item)
        }) else {
            continue;
        };
        let mirror = if axis == 0 {
            Mirror::FrontBack
        } else {
            Mirror::LeftRight
        };
        let Some(transforms) = game.state_transforms() else {
            continue;
        };
        let state = transforms.mirror(state, mirror);
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
            let mut wand = wand;
            if game
                .native_set_component(&mut wand, SIMULATE, Tag::Byte(0))
                .is_ok()
            {
                *game.stack_in_mut(wand_slot) = Some(wand);
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
        let Some((anchor, axis)) = plane(game, &wand) else {
            continue;
        };
        let distance = (0..3)
            .map(|i| (f64::from(pos[i]) - anchor[i]).powi(2))
            .sum::<f64>();
        if distance > 50.0_f64.powi(2) {
            continue;
        }
        let reflected = i64::from(pos[axis]) - 2 * ((f64::from(pos[axis]) - anchor[axis]) as i64);
        let Ok(reflected) = i32::try_from(reflected) else {
            continue;
        };
        let mut target = pos;
        target[axis] = reflected;
        if target == pos {
            continue;
        }
        let target_state = game.world.block(target[0], target[1], target[2]);
        let facts = game.res.facts().get(target_state).clone();
        if game.res.behaviours().is_air(target_state) || (!game.creative && facts.name != original)
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
