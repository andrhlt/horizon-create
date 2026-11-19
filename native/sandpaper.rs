use horizon_world::consumable::UseAnimation;
use horizon_world::nbt::Tag;
use horizon_world::player_inventory::EquipmentSlot;

use crate::items::ItemStack;

use super::create_depot::encode;
use super::{Game, Hand};

pub(super) const POLISHING: &str = "create:sand_paper_polishing";
const PAPER: &str = "create:sand_paper";
const RED_PAPER: &str = "create:red_sand_paper";
const ROSE_QUARTZ: &str = "create:rose_quartz";
const POLISHED_QUARTZ: &str = "create:polished_rose_quartz";
const USE_TICKS: i32 = 32;

fn is_paper(stack: &ItemStack) -> bool {
    matches!(stack.item.as_ref(), PAPER | RED_PAPER)
}

pub(super) fn duration(stack: &ItemStack, duration: &mut i32) {
    if is_paper(stack) {
        *duration = USE_TICKS;
    }
}

pub(super) fn animation(stack: &ItemStack, animation: &mut UseAnimation) {
    if is_paper(stack) {
        *animation = UseAnimation::Eat;
    }
}

fn polishing(stack: &ItemStack) -> Option<ItemStack> {
    let Tag::Compound(data) = stack.data()?.other(POLISHING)? else {
        return None;
    };
    ItemStack::from_nbt(data)
}

fn quartz(stack: &ItemStack) -> bool {
    stack.count > 0 && stack.item.as_ref() == ROSE_QUARTZ
}

fn ground(game: &Game<'_>) -> Option<(u32, ItemStack)> {
    let player = game.player.as_ref()?.position;
    let eye = game.eye_position()?;
    let direction = super::view_vector(game.yaw, game.pitch);
    let at = game.native_raycast(4.5).map_or_else(
        || std::array::from_fn(|i| eye[i] + direction[i] * 4.5),
        |hit| [hit.x, hit.y, hit.z],
    );
    game.dropped
        .iter()
        .find(|drop| {
            let location = drop.position.components();
            quartz(&drop.stack)
                && drop.position.distance_squared(player) <= 9.0
                && location
                    .into_iter()
                    .zip(at)
                    .all(|(x, hit)| (x - hit).abs() <= 1.125)
        })
        .map(|drop| (drop.id, drop.stack.clone()))
}

pub(super) fn start(game: &mut Game<'_>, stack: &ItemStack, hand: Hand, canceled: &mut bool) {
    if !is_paper(stack) || *canceled || polishing(stack).is_some() {
        return;
    }
    let other = if hand == Hand::Main {
        Hand::Off
    } else {
        Hand::Main
    };
    let held = game.with_hand(other, |game| {
        game.held().filter(|item| quartz(item)).cloned()
    });
    let (mut input, ground_id) = if let Some(stack) = held {
        (stack, None)
    } else if let Some((id, stack)) = ground(game) {
        (stack, Some(id))
    } else {
        *canceled = true;
        return;
    };
    // The server owns the inventory. The client starts the same hand animation.
    if game.remote.is_some() {
        return;
    }
    if let Some(id) = ground_id {
        let mut leftovers = input.clone();
        leftovers.count -= 1;
        if !game.native_set_item_entity(game.native_dimension(), id, leftovers) {
            *canceled = true;
            return;
        }
    } else {
        game.with_hand(other, |game| {
            if let Some(held) = game.held_mut() {
                held.count -= 1;
                if held.count == 0 {
                    *game.held_mut() = None;
                }
            }
        });
    }
    input.count = 1;
    if let Some(held) = game.held_mut() {
        held.data_mut().set_other(POLISHING, Some(encode(&input)));
    }
    trace(game, "start", 0);
}

pub(super) fn finish(
    game: &mut Game<'_>,
    stack: &ItemStack,
    hand: Hand,
    result: &mut Option<ItemStack>,
) {
    if !is_paper(stack) || !polishing(stack).is_some_and(|item| quartz(&item)) {
        return;
    }
    game.give_or_drop(ItemStack::new(POLISHED_QUARTZ, 1));
    if let Some(held) = game.held_mut() {
        held.data_mut().set_other(POLISHING, None);
    }
    let equipment = if hand == Hand::Main {
        EquipmentSlot::MainHand
    } else {
        EquipmentSlot::OffHand
    };
    game.damage_held_in_slot(1, equipment);
    *result = game.held().cloned();
    trace(game, "finish", USE_TICKS);
}

pub(super) fn release(game: &mut Game<'_>, stack: &ItemStack, remaining: i32, used: &mut bool) {
    if !is_paper(stack) {
        return;
    }
    let Some(input) = polishing(stack) else {
        return;
    };
    trace(game, "before_release", USE_TICKS - remaining);
    if let Some(held) = game.held_mut() {
        held.data_mut().set_other(POLISHING, None);
    }
    game.give_or_drop(input);
    *used = true;
    trace(game, "release", USE_TICKS - remaining + 1);
}

pub(super) fn tick(game: &Game<'_>, stack: &ItemStack, remaining: i32) {
    if is_paper(stack) {
        trace(game, "tick", USE_TICKS - remaining);
    }
}

fn trace(game: &Game<'_>, event: &str, tick: i32) {
    use std::io::Write;
    use std::sync::OnceLock;
    static TRACE: OnceLock<Option<std::path::PathBuf>> = OnceLock::new();
    if game.remote.is_some() {
        return;
    }
    let Some(path) =
        TRACE.get_or_init(|| std::env::var_os("CREATE_TRACE_SANDPAPER").map(Into::into))
    else {
        return;
    };
    let input = if game.hand == Hand::Main {
        game.offhand.as_ref()
    } else {
        game.inventory[game.selected].as_ref()
    };
    let held = game.held();
    let total = |id| {
        game.inventory
            .iter()
            .chain(std::iter::once(&game.offhand))
            .flatten()
            .filter(|stack| stack.item.as_ref() == id)
            .map(|stack| stack.count)
            .sum::<u32>()
    };
    let row = serde_json::json!({
        "event": event,
        "tick": tick,
        "input_in_hand": input.filter(|item| quartz(item)).map_or(0, |item| item.count),
        "raw_quartz": total(ROSE_QUARTZ),
        "polished_quartz": total(POLISHED_QUARTZ),
        "damage": held.map_or(0, |item| item.damage),
        "polishing": held.and_then(polishing).is_some(),
    });
    if let Ok(mut log) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
    {
        let _ = writeln!(log, "{row}");
    }
}
