use std::collections::HashMap;

use horizon_core::geometry::Direction;
use horizon_core::position::BlockPos;
use horizon_world::level::{PlacementContext, flags};
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;

use crate::containers::{BlockEntity, ModBlockEntity};
use crate::items::ItemStack;
use horizon_assets::item_model::DisplayContext;

use super::create_depot::encode;
use super::create_fan::facing;
use super::create_machines::{int, mod_entity, offset};
use super::native_block_entity_draw::BlockEntityDraw;
use super::{Game, GameLevel, Hand};

pub(super) const LINK: &str = "create:redstone_link";
const FREQUENCIES: [&str; 2] = ["FrequencyFirst", "FrequencyLast"];
const SIGNAL_RANGE: i64 = 256;

fn side_name(face: Direction) -> &'static str {
    match face {
        Direction::Down => "down",
        Direction::Up => "up",
        Direction::North => "north",
        Direction::South => "south",
        Direction::West => "west",
        Direction::East => "east",
    }
}

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    ctx: &PlacementContext,
) -> Option<BlockStateId> {
    if level.native_state_block(state) != Some(LINK) {
        return None;
    }
    level.native_state_with_property(state, "facing", side_name(ctx.face))
}

fn stack(data: &Compound, key: &str) -> Option<ItemStack> {
    let Tag::Compound(item) = data.get(&key.into())? else {
        return None;
    };
    ItemStack::from_nbt(item)
}

#[derive(Clone, Eq, Hash, PartialEq)]
struct Frequency {
    item: String,
    color: i32,
}

fn frequency(data: &Compound, key: &str) -> Option<Frequency> {
    frequency_of(stack(data, key)?)
}

fn frequency_of(item: ItemStack) -> Option<Frequency> {
    let color = match item
        .data()
        .and_then(|data| data.other("minecraft:dyed_color"))
    {
        Some(Tag::Int(rgb)) => *rgb,
        Some(Tag::Compound(data)) => int(data, "rgb").unwrap_or(-1),
        _ => -1,
    };
    Some(Frequency {
        item: item.item.to_string(),
        color,
    })
}

type Channel = [Option<Frequency>; 2];

struct Node {
    pos: [i32; 3],
    channel: Channel,
    receive: bool,
    input: i32,
}

fn input_signal(game: &mut Game<'_>, at: [i32; 3], facing: Direction) -> i32 {
    game.with_level(|behaviors, level, ticks| {
        Direction::ALL
            .into_iter()
            .map(|side| {
                let [x, y, z] = offset(at, side.normal());
                let p = BlockPos::new(x, y, z);
                let power = behaviors.signal_at(level, ticks, p, side);
                if side == facing.opposite() || power == 15 {
                    power
                } else {
                    power.max(behaviors.signal_at(level, ticks, p, Direction::Up))
                }
            })
            .max()
            .unwrap_or(0)
    })
}

pub(super) fn schedule_powered(game: &mut Game<'_>, items: &[Tag]) -> bool {
    let [first, last] = items else {
        return false;
    };
    let channel = [first, last].map(|item| match item {
        Tag::Compound(item) => ItemStack::from_nbt(item).and_then(frequency_of),
        _ => None,
    });
    let ticking = game.block_ticking_area();
    let transmitters: Vec<_> = game
        .world
        .block_entity_tickers()
        .iter()
        .filter_map(|entry| {
            let (x, y, z) = entry.0;
            if !ticking(x, z) {
                return None;
            }
            let pos = [x, y, z];
            let link = mod_entity(game, pos).filter(|entity| entity.id == LINK)?;
            if game.native_block_property(pos, "receiver").as_deref() != Some("false")
                || FREQUENCIES.map(|key| frequency(&link.nbt, key)) != channel
            {
                return None;
            }
            Some((pos, facing(game, game.world.block(x, y, z))?))
        })
        .collect();
    transmitters
        .into_iter()
        .any(|(pos, face)| input_signal(game, pos, face) > 0)
}

fn in_range(a: [i32; 3], b: [i32; 3]) -> bool {
    a.into_iter()
        .zip(b)
        .map(|(x, y)| (i64::from(x) - i64::from(y)).pow(2))
        .sum::<i64>()
        < SIGNAL_RANGE * SIGNAL_RANGE
}

pub(super) fn tick(game: &mut Game<'_>) {
    let ticking = game.block_ticking_area();
    let mut nodes: Vec<_> = game
        .world
        .block_entity_tickers()
        .iter()
        .filter_map(|entry| {
            let (x, y, z) = entry.0;
            let pos = [x, y, z];
            let link = mod_entity(game, pos).filter(|entity| entity.id == LINK)?;
            if !ticking(x, z) {
                return None;
            }
            let receive = game.native_block_property(pos, "receiver").as_deref() == Some("true");
            Some(Node {
                pos,
                receive,
                channel: FREQUENCIES.map(|key| frequency(&link.nbt, key)),
                input: 0,
            })
        })
        .collect();
    let mut channels: HashMap<Channel, Vec<([i32; 3], i32)>> = HashMap::new();
    for node in nodes.iter_mut().filter(|link| !link.receive) {
        let [x, y, z] = node.pos;
        let Some(face) = facing(game, game.world.block(x, y, z)) else {
            continue;
        };
        node.input = input_signal(game, node.pos, face);
        if node.input > 0 {
            channels
                .entry(node.channel.clone())
                .or_default()
                .push((node.pos, node.input));
        }
    }
    for (pos, pair) in super::create_linked_controller::sources(game, true) {
        channels.entry(pair.map(|item| item.and_then(frequency_of))).or_default().push((pos, 15));
    }
    for node in nodes {
        let received = if node.receive {
            channels
                .get(&node.channel)
                .into_iter()
                .flatten()
                .filter(|(source, _)| in_range(node.pos, *source))
                .map(|(_, strength)| *strength)
                .max()
                .unwrap_or(0)
        } else {
            0
        };
        let before = mod_entity(game, node.pos)
            .and_then(|link| int(&link.nbt, "Receive"))
            .unwrap_or(0);
        game.native_with_mod_block_entity(node.pos, |entity| {
            entity.nbt.insert("Receive".into(), Tag::Int(received));
            entity.nbt.insert("Transmit".into(), Tag::Int(node.input));
            entity
                .nbt
                .insert("Transmitter".into(), Tag::Byte(i8::from(!node.receive)));
        });
        let on = node.input > 0 || received > 0;
        let was_on = game.native_block_property(node.pos, "powered").as_deref() == Some("true");
        if node.receive && (received != before || was_on != on) {
            game.native_set_block_property(node.pos, "powered", if on { "true" } else { "false" });
            game.native_update_signal_neighbors(game.native_dimension(), node.pos);
        } else if node.receive {
            game.native_set_block_property(node.pos, "powered", if on { "true" } else { "false" });
        } else {
            game.native_set_block_property_with(
                node.pos,
                "powered",
                if on { "true" } else { "false" },
                flags::UPDATE_CLIENTS,
            );
        }
    }
}

// Controller network updates change the received value immediately; receiver
// block entities publish the state and neighbor updates on their next tick.
pub(super) fn controller_update(game: &mut Game<'_>) {
    let ticking = game.block_ticking_area();
    let links: Vec<_> = game.world.block_entity_tickers().iter().filter_map(|entry| {
        let (x, y, z) = entry.0;
        if !ticking(x, z) { return None; }
        let pos = [x, y, z];
        let entity = mod_entity(game, pos).filter(|entity| entity.id == LINK)?;
        let receive = game.native_block_property(pos, "receiver").as_deref() == Some("true");
        Some((pos, receive, FREQUENCIES.map(|key| frequency(&entity.nbt, key)),
              int(&entity.nbt, "Transmit").unwrap_or(0)))
    }).collect();
    let manual: Vec<_> = super::create_linked_controller::sources(game, false).into_iter()
        .map(|(pos, pair)| (pos, pair.map(|item| item.and_then(frequency_of))))
        .collect();
    for (pos, _, channel, _) in links.iter().filter(|(_, receive, _, _)| *receive) {
        let block_power = links.iter().filter(|(source, receive, key, _)|
            !receive && key == channel && in_range(*pos, *source))
            .map(|(_, _, _, power)| *power).max().unwrap_or(0);
        let manual_power = manual.iter().any(|(source, key)| key == channel && in_range(*pos, *source));
        let received = if manual_power { 15 } else { block_power };
        game.native_with_mod_block_entity(*pos, |entity| {
            entity.nbt.insert("Receive".into(), Tag::Int(received));
        });
    }
}

fn is_receiver(level: &GameLevel<'_>, state: BlockStateId) -> bool {
    level.registry.state(state).is_some_and(|info| {
        info.name == LINK
            && info
                .properties
                .get("receiver")
                .is_some_and(|value| value == "true")
    })
}

pub(super) fn source(level: &GameLevel<'_>, state: BlockStateId, out: &mut bool) {
    *out |= is_receiver(level, state)
        && level
            .registry
            .state(state)
            .and_then(|info| info.properties.get("powered"))
            .is_some_and(|value| value == "true");
}

pub(super) fn signal(
    level: &GameLevel<'_>,
    pos: BlockPos,
    state: BlockStateId,
    face: Direction,
    direct: bool,
    out: &mut i32,
) {
    if !is_receiver(level, state) {
        return;
    }
    if direct
        && level
            .registry
            .state(state)
            .and_then(|info| info.properties.get("facing"))
            .is_none_or(|value| value != side_name(face.opposite()))
    {
        return;
    }
    if let Some(BlockEntity::Mod(entity)) = level.world.block_entities.get(&(pos.x, pos.y, pos.z)) {
        *out = int(&entity.nbt, "Receive").unwrap_or(0);
    }
}

fn slot(face: Direction, first: bool) -> [f64; 3] {
    let part = if first { 10.5 / 16.0 } else { 5.5 / 16.0 };
    let surface = 3.01 / 16.0;
    match face {
        Direction::Up => [0.5, surface, part],
        Direction::Down => [0.5, 1.0 - surface, 1.0 - part],
        Direction::North => [0.5, part, 1.0 - surface],
        Direction::South => [0.5, part, surface],
        Direction::West => [1.0 - surface, part, 0.5],
        Direction::East => [surface, part, 0.5],
    }
}

pub(super) fn click(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    let state = game.world.block(pos[0], pos[1], pos[2]);
    if game.hand != Hand::Main || game.native_state_block(state) != Some(LINK) {
        return false;
    }
    if game.held().is_none() && game.native_sneaking() {
        let receive = game.native_block_property(pos, "receiver").as_deref() != Some("true");
        game.native_set_block_property(pos, "receiver", if receive { "true" } else { "false" });
        game.native_update_signal_neighbors(game.native_dimension(), pos);
        return true;
    }
    let Some(face) = facing(game, state) else {
        return false;
    };
    let Some(hit) = game.native_raycast(6.0) else {
        return false;
    };
    let local = [hit.x, hit.y, hit.z]
        .into_iter()
        .zip(pos)
        .map(|(p, at)| p - f64::from(at))
        .collect::<Vec<_>>();
    let dist = |first| {
        slot(face, first)
            .into_iter()
            .zip(&local)
            .map(|(p, hit)| (p - hit).powi(2))
            .sum::<f64>()
    };
    let a = dist(true);
    let b = dist(false);
    if a.min(b) > 0.20_f64.powi(2) {
        return false;
    }
    let frequency = FREQUENCIES[usize::from(b < a)];
    let sample = game
        .held()
        .cloned()
        .map(|mut stack| {
            stack.count = 1;
            encode(&stack)
        })
        .unwrap_or(Tag::Compound(Compound::new()));
    game.native_with_mod_block_entity(pos, |entity| {
        entity.nbt.insert(frequency.into(), sample);
    });
    game.native_block_entity_sync(pos);
    true
}

pub(super) fn clipboard_frequencies(game: &Game<'_>, pos: [i32; 3]) -> Option<Tag> {
    let entity = mod_entity(game, pos).filter(|entity| entity.id == LINK)?;
    Some(Tag::Compound(
        ["First", "Last"]
            .into_iter()
            .zip(FREQUENCIES)
            .map(|(key, saved)| {
                let value = stack(&entity.nbt, saved).map_or_else(
                    || Tag::Compound(Compound::new()),
                    |mut frequency| {
                        frequency.count = 1;
                        crate::save::item_to_nbt(&frequency)
                    },
                );
                (key.into(), value)
            })
            .collect(),
    ))
}

pub(super) fn paste_clipboard_frequencies(
    game: &mut Game<'_>,
    pos: [i32; 3],
    frequencies: &Compound,
) -> bool {
    let (Some(Tag::Compound(first)), Some(Tag::Compound(last))) = (
        frequencies.get(&"First".into()),
        frequencies.get(&"Last".into()),
    ) else {
        return false;
    };
    if game
        .native_with_mod_block_entity(pos, |entity| {
            for (key, value) in FREQUENCIES.into_iter().zip([first, last]) {
                let tag = ItemStack::from_nbt(value).map_or_else(
                    || Tag::Compound(Compound::new()),
                    |mut frequency| {
                        frequency.count = 1;
                        encode(&frequency)
                    },
                );
                entity.nbt.insert(key.into(), tag);
            }
        })
        .is_none()
    {
        return false;
    }
    game.native_block_entity_sync(pos);
    true
}

pub(super) fn update_tag(entity: &ModBlockEntity) -> Compound {
    FREQUENCIES
        .into_iter()
        .filter_map(|key| {
            entity
                .nbt
                .get(&key.into())
                .cloned()
                .map(|tag| (key.into(), tag))
        })
        .collect()
}

pub(super) fn render(
    game: &Game<'_>,
    state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    let Some(face) = facing(game, state) else {
        return;
    };
    for (index, key) in FREQUENCIES.into_iter().enumerate() {
        let Some(item) = stack(&entity.nbt, key) else {
            continue;
        };
        draw.push();
        draw.translate(slot(face, index == 0).map(|v| v as f32));
        let yaw = match face {
            Direction::West => 90.0,
            Direction::East => 270.0,
            Direction::South => 180.0,
            _ => 0.0,
        };
        let pitch = match face {
            Direction::Up => 90.0,
            Direction::Down => 270.0,
            _ => 0.0,
        };
        draw.rotate_about([0.0, 1.0, 0.0], yaw, [0.0; 3]);
        draw.rotate_about([1.0, 0.0, 0.0], pitch, [0.0; 3]);
        draw.scale([0.30; 3]);
        game.native_draw_item(draw, &item, DisplayContext::Fixed, None, 0);
        draw.pop();
    }
}
