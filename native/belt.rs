use horizon_assets::item_model::DisplayContext;
use horizon_core::geometry::Direction;
use horizon_world::level::flags;
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;

use crate::containers::ModBlockEntity;
use crate::items::ItemStack;

use super::Game;
use super::create_assembly::{self, Action as AssemblyAction};
use super::create_belt_funnel;
use super::create_brass_tunnel::{self, Arrival};
use super::create_depot::{DEPOT, compound, encode, receive_stack};
use super::create_fan::{self, FAN_TIME, Kind};
use super::create_machines::{
    SHAFT, axis_index, collect_landed_items, float, int, mod_entity, offset, reading, set_float,
};
use super::create_spout::{self, Action as SpoutAction};
use super::create_threshold_switch::delta;
use super::create_visuals::{draw_rotating, wheel_angle};
use super::native_block_entity_draw::BlockEntityDraw;

pub(super) const BELT: &str = "create:belt";
const CONNECTOR: &str = "create:belt_connector";
const FIRST_SHAFT: &str = "CreateBeltFirstShaft";
const MAX_LENGTH: i32 = 20;
const PULLEY: &str = "create:block/belt_pulley";

#[derive(Clone, Copy, PartialEq, Eq)]
pub(super) enum Part {
    Start,
    Middle,
    Pulley,
    End,
}

pub(super) fn segment(game: &Game<'_>, pos: [i32; 3]) -> Option<(Direction, Part)> {
    let state = game.world.block(pos[0], pos[1], pos[2]);
    if game.native_state_block(state) != Some(BELT)
        || !matches!(
            game.native_block_state_property(state, "slope"),
            Some("horizontal" | "upward" | "downward")
        )
    {
        return None;
    }
    let direction = match game.native_block_state_property(state, "facing")? {
        "east" => Direction::East,
        "west" => Direction::West,
        "south" => Direction::South,
        "north" => Direction::North,
        _ => return None,
    };
    let part = match game.native_block_state_property(state, "part")? {
        "start" => Part::Start,
        "middle" => Part::Middle,
        "pulley" => Part::Pulley,
        "end" => Part::End,
        _ => return None,
    };
    Some((direction, part))
}

pub(super) fn rise(game: &Game<'_>, pos: [i32; 3]) -> i32 {
    match game.native_block_property(pos, "slope").as_deref() {
        Some("upward") => 1,
        Some("downward") => -1,
        _ => 0,
    }
}

pub(super) fn step(direction: Direction, rise: i32) -> [i32; 3] {
    let [x, _, z] = delta(direction);
    [x, rise, z]
}

pub(super) fn pulley_axis(direction: Direction) -> usize {
    if matches!(direction, Direction::East | Direction::West) {
        2
    } else {
        0
    }
}

fn belt_speed(direction: Direction, rpm: f32) -> f32 {
    let sign = if matches!(direction, Direction::West | Direction::South) {
        1.0
    } else {
        -1.0
    };
    rpm / 480.0 * sign
}

fn shaft(game: &Game<'_>, pos: [i32; 3]) -> Option<usize> {
    if game.native_block(pos) != SHAFT {
        return None;
    }
    axis_index(&game.native_block_property(pos, "axis")?)
}

fn selected(stack: &ItemStack) -> Option<[i32; 3]> {
    let Tag::IntArray(pos) = stack.custom_data()?.get(&FIRST_SHAFT.into())? else {
        return None;
    };
    pos.as_slice().try_into().ok()
}

fn select(game: &mut Game<'_>, pos: Option<[i32; 3]>) {
    if let Some(held) = game.held_mut().as_mut() {
        let mut data = held.custom_data().cloned().unwrap_or_default();
        if let Some(pos) = pos {
            data.insert(FIRST_SHAFT.into(), Tag::IntArray(pos.to_vec()));
        } else {
            data.remove(&FIRST_SHAFT.into());
        }
        let stored = (!data.is_empty()).then_some(Tag::Compound(data));
        held.data_mut().set_other("minecraft:custom_data", stored);
    }
}

pub(super) fn use_connector(game: &mut Game<'_>, pos: [i32; 3], stack: &ItemStack) -> bool {
    if stack.item.as_ref() != CONNECTOR {
        return false;
    }
    let Some(axis) = shaft(game, pos) else {
        return false;
    };
    let Some(first) = selected(stack).filter(|first| shaft(game, *first).is_some()) else {
        select(game, Some(pos));
        return true;
    };
    if first == pos {
        select(game, None);
        return true;
    }
    let diff: [i32; 3] = std::array::from_fn(|i| pos[i] - first[i]);
    let length = diff[0].abs() + diff[2].abs();
    if axis == 1
        || shaft(game, first) != Some(axis)
        || diff[axis] != 0
        || diff[1] != 0 && diff[1].abs() != length
        || !(1..MAX_LENGTH).contains(&length)
    {
        return true;
    }
    let normal = diff.map(i32::signum);
    let facing = match [normal[0], 0, normal[2]] {
        [1, 0, 0] => "east",
        [-1, 0, 0] => "west",
        [0, 0, 1] => "south",
        _ => "north",
    };
    let slope = match normal[1] {
        1 => "upward",
        -1 => "downward",
        _ => "horizontal",
    };
    let speed = |at| {
        mod_entity(game, at)
            .and_then(|entity| float(&entity.nbt, "Speed"))
            .unwrap_or(0.0)
    };
    let a = speed(first);
    let b = speed(pos);
    if a != 0.0 && b != 0.0 && a.signum() != b.signum() {
        return true;
    }
    let mut placements = Vec::new();
    for i in 0..=length {
        let at = offset(first, normal.map(|n| n * i));
        let block = game.native_block(at);
        let is_shaft = shaft(game, at) == Some(axis);
        if !is_shaft && !matches!(block.as_str(), "minecraft:air" | "minecraft:water") {
            return true;
        }
        let part = if i == 0 {
            "start"
        } else if i == length {
            "end"
        } else if is_shaft {
            "pulley"
        } else {
            "middle"
        };
        let Some(state) = game.with_level(|_, level, _| {
            let state = level.registry.default_state(BELT)?;
            let state = level.native_state_with_property(state, "facing", facing)?;
            let state = level.native_state_with_property(state, "part", part)?;
            let state = level.native_state_with_property(state, "slope", slope)?;
            level.native_state_with_property(
                state,
                "waterlogged",
                if block == "minecraft:water" {
                    "true"
                } else {
                    "false"
                },
            )
        }) else {
            return true;
        };
        placements.push((at, state));
    }
    for (at, state) in placements {
        game.native_set_block(game.native_dimension(), at, state, flags::UPDATE_ALL);
    }
    select(game, None);
    game.consume_held();
    true
}

fn chain(game: &Game<'_>, first: [i32; 3], direction: Direction) -> Vec<[i32; 3]> {
    let mut blocks = vec![first];
    for _ in 1..MAX_LENGTH {
        let previous = *blocks.last().expect("belt start");
        let pos = offset(previous, step(direction, rise(game, previous)));
        match segment(game, pos) {
            Some((face, Part::End)) if face == direction => {
                blocks.push(pos);
                return blocks;
            }
            Some((face, Part::Middle | Part::Pulley)) if face == direction => blocks.push(pos),
            _ => break,
        }
    }
    Vec::new()
}

#[derive(Clone)]
struct Carried {
    stack: ItemStack,
    previous: f32,
    position: f32,
    angle: i32,
    inserted_at: i32,
    inserted_from: Option<Direction>,
    processing: Option<(Kind, i32)>,
    locked: bool,
    spacing_break_after: bool,
}

fn items(nbt: &Compound) -> Vec<Carried> {
    let Some(inv) = compound(nbt, "Inventory") else {
        return Vec::new();
    };
    let Some(Tag::List(stacks)) = inv.get(&"Items".into()) else {
        return Vec::new();
    };
    stacks
        .iter()
        .filter_map(|tag| {
            let Tag::Compound(item) = tag else {
                return None;
            };
            Some(Carried {
                stack: ItemStack::from_nbt(compound(item, "Item")?)?,
                previous: float(item, "PrevPos")?,
                position: float(item, "Pos")?,
                angle: int(item, "Angle").unwrap_or(180),
                inserted_at: int(item, "InsertedAt").unwrap_or(-1),
                inserted_from: int(item, "InsertedFrom").and_then(|id| {
                    [
                        Direction::Down,
                        Direction::Up,
                        Direction::North,
                        Direction::South,
                        Direction::West,
                        Direction::East,
                    ]
                    .get(id as usize)
                    .copied()
                }),
                locked: int(item, "Locked") == Some(1),
                spacing_break_after: int(item, "SpacingBreakAfter") == Some(1),
                processing: match item.get(&"FanProcessingType".into()) {
                    Some(Tag::String(value)) => Kind::from_id(&value.to_string_lossy())
                        .map(|kind| (kind, int(item, "FanProcessingTime").unwrap_or(-1))),
                    _ => None,
                },
            })
        })
        .collect()
}

fn positive_order(nbt: &Compound) -> bool {
    compound(nbt, "Inventory").and_then(|inventory| int(inventory, "PositiveOrder")) == Some(1)
}

fn save(nbt: &mut Compound, stacks: &[Carried], positive: bool) {
    let serialized = stacks
        .iter()
        .map(|carried| {
            let mut item = Compound::new();
            item.insert("Item".into(), encode(&carried.stack));
            set_float(&mut item, "Pos", carried.position);
            set_float(&mut item, "PrevPos", carried.previous);
            item.insert("Angle".into(), Tag::Int(carried.angle));
            item.insert("InsertedAt".into(), Tag::Int(carried.inserted_at));
            if let Some(direction) = carried.inserted_from {
                let id = match direction {
                    Direction::Down => 0,
                    Direction::Up => 1,
                    Direction::North => 2,
                    Direction::South => 3,
                    Direction::West => 4,
                    Direction::East => 5,
                };
                item.insert("InsertedFrom".into(), Tag::Int(id));
            }
            if carried.spacing_break_after {
                item.insert("SpacingBreakAfter".into(), Tag::Byte(1));
            }
            if carried.locked {
                item.insert("Locked".into(), Tag::Byte(1));
            }
            if let Some((kind, time)) = carried.processing {
                item.insert("FanProcessingType".into(), Tag::String(kind.id().into()));
                item.insert("FanProcessingTime".into(), Tag::Int(time));
            }
            Tag::Compound(item)
        })
        .collect();
    let mut inventory = Compound::new();
    inventory.insert("Items".into(), Tag::List(serialized));
    inventory.insert("PositiveOrder".into(), Tag::Byte(i8::from(positive)));
    nbt.insert("Inventory".into(), Tag::Compound(inventory));
}

/// Locate the controller and index from a loaded horizontal belt segment.
fn controller(game: &Game<'_>, pos: [i32; 3]) -> Option<([i32; 3], i32, Direction)> {
    let (direction, _) = segment(game, pos)?;
    let mut at = pos;
    for index in 0..MAX_LENGTH {
        if segment(game, at)?.1 == Part::Start {
            return Some((at, index, direction));
        }
        at = [0, 1, -1].into_iter().find_map(|height| {
            let previous = offset(at, step(direction, height).map(|n| -n));
            let (face, part) = segment(game, previous)?;
            (face == direction && part != Part::End && rise(game, previous) == height)
                .then_some(previous)
        })?;
    }
    None
}

pub(super) fn extract_at(
    game: &mut Game<'_>,
    pos: [i32; 3],
    limit: u32,
    exact: bool,
    filter: &Compound,
) -> Option<ItemStack> {
    let (start, index, direction) = controller(game, pos)?;
    let belt = mod_entity(game, start)?;
    let speed = belt_speed(direction, reading(belt, 0));
    let mut carried = items(&belt.nbt);
    let item = carried.iter_mut().find(|item| {
        item.stack.count != 0 && item.position > index as f32 && item.position <= index as f32 + 1.0
    })?;
    if (exact && item.stack.count < limit)
        || !super::create_item_filters::accepts(game.items(), filter, &item.stack)
    {
        return None;
    }
    let count = item.stack.count.min(limit);
    let out = ItemStack {
        count,
        ..item.stack.clone()
    };
    item.stack.count -= count;
    carried.retain(|item| item.stack.count > 0);
    game.native_with_mod_block_entity(start, |belt| save(&mut belt.nbt, &carried, speed >= 0.0))?;
    game.native_block_entity_sync(start);
    Some(out)
}

pub(super) fn detect_centered(
    game: &Game<'_>,
    at: [i32; 3],
    accepts: impl Fn(&ItemStack) -> bool,
) -> bool {
    let Some((controller, segment, _)) = controller(game, at) else {
        return false;
    };
    mod_entity(game, controller).is_some_and(|belt| {
        let center = segment as f32 + 0.5;
        items(&belt.nbt)
            .iter()
            .any(|item| (item.position - center).abs() <= 0.45 && accepts(&item.stack))
    })
}

pub(super) fn feed_point(
    game: &Game<'_>,
    pos: [i32; 3],
) -> Option<([i32; 3], i32, Direction, f32)> {
    let (start, index, direction) = controller(game, pos)?;
    let speed = belt_speed(direction, reading(mod_entity(game, start)?, 0));
    let movement = if speed > 0.0 {
        direction
    } else {
        direction.opposite()
    };
    Some((start, index, movement, speed))
}

pub(super) fn can_feed(
    game: &Game<'_>,
    start: [i32; 3],
    index: i32,
    movement: Direction,
    face: Direction,
    speed: f32,
) -> bool {
    if speed == 0.0 || movement == face.opposite() {
        return false;
    }
    let Some(belt) = mod_entity(game, start) else {
        return false;
    };
    if matches!(belt.nbt.get(&"CapturedAt".into()), Some(Tag::Long(tick)) if *tick == game.world.game_time)
        && matches!(belt.nbt.get(&"CapturedInputs".into()), Some(Tag::List(positions))
            if positions.iter().any(|tag| matches!(tag, Tag::IntArray(pos) if
                pos.as_slice() == [index, face.normal()[0], face.normal()[1], face.normal()[2]])))
    {
        return false;
    }
    let insertion = index as f32
        + if movement != face {
            0.5
        } else if speed < 0.0 {
            1.0
        } else {
            0.0
        };
    items(&belt.nbt).iter().all(|item| {
        item.stack.count == 0
            || item.inserted_at != index
            || item.inserted_from != Some(face)
            || if speed > 0.0 {
                item.position > insertion + 1.0
            } else {
                item.position < insertion - 1.0
            }
    })
}

pub(super) fn receive_landed_package(game: &mut Game<'_>, pos: [i32; 3], stack: ItemStack) -> bool {
    if matches!(
        game.native_block(offset(pos, [0, 1, 0])).as_str(),
        super::create_andesite_tunnel::TUNNEL | create_brass_tunnel::TUNNEL
    ) {
        return false;
    }
    let Some((start, index, direction)) = controller(game, pos) else {
        return false;
    };
    let Some(belt) = mod_entity(game, start) else {
        return false;
    };
    // A stopped Belt accepts top collisions from its retained direction.
    let positive = positive_order(&belt.nbt);
    let (movement, order) = if positive {
        (direction, 1.0)
    } else {
        (direction.opposite(), -1.0)
    };
    if !can_feed(game, start, index, movement, Direction::Up, order) {
        return false;
    }
    feed(game, start, index, movement, Direction::Up, order, stack);
    true
}

pub(super) fn feed(
    game: &mut Game<'_>,
    start: [i32; 3],
    index: i32,
    movement: Direction,
    face: Direction,
    speed: f32,
    stack: ItemStack,
) {
    insert_stack(game, start, index, movement, face, speed, stack, 0.0);
}

fn insert_stack(
    game: &mut Game<'_>,
    start: [i32; 3],
    index: i32,
    movement: Direction,
    face: Direction,
    speed: f32,
    stack: ItemStack,
    lead_in: f32,
) {
    let position = index as f32
        + if movement == face {
            if speed > 0.0 { 0.0 } else { 1.0 }
        } else {
            0.5 - speed.signum() / 16.0
        }
        - speed.signum() * lead_in;
    game.native_with_mod_block_entity(start, |belt| {
        let mut carried = items(&belt.nbt);
        carried.push(Carried {
            stack,
            previous: position,
            position,
            angle: 180,
            inserted_at: index,
            inserted_from: Some(face),
            processing: None,
            locked: false,
            spacing_break_after: false,
        });
        carried.sort_by(|a, b| {
            if speed > 0.0 {
                b.position.total_cmp(&a.position)
            } else {
                a.position.total_cmp(&b.position)
            }
        });
        save(&mut belt.nbt, &carried, speed > 0.0);
    });
    game.native_block_entity_sync(start);
}

pub(super) fn fan_tick(game: &mut Game<'_>, pos: [i32; 3], kind: Kind) {
    let Some((start, index, direction)) = controller(game, pos) else {
        return;
    };
    let Some(entity) = mod_entity(game, start) else {
        return;
    };
    let speed = belt_speed(direction, reading(entity, 0));
    let mut carried = items(&entity.nbt);
    if carried.is_empty() {
        return;
    }
    let mut changed = false;
    let mut processed = Vec::new();
    for item in &mut carried {
        if item.stack.count == 0 || (item.position - (index as f32 + 0.5)).abs() > 0.51 {
            continue;
        }
        let time = match item.processing {
            Some((previous, time)) if previous == kind => time,
            _ => {
                let timer = if create_fan::recipe(game, kind, &item.stack).is_some() {
                    FAN_TIME * (((item.stack.count - 1) / 16 + 1) as i32) + 1
                } else {
                    -1
                };
                item.processing = Some((kind, timer));
                changed = true;
                continue;
            }
        };
        if time < 0 {
            continue;
        }
        item.processing = Some((kind, time - 1));
        changed = true;
        if time == 0
            && let Some(results) = create_fan::recipe(game, kind, &item.stack)
        {
            let mut outputs =
                super::create_fan_items::roll(game, item.stack.count, &results).into_iter();
            if let Some(stack) = outputs.next() {
                item.stack = stack;
                for extra in outputs {
                    processed.push(Carried {
                        stack: extra,
                        ..item.clone()
                    });
                }
            } else {
                item.stack.count = 0;
            }
        }
    }
    if changed {
        carried.extend(processed);
        game.native_with_mod_block_entity(start, |belt| {
            save(&mut belt.nbt, &carried, speed >= 0.0)
        });
        game.native_block_entity_sync(start);
    }
}

fn infeed(
    game: &mut Game<'_>,
    entity: &mut ModBlockEntity,
    chain: &[[i32; 3]],
    speed: f32,
    items: &mut Vec<Carried>,
) {
    for (index, &pos) in chain.iter().enumerate() {
        let shift = if speed == 0.0 {
            0.0
        } else {
            speed.signum() / 16.0
        };
        let start = index as f32 + 0.5 - shift;
        if items
            .iter()
            .any(|carried| (carried.position - start).abs() < 1.0)
        {
            continue;
        }
        let mut stack = if index == 0 {
            entity.items[0].take()
        } else if mod_entity(game, pos)
            .is_some_and(|segment| segment.items.first().is_some_and(Option::is_some))
        {
            game.native_with_mod_block_entity(pos, |segment| segment.items[0].take())
                .flatten()
        } else {
            None
        };
        if stack.is_none()
            && !matches!(
                game.native_block(offset(pos, [0, 1, 0])).as_str(),
                super::create_andesite_tunnel::TUNNEL | create_brass_tunnel::TUNNEL
            )
        {
            collect_landed_items(game, pos, &mut stack, BELT);
        }
        if let Some(stack) = stack {
            items.push(Carried {
                stack,
                previous: start,
                position: start,
                angle: 180,
                inserted_at: index as i32,
                inserted_from: Some(Direction::Up),
                processing: None,
                locked: false,
                spacing_break_after: false,
            });
        }
    }
}

fn advance(
    game: &mut Game<'_>,
    chain: &[[i32; 3]],
    direction: Direction,
    speed: f32,
    items: Vec<Carried>,
    captured_inputs: &mut Vec<Tag>,
) -> Vec<Carried> {
    if speed == 0.0 {
        return items;
    }
    let positive = speed > 0.0;
    let along = delta(direction);
    let length = chain.len() as i32;
    let first = chain[0];
    let end = if positive {
        chain[chain.len() - 1]
    } else {
        first
    };
    let target = offset(end, along.map(|n| if positive { n } else { -n }));
    let movement = if positive {
        direction
    } else {
        direction.opposite()
    };
    let target_block = game.native_block(target);
    let depot = target_block == DEPOT;
    let ejector = target_block == super::create_ejector::EJECTOR;
    let next_belt = feed_point(game, target);
    let drain = target_block == super::create_item_drain::DRAIN;
    let blocked = !depot && !ejector && !drain && next_belt.is_none()
        && !game.native_block_collision(target).is_empty();
    let margin = if depot || ejector || drain || next_belt.is_some() {
        0.25
    } else if blocked {
        0.45
    } else {
        0.0
    };
    let edge = if positive { length as f32 } else { 0.0 };
    let mut front: Option<f32> = None;
    let mut remaining = Vec::with_capacity(items.len());
    for mut item in items {
        item.previous = item.position;
        let spacing_break = std::mem::take(&mut item.spacing_break_after);
        let mut distance = speed;
        let mut blocked_by_front = false;
        if let Some(front_position) = front {
            let space = front_position - item.position;
            blocked_by_front = space.abs() <= 1.0;
            distance = if blocked_by_front {
                0.0
            } else if positive {
                distance.min(space - 1.0)
            } else {
                distance.max(space + 1.0)
            };
        }
        let mut room = edge - item.position;
        if room.abs() < distance.abs() + 1.0 {
            room += if positive { -margin } else { margin };
        }
        let moved = if positive {
            distance.min(room)
        } else {
            distance.max(room)
        };
        let next = item.position + moved;
        let stage = item.position.floor() as i32;
        let center = stage as f32 + 0.5 + speed.signum() / 512.0;
        let toward = |point| {
            if positive {
                point >= center
            } else {
                point <= center
            }
        };
        let crossing = if positive {
            item.position <= stage as f32 + 0.5 && next >= stage as f32 + 0.5
        } else {
            item.position >= stage as f32 + 0.5 && next <= stage as f32 + 0.5
        };
        if (0..length).contains(&stage) && (item.locked || !blocked_by_front && crossing) {
            let above = offset(chain[stage as usize], [0, 2, 0]);
            let action = match game.native_block(above).as_str() {
                "create:deployer" => {
                    create_assembly::deploy(game, above, &mut item.stack, item.locked)
                }
                super::create_press::PRESS => {
                    super::create_press::offer_belt(game, above, &mut item.stack, item.locked)
                }
                _ => AssemblyAction::Pass,
            };
            match action {
                AssemblyAction::Pass => item.locked = false,
                AssemblyAction::Hold => {
                    item.position = center;
                    item.locked = true;
                    front = (!spacing_break).then_some(center);
                    remaining.push(item);
                    continue;
                }
                AssemblyAction::Output { stack, locked } => {
                    let mut output = item.clone();
                    output.position = center;
                    output.stack = stack;
                    output.processing = None;
                    output.locked = locked;
                    // Java leaves an empty held entry behind a spent input for
                    // one pass. The next item can advance before it is removed.
                    output.spacing_break_after = !locked && item.stack.count == 0;
                    remaining.push(output);
                    if item.stack.count != 0 {
                        item.position = center - speed.signum() / 256.0;
                        if locked {
                            item.locked = false;
                        }
                        remaining.push(item);
                    }
                    front = (!spacing_break).then_some(center);
                    continue;
                }
            }
        }
        if blocked_by_front {
            front = (!spacing_break).then_some(item.position);
            remaining.push(item);
            continue;
        }
        if (0..length).contains(&stage)
            && toward(next)
            && (!toward(item.position) || item.position == center)
        {
            let above = offset(chain[stage as usize], [0, 2, 0]);
            match create_spout::offer(game, above, &mut item.stack, item.position == center) {
                SpoutAction::Hold => {
                    item.position = center;
                    front = (!spacing_break).then_some(center);
                    remaining.push(item);
                    continue;
                }
                SpoutAction::Output(stack) => {
                    let mut output = item.clone();
                    output.position = center;
                    output.stack = stack;
                    output.processing = None;
                    remaining.push(output);
                    if item.stack.count > 0 {
                        item.position = center;
                        remaining.push(item);
                    }
                    front = (!spacing_break).then_some(center);
                    continue;
                }
                SpoutAction::Pass => {}
            }
        }
        if let Some(entry) = create_belt_funnel::take(
            game,
            chain,
            direction,
            movement,
            item.position,
            next,
            &mut item.stack,
        ) {
            if item.stack.count > 0 {
                item.position = entry;
                front = (!spacing_break).then_some(entry);
                remaining.push(item);
            }
            continue;
        }
        if let Some(entry) = super::create_crushing::blocking_belt_position(
            game,
            chain,
            direction,
            movement,
            item.position,
            next,
            &mut item.stack,
        ) {
            item.position = entry;
            front = (!spacing_break).then_some(entry);
            if item.stack.count > 0 {
                remaining.push(item);
            }
            continue;
        }
        let next_segment = next as i32;
        if next_segment != item.position as i32 && (0..length).contains(&next_segment) {
            let at = chain[next_segment as usize];
            match create_brass_tunnel::arrive(game, at, movement, &item.stack) {
                Arrival::Pass => {}
                Arrival::Wait => {
                    item.position = item.position.floor() + if speed > 0.0 { 0.99 } else { 0.01 };
                    front = (!spacing_break).then_some(item.position);
                    remaining.push(item);
                    continue;
                }
                Arrival::Capture => {
                    if let Some(face) = item.inserted_from {
                        let [x, y, z] = face.normal();
                        captured_inputs.push(Tag::IntArray(vec![item.inserted_at, x, y, z]));
                    }
                    continue;
                }
            }
            if !super::create_andesite_tunnel::distribute(game, at, movement, &mut item.stack) {
                front = (!spacing_break).then_some(item.position);
                remaining.push(item);
                continue;
            }
        }
        item.position = next;
        front = (!spacing_break).then_some(item.position);
        if moved != distance {
            if depot {
                let offered = item.stack.count;
                let rest = receive_stack(game, target, item.stack);
                if rest.as_ref().map_or(0, |stack| stack.count) < offered {
                    super::create_depot::play_slide(game, target);
                }
                let Some(rest) = rest else {
                    continue;
                };
                item.stack = rest;
            } else if ejector {
                let inserted = super::create_ejector::insert(game, target, &item.stack);
                if inserted != 0 {
                    game.native_block_entity_sync(target);
                    item.stack.count -= inserted;
                    if item.stack.count == 0 {
                        continue;
                    }
                }
            } else if drain {
                item.stack.count -= super::create_item_drain::accept(game, target, &item.stack, movement);
                if item.stack.count == 0 {
                    continue;
                }
            } else if let Some((start, index, next_movement, next_speed)) = next_belt {
                if can_feed(game, start, index, next_movement, movement, next_speed) {
                    let previous_segment = offset(target, movement.opposite().normal());
                    let lead_in = if next_movement == movement
                        && item.previous != 0.0
                        && segment(game, previous_segment).is_some()
                    {
                        0.26
                    } else {
                        0.0
                    };
                    insert_stack(
                        game,
                        start,
                        index,
                        next_movement,
                        movement,
                        next_speed,
                        item.stack,
                        lead_in,
                    );
                    continue;
                }
            } else if !blocked {
                let slope = rise(game, first) as f32;
                let height = slope * (item.position.min(length as f32 - 0.5) - 0.5);
                let velocity = f64::from(speed.abs().max(0.125));
                let normal = movement.normal();
                let impulse = [
                    f64::from(normal[0]) * velocity,
                    f64::from(slope * speed.signum()) * velocity + 0.125,
                    f64::from(normal[2]) * velocity,
                ];
                let magnitude = impulse.iter().map(|v| v * v).sum::<f64>().sqrt();
                let world_pos = std::array::from_fn(|axis| {
                    f64::from(first[axis])
                        + if axis == 1 {
                            f64::from(height) + 0.875
                        } else {
                            0.5 + f64::from(along[axis]) * f64::from(item.position - 0.5)
                        }
                        + impulse[axis] / magnitude * 0.001
                });
                game.add_item_entity(item.stack, world_pos, Some(impulse), 10);
                continue;
            }
        }
        remaining.push(item);
    }
    remaining
}

pub(super) fn tick(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
    rpm: f32,
    speed_changed: bool,
) {
    let Some((direction, part)) = segment(game, pos) else {
        return;
    };
    if part != Part::Start {
        if speed_changed {
            game.native_block_entity_sync(pos);
        }
        return;
    }
    let chain = chain(game, pos, direction);
    if chain.len() < 2 || entity.items.is_empty() {
        return;
    }
    let speed = belt_speed(direction, rpm);
    let mut carried = items(&entity.nbt);
    let before = carried.len();
    carried.retain(|item| item.stack.count > 0);
    infeed(game, entity, &chain, speed, &mut carried);
    let retained_order = positive_order(&entity.nbt);
    let positive = if speed == 0.0 {
        retained_order
    } else {
        speed > 0.0
    };
    if before == 0 && carried.is_empty() && !speed_changed && positive == retained_order {
        return;
    }
    carried.sort_by(|a, b| {
        if positive {
            b.position.total_cmp(&a.position)
        } else {
            a.position.total_cmp(&b.position)
        }
    });
    let mut captured_inputs = Vec::new();
    let carried = advance(
        game,
        &chain,
        direction,
        speed,
        carried,
        &mut captured_inputs,
    );
    if captured_inputs.is_empty() {
        entity.nbt.remove(&"CapturedAt".into());
        entity.nbt.remove(&"CapturedInputs".into());
    } else {
        entity
            .nbt
            .insert("CapturedAt".into(), Tag::Long(game.world.game_time));
        entity
            .nbt
            .insert("CapturedInputs".into(), Tag::List(captured_inputs));
    }
    save(&mut entity.nbt, &carried, positive);
    game.native_block_entity_sync(pos);
}

pub(super) fn register_models(models: &mut Vec<String>) {
    models.push(PULLEY.into());
}

pub(super) fn update_tag(entity: &ModBlockEntity) -> Compound {
    let mut tag = Compound::new();
    set_float(&mut tag, "VisualSpeed", reading(entity, 0));
    if let Some(inventory) = entity.nbt.get(&"Inventory".into()) {
        tag.insert("Inventory".into(), inventory.clone());
    }
    tag
}

pub(super) fn render(
    game: &Game<'_>,
    pos: [i32; 3],
    _state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    let Some((direction, part)) = segment(game, pos) else {
        return;
    };
    if part != Part::Middle {
        let rpm = float(&entity.nbt, "VisualSpeed").unwrap_or(0.0);
        let angle = wheel_angle(draw.game_time, draw.partial, rpm, 0.0);
        draw_rotating(game, draw, pulley_axis(direction), angle, PULLEY);
    }
    if part == Part::Start {
        let along = delta(direction).map(|n| n as f32);
        let slope = rise(game, pos) as f32;
        let max_travel = int(&entity.nbt, "Length").unwrap_or(1) as f32 - 1.0;
        for item in items(&entity.nbt)
            .into_iter()
            .filter(|item| item.stack.count > 0)
        {
            let travel = item.previous + (item.position - item.previous) * draw.partial - 0.5;
            draw.push();
            let height = travel.clamp(0.0, max_travel.max(0.0)) * slope;
            draw.translate([
                0.5 + along[0] * travel,
                0.86 + height,
                0.5 + along[2] * travel,
            ]);
            if slope != 0.0 && (0.0..=max_travel).contains(&travel) {
                draw.rotate_about([along[2], 0.0, -along[0]], -45.0 * slope, [0.0; 3]);
            }
            draw.rotate_about([0.0, 1.0, 0.0], item.angle as f32, [0.0; 3]);
            draw.rotate_about([1.0, 0.0, 0.0], 90.0, [0.0; 3]);
            draw.scale([0.55; 3]);
            game.native_draw_item(draw, &item.stack, DisplayContext::Fixed, None, 0);
            draw.pop();
        }
    }
}
