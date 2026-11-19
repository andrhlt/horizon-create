use horizon_core::position::BlockPos;
use horizon_world::{
    fluid::{FluidKind, FluidState},
    level::{PlacementContext, flags},
    registry::BlockStateId,
};

use crate::containers::{BlockEntity, ModBlockEntity};

use super::{Game, GameLevel};

pub(super) const ENTITY: &str = "create:package_postbox";

pub(super) fn block(name: &str) -> bool {
    name.strip_prefix("create:")
        .and_then(|name| name.strip_suffix("_postbox"))
        .is_some_and(|color| {
            matches!(
                color,
                "white"
                    | "orange"
                    | "magenta"
                    | "light_blue"
                    | "yellow"
                    | "lime"
                    | "pink"
                    | "gray"
                    | "light_gray"
                    | "cyan"
                    | "purple"
                    | "blue"
                    | "brown"
                    | "green"
                    | "red"
                    | "black"
            )
        })
}

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    ctx: &PlacementContext,
    fluid: FluidState,
) -> Option<BlockStateId> {
    if !level.native_state_block(state).is_some_and(block) {
        return None;
    }
    let facing = ((f64::from(ctx.yaw) / 90.0 + 0.5).floor() as i32).rem_euclid(4);
    let state = level.native_state_with_property(
        state,
        "facing",
        ["north", "east", "south", "west"][facing as usize],
    )?;
    level.native_state_with_property(
        state,
        "waterlogged",
        if fluid.kind() == FluidKind::Water && fluid.is_source() {
            "true"
        } else {
            "false"
        },
    )
}

pub(super) fn viewers(game: &mut Game<'_>, at: [i32; 3], viewers: u32) {
    if !block(&game.native_block(at)) {
        return;
    }
    let open = if viewers == 0 { "false" } else { "true" };
    if game.native_block_property(at, "open").as_deref() == Some(open) {
        return;
    }
    if game.native_set_block_property_with(at, "open", open, flags::UPDATE_ALL) {
        let sound = if viewers == 0 {
            "minecraft:block.barrel.close"
        } else {
            "minecraft:block.barrel.open"
        };
        game.native_play_sound_in_place(sound, at.map(|coord| f64::from(coord) + 0.5), 4, 1.0, 1.0);
    }
}

pub(super) fn output(level: &GameLevel<'_>, pos: BlockPos, state: BlockStateId, out: &mut i32) {
    if level.native_state_block(state).is_some_and(block)
        && let Some(BlockEntity::Mod(entity)) =
            level.world.block_entities.get(&(pos.x, pos.y, pos.z))
    {
        *out = signal(entity);
    }
}

fn signal(entity: &ModBlockEntity) -> i32 {
    let slots = super::create_chain_conveyor_packages::PORT_SLOTS;
    let used = entity
        .items
        .iter()
        .take(slots)
        .flatten()
        .filter(|stack| stack.count > 0)
        .count();
    if used == 0 {
        0
    } else {
        1 + (14 * used / slots) as i32
    }
}

pub(super) fn inventory_tick(game: &mut Game<'_>, at: [i32; 3]) {
    let Some(entity) =
        super::create_machines::mod_entity(game, at).filter(|entity| entity.id == ENTITY)
    else {
        return;
    };
    let output = signal(entity);
    if entity.data.first().copied().unwrap_or(0) == output {
        return;
    }
    game.native_with_mod_block_entity(at, |entity| {
        if let Some(previous) = entity.data.first_mut() {
            *previous = output;
        } else {
            entity.data.push(output);
        }
    });
    game.native_update_output_neighbors(game.native_dimension(), at);
}

// Java's Postbox targeting selection belongs to the player until a Postbox is placed.
thread_local! {
    static STATION_TARGETS: std::cell::RefCell<std::collections::HashMap<([i32; 4], String), [i32; 3]>> =
        std::cell::RefCell::new(std::collections::HashMap::new());
}

pub(super) fn select_station(game: &mut Game<'_>, station: [i32; 3]) -> bool {
    if game.hand != super::Hand::Main
        || !game.held().is_some_and(|stack| block(stack.item.as_ref()))
        || game.native_block(station) != super::create_station::STATION
    {
        return false;
    }
    if game.native_authoritative() {
        let key = (
            game.acting_player_uuid(),
            game.native_dimension().to_owned(),
        );
        STATION_TARGETS.with_borrow_mut(|targets| {
            targets.insert(key, station);
        });
    }
    true
}

pub(super) fn placed(game: &mut Game<'_>, pos: [i32; 3], stack: &crate::items::ItemStack) {
    if !game.native_authoritative()
        || !block(stack.item.as_ref())
        || !block(&game.native_block(pos))
    {
        return;
    }
    let key = (
        game.acting_player_uuid(),
        game.native_dimension().to_owned(),
    );
    let Some(station) = STATION_TARGETS.with_borrow_mut(|targets| targets.remove(&key)) else {
        return;
    };
    let delta: [i32; 3] = std::array::from_fn(|axis| station[axis] - pos[axis]);
    let distance_squared = f64::from(delta[0]).powi(2)
        + (f64::from(delta[1]) + 0.5).powi(2)
        + f64::from(delta[2]).powi(2);
    if distance_squared > 25.0 {
        return;
    }
    let target = horizon_world::nbt::Tag::compound([
        (
            "type",
            horizon_world::nbt::Tag::String("create:train_station".into()),
        ),
        (
            "relative_pos",
            horizon_world::nbt::Tag::IntArray(delta.to_vec()),
        ),
    ]);
    game.native_with_mod_block_entity(pos, |entity| {
        entity.nbt.insert("Target".into(), target);
    });
    game.native_block_entity_sync(pos);
    // The open-screen packet is sent during the placement action, before the
    // usual block broadcast. The client needs the placed block to identify
    // which native screen to open.
    if let Some(player) = game.lan_acting_uuid {
        let state = game.world.block(pos[0], pos[1], pos[2]).0 as i32;
        game.native_send(
            player,
            horizon_protocol::packets::play::Clientbound::BlockUpdate(
                horizon_protocol::packets::play::BlockUpdate { pos, state },
            ),
        );
    }
    game.open_menu(pos);
}
