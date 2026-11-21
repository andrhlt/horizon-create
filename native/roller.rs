use horizon_core::geometry::Direction;
use horizon_core::random::RandomSource;
use horizon_world::level::{PlaceContext, flags};
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;

use crate::items::ItemStack;
use horizon_core::{geometry::Vec3, position::BlockPos};

use super::Game;
use super::create_bearing::{cargo_items, deposit, relative};
use super::create_depot::{compound, encode};
use super::create_fan::facing;
use super::create_machines::{float, int, offset, set_float, string};

pub(super) const ROLLER: &str = "create:mechanical_roller";
const FILL_DEPTH: i32 = 12;

#[derive(Clone, Copy, PartialEq, Eq)]
enum Mode {
    Pave,
    Fill,
    Wide,
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Fill {
    Blocked,
    Intact,
    Placed,
}

fn xyz(data: &Compound, key: &str) -> Option<[i32; 3]> {
    let Tag::IntArray(position) = data.get(&key.into())? else {
        return None;
    };
    position.as_slice().try_into().ok()
}

fn store_pos(data: &mut Compound, key: &str, pos: [i32; 3]) {
    data.insert(key.into(), Tag::IntArray(pos.to_vec()));
}

pub(super) fn redirect_placement(game: &mut Game<'_>, context: &mut PlaceContext) {
    if context.item != ROLLER {
        return;
    }
    let clicked = context.clicked_pos;
    let support = [clicked.x, clicked.y - 1, clicked.z];
    let full_top = game.native_block_collision(support).iter().any(|bounds| {
        bounds[4] == 1.0
            && bounds[0] == 0.0
            && bounds[2] == 0.0
            && bounds[3] == 1.0
            && bounds[5] == 1.0
    });
    if !full_top {
        return;
    }
    let target = [clicked.x, clicked.y + 1, clicked.z];
    if !game.with_level(|behaviours, level, _| {
        behaviours.is_replaceable(level.world.block(target[0], target[1], target[2]))
    }) {
        return;
    }
    context.clicked_pos = BlockPos::new(target[0], target[1], target[2]);
    context.hit = Vec3::new(
        f64::from(target[0]) + 0.5,
        f64::from(target[1]) + 1.0,
        f64::from(target[2]) + 0.5,
    );
}

fn find_stock(blocks: &mut [Compound], item: &str, take: bool) -> bool {
    for cargo in blocks {
        let Some((items, _)) = cargo_items(cargo) else {
            continue;
        };
        let found = items.iter().position(|entry| {
            matches!(entry, Tag::Compound(tag)
                if string(tag, "id").as_deref() == Some(item)
                    && int(tag, "count").unwrap_or(0) > 0)
        });
        let Some(index) = found else { continue };
        if take && let Tag::Compound(tag) = &mut items[index] {
            let left = int(tag, "count").unwrap_or(1) - 1;
            if left == 0 {
                items.remove(index);
            } else {
                tag.insert("count".into(), Tag::Int(left));
            }
        }
        return true;
    }
    false
}

fn in_tag(game: &Game<'_>, state: BlockStateId, tag: &str) -> bool {
    let behaviours = game.res.behaviours();
    behaviours
        .tag(tag)
        .is_some_and(|set| set.contains(behaviours.block(state)))
}

fn hardness(game: &Game<'_>, pos: [i32; 3]) -> Option<f32> {
    let state = game.world.block(pos[0], pos[1], pos[2]);
    let facts = game.res.facts().get(state);
    if facts.hardness < 0.0
        || matches!(
            facts.name.as_ref(),
            "create:track" | "minecraft:moving_piston"
        )
        || game.native_block_collision(pos).is_empty()
        || Direction::ALL.into_iter().any(|side| {
            let portal = offset(pos, side.normal());
            in_tag(
                game,
                game.world.block(portal[0], portal[1], portal[2]),
                "minecraft:portals",
            )
        })
    {
        return None;
    }
    Some(facts.hardness)
}

fn clear_column(
    game: &Game<'_>,
    mode: Mode,
    cargo: &mut [Compound],
    at: [i32; 3],
    material: Option<&str>,
) -> Vec<([i32; 3], f32)> {
    if mode != Mode::Pave {
        return Vec::new();
    }
    let has_stock = material.is_some_and(|item| find_stock(cargo, item, false));
    let start = if has_stock { 0 } else { 1 };
    (start..=2)
        .filter_map(|height| {
            let target = offset(at, [0, height, 0]);
            if height == 0 && material.is_some_and(|item| game.native_block(target) == item) {
                return None;
            }
            let hard = hardness(game, target)?;
            Some((target, hard))
        })
        .collect()
}

fn try_fill(
    game: &mut Game<'_>,
    cargo: &mut [Compound],
    at: [i32; 3],
    item: &str,
    state: BlockStateId,
) -> Fill {
    if !game.world.loaded(at[0], at[2]) {
        return Fill::Blocked;
    }
    let existing = game.world.block(at[0], at[1], at[2]);
    if game.native_block(at) == item {
        return Fill::Intact;
    }
    if !game.res.behaviours().is_replaceable(existing)
        && !in_tag(game, existing, "minecraft:leaves")
        && (!game.native_block_collision(at).is_empty()
            || in_tag(game, existing, "minecraft:portals"))
    {
        return Fill::Blocked;
    }
    if !find_stock(cargo, item, false)
        || !game.native_set_block(game.native_dimension(), at, state, flags::UPDATE_ALL)
    {
        return Fill::Blocked;
    }
    find_stock(cargo, item, true);
    Fill::Placed
}

fn pave(
    game: &mut Game<'_>,
    data: &mut Compound,
    mode: Mode,
    first: &mut [Compound],
    last: &mut [Compound],
    at: [i32; 3],
    item: Option<&str>,
) {
    let Some((item, state)) = item.and_then(|item| Some((item, game.native_default_state(item)?)))
    else {
        return;
    };
    for depth in 0..=if mode == Mode::Pave { 0 } else { FILL_DEPTH } {
        let radius = if mode == Mode::Wide {
            (depth + 1) / 2
        } else {
            0
        };
        let mut changed = false;
        let mut any_open = false;
        for x in -radius..=radius {
            for z in -radius..=radius {
                if x.abs() + z.abs() > radius {
                    continue;
                }
                let target = offset(at, [x, -depth, z]);
                let storage = if find_stock(first, item, false) {
                    &mut *first
                } else {
                    &mut *last
                };
                let result = try_fill(game, storage, target, item, state);
                changed |= result == Fill::Placed;
                any_open |= result != Fill::Blocked;
            }
        }
        if changed {
            data.insert("WaitingTicks".into(), Tag::Int(2));
            store_pos(data, "LastPos", at);
            return;
        }
        if !any_open && depth != 0 {
            break;
        }
    }
}

fn visit(
    game: &mut Game<'_>,
    data: &mut Compound,
    mode: Mode,
    first: &mut [Compound],
    last: &mut [Compound],
    at: [i32; 3],
    material: Option<&str>,
) {
    let mut targets = clear_column(game, mode, first, at, material);
    if mode == Mode::Pave && !material.is_some_and(|item| find_stock(first, item, false)) {
        targets = clear_column(game, mode, last, at, material);
    }
    if let Some((hardest, _)) = targets.into_iter().max_by(|a, b| a.1.total_cmp(&b.1)) {
        store_pos(data, "ReferencePos", at);
        store_pos(data, "BreakingPos", hardest);
        return;
    }
    pave(game, data, mode, first, last, at, material);
}

fn destroy(game: &mut Game<'_>, first: &mut [Compound], last: &mut [Compound], at: [i32; 3]) {
    let unsupported = [
        "minecraft:needs_stone_tool",
        "minecraft:needs_iron_tool",
        "minecraft:needs_diamond_tool",
    ]
    .iter()
    .any(|tag| in_tag(game, game.world.block(at[0], at[1], at[2]), tag));
    let drops = game
        .native_machine_destroy_block(at, None, true)
        .unwrap_or_default();
    for stack in drops {
        if unsupported || game.world.random.next_boolean() {
            continue;
        }
        let limit = game
            .items()
            .get(&stack.item)
            .map_or(64, |item| item.max_stack);
        if let Some(rest) = deposit(first, stack, limit).and_then(|rest| deposit(last, rest, limit))
        {
            game.pop_resource(at, rest);
        }
    }
}

pub(super) fn tick(
    game: &mut Game<'_>,
    blocks: &mut [Compound],
    prior: [f64; 3],
    anchor: [f64; 3],
    payload: u32,
) -> bool {
    let motion = std::array::from_fn::<_, 3, _>(|i| anchor[i] - prior[i]);
    let mut stalled = false;
    for index in 0..blocks.len() {
        let (first, remainder) = blocks.split_at_mut(index);
        let (actor, last) = remainder.split_first_mut().unwrap();
        let Some(saved) = compound(actor, "BlockState")
            .filter(|state| string(state, "Name").as_deref() == Some(ROLLER))
        else {
            continue;
        };
        let Some(side) = game
            .state_from_nbt(&Tag::Compound(saved.clone()))
            .and_then(|state| facing(game, state))
        else {
            continue;
        };
        let local = relative(actor);
        let facing = side.normal();
        let current = std::array::from_fn::<_, 3, _>(|i| {
            (anchor[i] + f64::from(local[i]) + 0.5 + 0.45 * f64::from(facing[i])
                - if i == 1 { 2.0 } else { 0.0 })
            .floor() as i32
        });
        let settings = compound(actor, "Entity");
        let material = settings
            .and_then(|data| compound(data, "Filter"))
            .and_then(|item| string(item, "id"));
        let mode = match settings.and_then(|data| int(data, "ScrollValue")) {
            Some(1) => Mode::Fill,
            Some(2) => Mode::Wide,
            _ => Mode::Pave,
        };
        let previous = xyz(actor, "RollerPosition");
        store_pos(actor, "RollerPosition", current);
        let breaking = xyz(actor, "BreakingPos").is_some();
        let waiting = int(actor, "WaitingTicks").is_some();
        if !breaking && !waiting {
            let moving_forward = motion
                .into_iter()
                .zip(facing)
                .map(|(step, sign)| step * f64::from(sign))
                .sum::<f64>()
                > 0.0;
            if !moving_forward
                || previous.is_none()
                || previous == Some(current) && int(actor, "Rolled") == Some(1)
            {
                continue;
            }
            actor.insert("Rolled".into(), Tag::Byte(1));
            let speed = motion.into_iter().map(|v| v * v).sum::<f64>().sqrt();
            let animation = (((speed * 1000.0 + 100.0) as i32) / 100 * 100) as f32;
            set_float(
                actor,
                "BreakSpeed",
                (animation / 500.0 * 1.5).clamp(1.0 / 128.0, 16.0),
            );
            visit(game, actor, mode, first, last, current, material.as_deref());
        }
        if let Some(break_at) = xyz(actor, "BreakingPos") {
            let breaker = -(payload as i32)
                .wrapping_mul(4096)
                .wrapping_add(index as i32 + 1);
            let wait = int(actor, "TicksUntilNextProgress").unwrap_or(0);
            if wait > 0 {
                actor.insert("TicksUntilNextProgress".into(), Tag::Int(wait - 1));
            } else if let Some(hard) = hardness(game, break_at) {
                let speed = float(actor, "BreakSpeed").unwrap_or(1.0 / 128.0);
                let progress = int(actor, "Progress").unwrap_or(0) + ((speed / hard) as i32).max(1);
                if progress < 10 {
                    actor.insert("Progress".into(), Tag::Int(progress));
                    actor.insert(
                        "TicksUntilNextProgress".into(),
                        Tag::Int((hard / speed) as i32),
                    );
                    game.native_set_break_progress(breaker, break_at, progress);
                } else {
                    let reference = xyz(actor, "ReferencePos").unwrap_or(current);
                    let mut positions =
                        clear_column(game, mode, first, reference, material.as_deref());
                    if !material
                        .as_deref()
                        .is_some_and(|item| find_stock(first, item, false))
                    {
                        positions = clear_column(game, mode, last, reference, material.as_deref());
                    }
                    destroy(game, first, last, break_at);
                    for (pos, _) in positions {
                        if pos != break_at {
                            destroy(game, first, last, pos);
                        }
                    }
                    for key in [
                        "BreakingPos",
                        "ReferencePos",
                        "Progress",
                        "TicksUntilNextProgress",
                    ] {
                        actor.remove(&key.into());
                    }
                    game.native_set_break_progress(breaker, break_at, -1);
                    pave(
                        game,
                        actor,
                        mode,
                        first,
                        last,
                        reference,
                        material.as_deref(),
                    );
                }
            } else {
                for key in [
                    "BreakingPos",
                    "ReferencePos",
                    "Progress",
                    "TicksUntilNextProgress",
                ] {
                    actor.remove(&key.into());
                }
                game.native_set_break_progress(breaker, break_at, -1);
            }
        }
        if let Some(wait) = int(actor, "WaitingTicks") {
            if wait > 0 {
                actor.insert("WaitingTicks".into(), Tag::Int(wait - 1));
            } else {
                actor.remove(&"WaitingTicks".into());
                let reference = xyz(actor, "LastPos").unwrap_or(current);
                actor.remove(&"LastPos".into());
                visit(
                    game,
                    actor,
                    mode,
                    first,
                    last,
                    reference,
                    material.as_deref(),
                );
            }
        }
        stalled |= xyz(actor, "BreakingPos").is_some() || int(actor, "WaitingTicks").is_some();
    }
    stalled
}

pub(super) fn set_filter(game: &mut Game<'_>, pos: [i32; 3], stack: &ItemStack) -> bool {
    let Some(mut state) = game.native_default_state(&stack.item) else {
        return false;
    };
    if game.native_block_state_property(state, "type").is_some() {
        state = game.with_level(|_, level, _| {
            level
                .native_state_with_property(state, "type", "double")
                .unwrap_or(state)
        });
    }
    let facts = game.res.facts().get(state);
    if game.native_block(pos) != ROLLER
        || facts.block_entity
        || facts.has_class("StairBlock")
        || !facts.full_collision
    {
        return false;
    }
    let sample = ItemStack {
        count: 1,
        ..stack.clone()
    };
    if game
        .native_with_mod_block_entity(pos, |roller| {
            roller.nbt.insert("Filter".into(), encode(&sample));
        })
        .is_none()
    {
        return false;
    }
    game.native_block_entity_sync(pos);
    game.swing_arm();
    true
}

pub(super) fn set_mode(game: &mut Game<'_>, pos: [i32; 3], mode: i32) {
    if !(0..=2).contains(&mode) {
        return;
    }
    let changed = game.native_with_mod_block_entity(pos, |roller| {
        if roller.id != ROLLER || int(&roller.nbt, "ScrollValue") == Some(mode) {
            return false;
        }
        roller.nbt.insert("ScrollValue".into(), Tag::Int(mode));
        true
    });
    if changed == Some(true) {
        game.native_block_entity_sync(pos);
    }
}
