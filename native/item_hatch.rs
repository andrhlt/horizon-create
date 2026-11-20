use horizon_core::{geometry::Direction, position::BlockPos};
use horizon_world::{
    fluid::{FluidKind, FluidState},
    level::{PlacementContext, Ticks, flags},
    nbt::{Compound, Tag},
    registry::BlockStateId,
};

use crate::{items::ItemStack, save::item_to_nbt};

use super::create_depot::compound;
use super::create_fan::facing;
use super::create_fluids::name as direction_name;
use super::create_item_filters::accepts;
use super::create_machines::{mod_entity, offset};
use super::{Game, GameLevel};

pub(super) const HATCH: &str = "create:item_hatch";
const OPEN_TIME: i32 = 10;

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    context: &PlacementContext,
    fluid: FluidState,
) -> Option<Option<BlockStateId>> {
    if level.native_state_block(state) != Some(HATCH) {
        return None;
    }
    if matches!(context.face, Direction::Up | Direction::Down) {
        return Some(None);
    }
    let wet = fluid.kind() == FluidKind::Water && fluid.is_source();
    Some(
        level
            .native_state_with_property(state, "facing", direction_name(context.face.opposite()))
            .and_then(|state| {
                level.native_state_with_property(
                    state,
                    "waterlogged",
                    if wet { "true" } else { "false" },
                )
            }),
    )
}

pub(super) fn tick(
    level: &mut GameLevel<'_>,
    ticks: &mut Ticks,
    at: BlockPos,
    state: BlockStateId,
) {
    if level.native_state_block(state) == Some(HATCH) {
        level.native_set_block_property(
            ticks,
            [at.x, at.y, at.z],
            "open",
            "false",
            flags::UPDATE_ALL,
        );
    }
}

fn filter_hit(at: [i32; 3], direction: Direction, hit: [f64; 3]) -> bool {
    let normal = direction.normal();
    let center = [
        f64::from(at[0]) + 0.5 + f64::from(normal[0]) * 0.09375,
        f64::from(at[1]) + 5.15 / 16.0 - 0.125,
        f64::from(at[2]) + 0.5 + f64::from(normal[2]) * 0.09375,
    ];
    center
        .into_iter()
        .zip(hit)
        .map(|(a, b)| (a - b).powi(2))
        .sum::<f64>()
        < (0.5_f64 * 0.965 / 2.0).powi(2)
}

fn physical_filter(stack: &ItemStack) -> bool {
    matches!(
        stack.item.as_ref(),
        "create:filter" | "create:attribute_filter" | "create:package_filter"
    )
}

fn write_filter(game: &mut Game<'_>, at: [i32; 3]) {
    let mut stack = game.held().cloned();
    if stack.as_ref().is_some_and(|stack| {
        matches!(
            stack.item.as_ref(),
            "create:wrench" | "create:mechanical_arm"
        )
    }) {
        return;
    }
    let Some(entity) = mod_entity(game, at) else {
        return;
    };
    let previous = compound(&entity.nbt, "Filter").and_then(ItemStack::from_nbt);
    if let Some(previous) = previous.filter(physical_filter)
        && (!game.creative
            || !game
                .inventory
                .iter()
                .flatten()
                .any(|stack| stack.same_item_same_components(&previous)))
    {
        game.give_or_drop(previous);
        game.guest_inventory_resend |= game.lan_acting.is_some();
    }
    let consume = stack.as_ref().is_some_and(physical_filter);
    if consume && let Some(stack) = &mut stack {
        stack.count = 1;
    }
    let filter = stack
        .as_ref()
        .map_or_else(|| Tag::Compound(Compound::new()), item_to_nbt);
    game.native_with_mod_block_entity(at, |entity| {
        entity.nbt.insert("Filter".into(), filter);
    });
    if consume && !game.creative {
        game.consume_held();
        game.guest_inventory_resend |= game.lan_acting.is_some();
    }
    game.native_block_entity_sync(at);
    game.swing_arm();
    let center = at.map(|coord| f64::from(coord) + 0.5);
    game.native_play_sound_in_place("minecraft:entity.item_frame.add_item", center, 4, 0.25, 0.1);
}

pub(super) fn click(game: &mut Game<'_>, at: [i32; 3], hit: [f64; 3]) -> bool {
    if game.native_block(at) != HATCH || !game.native_authoritative() {
        return false;
    }
    // The main hand consumes the Java Hatch interaction. Horizon can also
    // forward the off-hand packet for this click before it sees that result.
    if game.hand != horizon_client::first_person::Hand::Main {
        return true;
    }
    let state = game.world.block(at[0], at[1], at[2]);
    let Some(direction) = facing(game, state) else {
        return false;
    };
    let sneaking = game.native_sneaking();
    if sneaking
        && game
            .held()
            .is_some_and(|stack| stack.item.as_ref() == "create:wrench")
    {
        return false;
    }
    if !sneaking && filter_hit(at, direction, hit) {
        write_filter(game, at);
        return true;
    }

    let storage = offset(at, direction.normal());
    let Some(filter) = mod_entity(game, at).map(|entity| entity.nbt.clone()) else {
        return true;
    };
    let slots = if sneaking {
        9..36
    } else {
        game.selected..game.selected + 1
    };
    let mut inserted = false;
    for slot in slots {
        let Some(stack) = game.stack_in(slot).cloned() else {
            continue;
        };
        let package = game
            .items()
            .item_tags
            .get("create:packages")
            .is_some_and(|tag| tag.contains(stack.item.as_ref()));
        if !(horizon_client::bundle::fits_inside_container_items(game.items(), &stack) || package)
            || !accepts(game.items(), &filter, &stack)
        {
            continue;
        }
        let before = stack.count;
        let rest = game.native_insert_item_unsided(storage, stack);
        if rest.as_ref().is_some_and(|left| left.count == before) {
            continue;
        }
        *game.stack_in_mut(slot) = rest;
        inserted = true;
    }
    if inserted {
        game.guest_inventory_resend |= game.lan_acting.is_some();
        game.native_set_block_property_with(at, "open", "true", flags::UPDATE_ALL);
        game.with_level(|_, level, ticks| {
            level.native_schedule_block_tick(ticks, at, HATCH, OPEN_TIME)
        });
        let center = at.map(|coord| f64::from(coord) + 0.5);
        game.native_play_sound_in_place("create:item_hatch", center, 4, 0.25, 1.4);
        game.native_play_sound_in_place("create:item_hatch_compounded_1", center, 4, 0.75, 1.15);
        if let Some(actor) = game.native_acting_player() {
            let key = if sneaking {
                "create.item_hatch.deposit_inventory"
            } else {
                "create.item_hatch.deposit_item"
            };
            game.native_action_bar(actor.uuid, horizon_client::text::Text::translate(key, &[]));
        }
    }
    game.swing_arm();
    true
}
