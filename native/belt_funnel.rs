use horizon_core::geometry::Direction;
use horizon_world::nbt::Tag;

use crate::containers::ModBlockEntity;
use crate::items::ItemStack;

use super::Game;
use super::create_belt;
use super::create_depot::{DEPOT, receive_stack};
use super::create_fan::facing;
use super::create_item_filters::accepts;
use super::create_machines::{
    CHUTE, PLAIN_CHUTE, insert_chute, int, mod_entity, offset, same_stack,
};
use super::create_threshold_switch::delta;

pub(super) const ANDESITE: &str = "create:andesite_belt_funnel";
pub(super) const BRASS: &str = "create:brass_belt_funnel";
pub(super) const CRATE: &str = "create:creative_crate";
pub(super) const FUNNEL: &str = "create:funnel";
pub(super) const COOLDOWN: i32 = 8;

pub(super) fn power(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    game.native_neighbor_signal(game.native_dimension(), pos) > 0
}

pub(super) fn amount(block: &str, entity: &ModBlockEntity) -> (u32, bool) {
    if matches!(block, ANDESITE | super::create_funnel::ANDESITE) {
        return (1, false);
    }
    let configured = int(&entity.nbt, "FilterAmount").unwrap_or(0);
    let up_to = configured == 0 || int(&entity.nbt, "UpTo") == Some(1);
    (
        if configured <= 0 {
            64
        } else {
            configured as u32
        },
        !up_to,
    )
}

pub(super) fn outlet(game: &Game<'_>, pos: [i32; 3]) -> Option<Direction> {
    let state = game.world.block(pos[0], pos[1], pos[2]);
    if !matches!(game.native_state_block(state),
        Some(ANDESITE | BRASS | super::create_funnel::ANDESITE | super::create_funnel::BRASS))
    {
        return None;
    }
    facing(game, state)
}

fn pulling_destination(
    game: &mut Game<'_>,
    pos: [i32; 3],
    face: Direction,
    stack: &ItemStack,
) -> Option<[i32; 3]> {
    let state = game.world.block(pos[0], pos[1], pos[2]);
    if !matches!(game.native_state_block(state), Some(ANDESITE | BRASS))
        || game.native_block_state_property(state, "shape") != Some("pulling")
        || power(game, pos)
        || !mod_entity(game, pos).is_some_and(|entity| accepts(game.items(), &entity.nbt, stack))
    {
        return None;
    }
    Some(offset(pos, face.opposite().normal()))
}

pub(super) fn can_pull_all(
    game: &mut Game<'_>,
    pos: [i32; 3],
    face: Direction,
    stack: &ItemStack,
) -> bool {
    pulling_destination(game, pos, face, stack)
        .is_some_and(|target| fits(game, target, face, stack, stack.count))
}

pub(super) fn pull(
    game: &mut Game<'_>,
    pos: [i32; 3],
    face: Direction,
    stack: &ItemStack,
) -> Option<ItemStack> {
    let Some(target) = pulling_destination(game, pos, face, stack) else {
        return Some(stack.clone());
    };
    let remainder = insert(game, target, face, stack.clone());
    let accepted = stack.count - remainder.as_ref().map_or(0, |rest| rest.count);
    if accepted > 0 {
        super::create_smart_observer::funnel_transfer(
            game, pos, &ItemStack { count: accepted, ..stack.clone() },
        );
        super::create_funnel_flap::pulled(game, pos);
    }
    remainder
}


pub(super) fn pull_first(
    game: &mut Game<'_>,
    pos: [i32; 3],
    face: Direction,
    items: &mut [Option<ItemStack>],
) -> bool {
    let Some((held, buffered)) = items.split_first_mut() else {
        return false;
    };
    for slot in buffered.iter_mut().chain(std::iter::once(held)) {
        if let Some(stack) = slot {
            let remainder = pull(game, pos, face, stack);
            if remainder.as_ref().map_or(0, |item| item.count) != stack.count {
                *slot = remainder;
                return true;
            }
        }
    }
    false
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    let block = game.native_block(pos);
    let powered = power(game, pos);
    if (game.native_block_property(pos, "powered").as_deref() == Some("true")) != powered {
        game.native_set_block_property_with(
            pos,
            "powered",
            if powered { "true" } else { "false" },
            2,
        );
    }
    if powered {
        entity.nbt.insert("TransferCooldown".into(), Tag::Int(0));
        return;
    }

    let state = game.world.block(pos[0], pos[1], pos[2]);
    let Some(face) = facing(game, state) else {
        return;
    };
    let below = offset(pos, [0, -1, 0]);
    let pushing = game.native_block_state_property(state, "shape") == Some("pushing");
    let belt = create_belt::feed_point(game, below).filter(|(_, _, movement, _)| {
        pushing
            || face == *movement
                && matches!(
                    game.native_block_state_property(state, "shape"),
                    Some("extended" | "retracted")
                )
    });
    let depot = pushing && game.native_block(below) == DEPOT;
    if !depot && belt.is_none() {
        return;
    }
    let cooldown = int(&entity.nbt, "TransferCooldown").unwrap_or(0);
    if cooldown > 0 {
        entity
            .nbt
            .insert("TransferCooldown".into(), Tag::Int(cooldown - 1));
        return;
    }
    if let Some((start, index, movement, speed)) = belt {
        if !create_belt::can_feed(game, start, index, movement, face, speed) {
            return;
        }
    } else if !mod_entity(game, below).is_some_and(|depot| depot.items.iter().all(Option::is_none))
    {
        return;
    }

    let supply = offset(pos, delta(face.opposite()));
    let (limit, exact) = amount(&block, entity);
    let stack = extract(game, supply, face, entity, limit, exact);
    if let Some(stack) = stack {
        let transferred = stack.clone();
        if let Some((start, index, movement, speed)) = belt {
            create_belt::feed(game, start, index, movement, face, speed, stack);
        } else if let Some(remainder) = receive_stack(game, below, stack) {
            let _ = game.native_insert_item(supply, face, remainder);
            return;
        }
        super::create_smart_observer::funnel_transfer(game, pos, &transferred);
        super::create_funnel_flap::pushed(game, pos, entity);
        entity
            .nbt
            .insert("TransferCooldown".into(), Tag::Int(COOLDOWN));
    }
}

pub(super) fn extract(
    game: &mut Game<'_>,
    supply: [i32; 3],
    face: Direction,
    entity: &ModBlockEntity,
    limit: u32,
    exact: bool,
) -> Option<ItemStack> {
    if let Some(stack) =
        super::create_cart_assembler::extract_docked(game, supply, entity, limit, exact)
    {
        return Some(stack);
    }
    let dimension = game.native_dimension();
    if game.native_block(supply) == CRATE {
        super::create_creative_crate::sample(game, supply)
            .filter(|stack| accepts(game.items(), &entity.nbt, stack))
            .and_then(|mut stack| {
                let max = super::create_packager::max_stack(game.items(), &stack);
                stack.count = limit.min(max);
                (!exact || stack.count == limit).then_some(stack)
            })
    } else {
        let slots = game.native_container_slots(dimension, supply, face)?;
        let stocks: Vec<_> = slots
            .into_iter()
            .filter_map(|slot| {
                slot.stack
                    .filter(|stack| slot.can_take && accepts(game.items(), &entity.nbt, stack))
                    .map(|stack| (slot.slot, stack))
            })
            .collect();
        let sample = stocks.iter().map(|(_, stack)| stack).find(|sample| {
            !exact
                || stocks
                    .iter()
                    .filter(|(_, stack)| same_stack(stack, sample))
                    .map(|(_, stack)| stack.count)
                    .sum::<u32>()
                    >= limit
        })?;
        let limit = limit.min(game.native_max_stack_size(&sample.item).unwrap_or(64));
        let mut output = sample.clone();
        output.count = 0;
        for (slot, stack) in stocks.iter().filter(|(_, stack)| same_stack(stack, sample)) {
            let count = stack.count.min(limit - output.count);
            if count == 0 {
                break;
            }
            if let Some(pulled) = game.native_extract_item(dimension, supply, face, *slot, count) {
                output.count += pulled.count;
            }
        }
        (output.count > 0).then_some(output)
    }
}

/// Move a passing stack into the inventory behind a funnel. Opposing funnels
/// stop the belt stack at their entry when there is still something to take.
pub(super) fn take(
    game: &mut Game<'_>,
    chain: &[[i32; 3]],
    direction: Direction,
    movement: Direction,
    old: f32,
    next: f32,
    stack: &mut ItemStack,
) -> Option<f32> {
    let length = chain.len() as i32;
    let positive = movement == direction;
    let candidates = old.floor() as i32;
    let first_segment = candidates.clamp(0, length - 1);
    let mut index = first_segment;
    while (0..length).contains(&index)
        && if positive {
            index as f32 <= next
        } else {
            (index + 1) as f32 >= next
        }
    {
        let pos = offset(chain[index as usize], [0, 1, 0]);
        index += if positive { 1 } else { -1 };
        let block = game.native_block(pos);
        if !matches!(block.as_str(), ANDESITE | BRASS) {
            continue;
        }
        let state = game.world.block(pos[0], pos[1], pos[2]);
        let Some(face) = facing(game, state) else {
            continue;
        };
        let shape = game.native_block_state_property(state, "shape");
        if face == movement || shape == Some("pushing") {
            continue;
        }

        let segment = index - if positive { 1 } else { -1 };
        let mut entry = segment as f32 + 0.5;
        if shape == Some("extended") {
            entry += if positive { -0.499 } else { 0.499 };
        }
        if if positive {
            next <= entry
        } else {
            next >= entry
        } {
            break;
        }
        let blocking = face == movement.opposite();
        if !power(game, pos)
            && let Some(funnel) = mod_entity(game, pos)
            && accepts(game.items(), &funnel.nbt, stack)
        {
            let (limit, exact) = amount(&block, funnel);
            let target = offset(pos, delta(face.opposite()));
            let count = if exact { limit } else { stack.count };
            if count <= stack.count && (!exact || fits(game, target, face, stack, count)) {
                let offered = ItemStack {
                    count,
                    ..stack.clone()
                };
                let remainder = insert(game, target, face, offered);
                let accepted = count - remainder.map_or(0, |rest| rest.count);
                if accepted > 0 {
                    stack.count -= accepted;
                    super::create_smart_observer::funnel_transfer(
                        game,
                        pos,
                        &ItemStack {
                            count: accepted,
                            ..stack.clone()
                        },
                    );
                    super::create_funnel_flap::received(game, pos);
                }
            }
        }
        if blocking || stack.count == 0 {
            return Some(entry);
        }
    }
    None
}

fn insert(game: &mut Game<'_>, target: [i32; 3], face: Direction, stack: ItemStack) -> Option<ItemStack> {
    match game.native_block(target).as_str() {
        DEPOT => receive_stack(game, target, stack),
        CHUTE | PLAIN_CHUTE => insert_chute(game, target, stack),
        _ => game.native_insert_item(target, face, stack),
    }
}

pub(super) fn fits(game: &Game<'_>, pos: [i32; 3], face: Direction, stack: &ItemStack, count: u32) -> bool {
    let max = game.native_max_stack_size(&stack.item).unwrap_or(64);
    let Some(slots) = game.native_container_slots(game.native_dimension(), pos, face) else {
        return false;
    };
    let available: u32 = slots
        .into_iter()
        .filter(|slot| game.block_can_place(pos, slot.slot, stack))
        .map(|slot| match slot.stack {
            None => max,
            Some(current) if current.item == stack.item && current.extra == stack.extra => {
                max.saturating_sub(current.count)
            }
            _ => 0,
        })
        .sum();
    available >= count
}
