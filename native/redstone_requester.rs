use horizon_core::position::BlockPos;
use horizon_world::{
    level::{LevelAccess, PlacementContext, Ticks, flags},
    nbt::{Compound, Tag},
    registry::BlockStateId,
};

use super::{GameLevel, create_machines::int, create_packager, create_stock_network};
use crate::containers::BlockEntity;

pub(super) const REQUESTER: &str = "create:redstone_requester";

pub(super) fn new_tag() -> Compound {
    Compound::from([
        (
            "Freq".into(),
            Tag::IntArray(crate::save::random_uuid().to_vec()),
        ),
        ("Powered".into(), Tag::Byte(0)),
        ("Success".into(), Tag::Byte(0)),
        ("AllowPartial".into(), Tag::Byte(0)),
        ("EncodedAddress".into(), Tag::String("".into())),
    ])
}

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    context: &PlacementContext,
) -> Option<BlockStateId> {
    if level.native_state_block(state) != Some(REQUESTER) {
        return None;
    }
    let yaw = (f64::from(context.yaw) / 90.0 + 0.5).floor() as i32;
    level.native_state_with_property(state, "axis", if yaw & 1 == 1 { "x" } else { "z" })
}

pub(super) fn neighbor(
    level: &mut GameLevel<'_>,
    ticks: &mut Ticks,
    pos: BlockPos,
    state: BlockStateId,
) {
    if level.client_side {
        return;
    }
    let powered = level.behaviours.has_neighbor_signal(level, ticks, pos);
    let property = if powered { "true" } else { "false" };
    if let Some(next) = level.native_state_with_property(state, "powered", property)
        && next != state
    {
        level
            .behaviours
            .set_block(level, ticks, pos, next, flags::UPDATE_CLIENTS);
    }
    let key = (pos.x, pos.y, pos.z);
    let Some(BlockEntity::Mod(entity)) = level.world.block_entities.get(&key) else {
        return;
    };
    let data = entity.nbt.clone();
    if powered == (int(&data, "Powered").unwrap_or(0) != 0) {
        return;
    }
    if let Some(BlockEntity::Mod(entity)) = level.world.block_entities.get_mut(&key) {
        entity
            .nbt
            .insert("Powered".into(), Tag::Byte(i8::from(powered)));
        entity.nbt.insert("Success".into(), Tag::Byte(0));
    }
    if powered
        && send(level, ticks, &data)
        && let Some(BlockEntity::Mod(entity)) = level.world.block_entities.get_mut(&key)
    {
        entity.nbt.insert("Success".into(), Tag::Byte(1));
    }
    if let Some(log) = level.world.block_log.as_mut() {
        log.push(key);
    }
    create_packager::notify(level, ticks, pos);
}

fn send(level: &mut GameLevel<'_>, ticks: &mut Ticks, data: &Compound) -> bool {
    let Some(Tag::IntArray(frequency)) = data.get(&"Freq".into()) else {
        return false;
    };
    let Some(order) = data.get(&"EncodedRequest".into()) else {
        return false;
    };
    let address = crate::save::text(data.get(&"EncodedAddress".into())).unwrap_or_default();
    let partial = int(data, "AllowPartial").unwrap_or(0) != 0;
    create_stock_network::request(
        level,
        ticks,
        frequency,
        order,
        &address,
        create_stock_network::Request::Redstone {
            allow_partial: partial,
        },
    )
}

pub(super) fn output(level: &GameLevel<'_>, pos: BlockPos, state: BlockStateId, output: &mut i32) {
    if level.native_state_block(state) == Some(REQUESTER)
        && let Some(BlockEntity::Mod(entity)) =
            level.world.block_entities.get(&(pos.x, pos.y, pos.z))
    {
        *output = if int(&entity.nbt, "Success").unwrap_or(0) != 0 {
            15
        } else {
            0
        };
    }
}
