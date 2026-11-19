use horizon_core::{geometry::Direction, position::BlockPos};
use horizon_world::{
    fluid::{FluidKind, FluidState},
    level::{LevelAccess, PlacementContext, Ticks, flags},
    nbt::{Compound, Tag},
    registry::BlockStateId,
};

use crate::{
    containers::{BlockEntity, ModBlockEntity},
    items::ItemStack,
};
use horizon_client::{block_entity_item::BLOCK_ENTITY_DATA, text::Text};

use super::{Game, GameLevel, create_fluids::name as direction_name, create_packager};

pub(super) const LINK: &str = "create:stock_link";
const LINK_ENTITY: &str = "create:packager_link";
const FREQUENCY: &str = "Freq";
const PLACED_BY: &str = "PlacedBy";

pub(super) fn new_tag() -> Compound {
    Compound::from([
        ("Power".into(), Tag::Int(0)),
        (
            FREQUENCY.into(),
            Tag::IntArray(crate::save::random_uuid().to_vec()),
        ),
    ])
}

fn frequency(tag: &Tag) -> Option<[i32; 4]> {
    let Tag::IntArray(value) = tag else {
        return None;
    };
    value.as_slice().try_into().ok()
}

fn linked_entity(item: &str) -> Option<&'static str> {
    match item {
        LINK => Some(LINK_ENTITY),
        "create:factory_gauge" => Some("create:factory_panel"),
        super::create_redstone_requester::REQUESTER => {
            Some(super::create_redstone_requester::REQUESTER)
        }
        super::create_stock_ticker::TICKER => Some(super::create_stock_ticker::TICKER),
        _ => None,
    }
}

fn stack_frequency(stack: &ItemStack) -> Option<[i32; 4]> {
    let (kind, data) = horizon_client::block_entity_item::data(stack)?;
    if kind != linked_entity(&stack.item)? {
        return None;
    }
    frequency(data.get(FREQUENCY)?)
}

fn message(game: &mut Game<'_>, key: &str) {
    game.send_overlay_message(Text::translate(key, &[]));
}

pub(super) fn placed(game: &mut Game<'_>, at: [i32; 3], stack: &ItemStack) {
    let owner = game.acting_player_uuid();
    let tuned = stack_frequency(stack);
    game.native_with_mod_block_entity(at, |entity| {
        entity
            .nbt
            .insert(PLACED_BY.into(), Tag::IntArray(owner.to_vec()));
        if let Some(freq) = tuned {
            entity
                .nbt
                .insert(FREQUENCY.into(), Tag::IntArray(freq.to_vec()));
        }
    });
    game.native_block_entity_sync(at);
    placed_message(game, stack);
}

pub(super) fn placed_message(game: &mut Game<'_>, stack: &ItemStack) {
    let tuned = stack_frequency(stack);
    if !game.native_sneaking() {
        message(
            game,
            if tuned.is_some() {
                "create.logistically_linked.connected"
            } else {
                "create.logistically_linked.new_network_started"
            },
        );
    }
}

pub(super) fn use_item(game: &mut Game<'_>, hit: Option<[i32; 3]>) -> bool {
    if !game.native_authoritative() {
        return false;
    }
    let Some(kind) = game.held().and_then(|stack| linked_entity(&stack.item)) else {
        return false;
    };
    if let Some(at) = hit {
        if game.native_sneaking()
            || !matches!(
                game.native_block(at).as_str(),
                LINK | super::create_stock_ticker::TICKER
            )
        {
            return false;
        }
        let Some(freq) = super::create_machines::mod_entity(game, at)
            .and_then(|entity| entity.nbt.get(&FREQUENCY.into()))
            .and_then(frequency)
        else {
            return false;
        };
        let data = Compound::from([
            ("id".into(), Tag::String(kind.into())),
            (FREQUENCY.into(), Tag::IntArray(freq.to_vec())),
        ]);
        if let Some(held) = game.held_mut() {
            held.data_mut()
                .set_other(BLOCK_ENTITY_DATA, Some(Tag::Compound(data)));
        }
        game.guest_inventory_resend |= game.lan_acting.is_some();
        message(game, "create.logistically_linked.tuned");
    } else {
        let Some(held) = game.held_mut() else {
            return false;
        };
        if held
            .data()
            .and_then(|data| data.other(BLOCK_ENTITY_DATA))
            .is_none()
        {
            return false;
        }
        held.data_mut().set_other(BLOCK_ENTITY_DATA, None);
        game.guest_inventory_resend |= game.lan_acting.is_some();
        let actor = game.native_acting_id();
        let sound = "minecraft:entity.item_frame.remove_item";
        if game.lan_acting.is_some() {
            game.native_play_sound_to(actor, sound, "block", None, 0.75, 1.0);
        } else if let Some(player) = game.native_player() {
            game.native_play_local_sound(
                sound,
                [player.x.floor(), player.y.floor(), player.z.floor()],
                0.75,
                1.0,
                0,
            );
        }
        message(game, "create.logistically_linked.cleared");
    }
    true
}

pub(super) fn tooltip(stack: &ItemStack, lines: &mut Vec<(Text, u32)>) {
    if stack_frequency(stack).is_some() {
        lines.push((
            Text::translate("create.logistically_linked.tooltip", &[]),
            0xffaa00ff,
        ));
        lines.push((
            Text::translate("create.logistically_linked.tooltip_clear", &[]),
            0xaaaaaaff,
        ));
    }
}

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    context: &PlacementContext,
    fluid: FluidState,
) -> Option<BlockStateId> {
    let mut placed = level.registry.state(state)?.clone();
    if placed.name != LINK {
        return None;
    }
    let outward = if context.replace_clicked {
        context.nearest_looking_direction().opposite()
    } else {
        context.face
    };
    let yaw = (f64::from(context.yaw) / 90.0 + 0.5).floor() as i64 & 3;
    let horizontal = [
        Direction::South,
        Direction::West,
        Direction::North,
        Direction::East,
    ][yaw as usize];
    let (face, facing) = match outward {
        Direction::Up => ("floor", horizontal),
        Direction::Down => ("ceiling", horizontal.opposite()),
        side => ("wall", side),
    };
    placed.properties.insert("face".into(), face.into());
    placed
        .properties
        .insert("facing".into(), direction_name(facing).into());
    let wet = fluid.kind() == FluidKind::Water && fluid.is_source();
    placed
        .properties
        .insert("waterlogged".into(), wet.to_string());
    level.registry.id(&placed)
}

pub(super) fn attachment(level: &GameLevel<'_>, state: BlockStateId) -> Option<Direction> {
    let info = level
        .registry
        .state(state)
        .filter(|info| info.name == LINK)?;
    match info.properties.get("face")?.as_str() {
        "floor" => Some(Direction::Down),
        "ceiling" => Some(Direction::Up),
        _ => {
            let facing = info.properties.get("facing")?;
            Direction::ALL
                .into_iter()
                .find_map(|side| (direction_name(side) == facing).then(|| side.opposite()))
        }
    }
}

fn power(level: &mut GameLevel<'_>, ticks: &mut Ticks, pos: BlockPos, support: Direction) -> i32 {
    Direction::ALL
        .into_iter()
        .filter(|&side| side != support)
        .map(|side| {
            let [x, y, z] = side.normal();
            level
                .behaviours
                .signal_at(level, ticks, pos.offset(x, y, z), side)
        })
        .max()
        .unwrap_or_default()
}

pub(super) fn update_power(
    level: &mut GameLevel<'_>,
    ticks: &mut Ticks,
    pos: BlockPos,
    state: BlockStateId,
) {
    if level.client_side {
        return;
    }
    let Some(support) = attachment(level, state) else {
        return;
    };
    let strength = power(level, ticks, pos, support);
    if let Some(BlockEntity::Mod(entity)) =
        level.world.block_entities.get_mut(&(pos.x, pos.y, pos.z))
        && entity.nbt.get(&"Power".into()) != Some(&Tag::Int(strength))
    {
        entity.nbt.insert("Power".into(), Tag::Int(strength));
        level.world.modified.insert((pos.x >> 4, pos.z >> 4));
    }
    let property = if strength > 0 { "true" } else { "false" };
    if let Some(next) = level.native_state_with_property(state, "powered", property)
        && next != state
    {
        level
            .behaviours
            .set_block(level, ticks, pos, next, flags::UPDATE_CLIENTS);
    }
}

pub(super) fn tick(game: &mut Game<'_>, at: [i32; 3], entity: &mut ModBlockEntity) {
    if !entity.data.is_empty() {
        return;
    }
    entity.data.push(1);
    if !entity.nbt.contains_key(&FREQUENCY.into()) {
        entity.nbt.insert(
            FREQUENCY.into(),
            Tag::IntArray(crate::save::random_uuid().to_vec()),
        );
    }
    game.with_level(|_, level, ticks| {
        let pos = BlockPos::new(at[0], at[1], at[2]);
        let Some(support) = attachment(level, level.block_state(pos)) else {
            return;
        };
        let strength = power(level, ticks, pos, support);
        entity.nbt.insert("Power".into(), Tag::Int(strength));
        if strength < 15 {
            let [x, y, z] = support.normal();
            create_packager::refresh_link(level, ticks, pos.offset(x, y, z));
        }
    });
}
