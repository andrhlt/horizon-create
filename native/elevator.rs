use horizon_core::geometry::Direction;
use horizon_world::level::flags;
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;

use super::create_bearing::{capture, relative};
use super::create_contact::CONTACT;
use super::create_elevator_seats;
use super::create_elevator_floors as floor_controls;
use super::create_fan::facing;
use super::create_machines::{float, int, mod_entity, offset, set_float};
use super::create_rope::{self as rope, Payload};
use super::native_block_entity_draw::BlockEntityDraw;
use super::{Game, GameLevel};
use crate::containers::ModBlockEntity;

pub(super) const PULLEY: &str = "create:elevator_pulley";
use floor_controls::CONTACT as FLOOR;

fn coords(data: &Compound, name: &str) -> Option<[i32; 3]> {
    let Tag::IntArray(words) = data.get(&name.into())? else {
        return None;
    };
    words.as_slice().try_into().ok()
}

fn long(data: &Compound, name: &str) -> Option<i64> {
    match data.get(&name.into()) {
        Some(Tag::Long(value)) => Some(*value),
        _ => None,
    }
}

pub(super) fn click(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if game.native_block(pos) != PULLEY {
        return false;
    }
    let main = mod_entity(game, pos)
        .and_then(|entity| coords(&entity.nbt, "MirrorParent"))
        .unwrap_or(pos);
    game.native_with_mod_block_entity(main, |entity| {
        entity.nbt.insert("Clicked".into(), Tag::Byte(1));
    });
    true
}

pub(super) fn source(level: &GameLevel<'_>, state: BlockStateId, out: &mut bool) {
    *out |= level
        .registry
        .state(state)
        .is_some_and(|info| info.name == FLOOR);
}

pub(super) fn signal(
    level: &GameLevel<'_>,
    state: BlockStateId,
    side: Direction,
    direct: bool,
    out: &mut i32,
) {
    if direct {
        return;
    }
    let Some(info) = level.registry.state(state) else {
        return;
    };
    if info.name == FLOOR
        && info.properties.get("powering").is_some_and(|v| v == "true")
        && info
            .properties
            .get("facing")
            .is_some_and(|v| v != super::create_contact::face_name(side))
    {
        *out = 15;
    }
}

fn set_power(game: &mut Game<'_>, pos: [i32; 3], key: &str, on: bool) {
    game.native_set_block_property(pos, key, if on { "true" } else { "false" });
}

fn rider(data: &Compound, game: &Game<'_>) -> Option<u32> {
    let Tag::IntArray(uuid) = data.get(&"SeatOccupant".into())? else {
        return None;
    };
    game.mob_by_uuid(uuid.as_slice().try_into().ok()?)
}

pub(super) fn seats(game: &mut Game<'_>) {
    create_elevator_seats::prune(game);
    let dimension = game.native_dimension();
    let now = game.world.game_time;
    let mobs: Vec<_> = game.mobs.iter()
        .filter(|mob| mob.alive() && mob.extra.mount.is_none())
        .map(|mob| mob.id)
        .collect();
    for id in mobs {
        let existing = match game.persist.raw.get(&id) {
            Some(Tag::Compound(data)) => coords(data, "CreateSeat").zip(long(data, "CreateSeatAt")),
            _ => None,
        };
        let Some((seat, attached)) = existing else {
            continue;
        };
        if create_elevator_seats::is_seat(&game.native_block(seat)) {
            if now > attached {
                game.native_teleport_mob(
                    dimension,
                    id,
                    [
                        f64::from(seat[0]) + 0.5,
                        f64::from(seat[1]) + 0.4125,
                        f64::from(seat[2]) + 0.5,
                    ],
                );
            }
        } else if let Some(Tag::Compound(tag)) = game.persist.raw.get_mut(&id) {
            tag.remove(&"CreateSeat".into());
            tag.remove(&"CreateSeatAt".into());
        }
    }
}

fn seat_passengers(game: &mut Game<'_>, payload: &Payload, location: [f64; 3]) {
    for block in &payload.blocks {
        let Some(id) = rider(block, game) else {
            continue;
        };
        let rel = relative(block);
        let at = std::array::from_fn(|i| location[i] + f64::from(rel[i]) + 0.5);
        game.native_teleport_mob(game.native_dimension(), id, at);
    }
}

fn convert_floor(game: &mut Game<'_>, at: [i32; 3]) {
    if game.native_block(at) != CONTACT {
        return;
    }
    let Some(face) = game.native_block_property(at, "facing") else {
        return;
    };
    let Some(state) = game.native_default_state(FLOOR) else {
        return;
    };
    if let Some(state) =
        game.with_level(|_, level, _| level.native_state_with_property(state, "facing", &face))
    {
        game.native_set_block(game.native_dimension(), at, state, flags::UPDATE_ALL);
    }
}

fn assemble(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity, rpm: f32) {
    if rpm == 0.0 {
        return;
    }
    let max = rope::level_range(game, pos);
    let Some(depth) = (1..=max).find(|&depth| {
        let at = rope::at_depth(pos, depth);
        let state = game.world.block(at[0], at[1], at[2]);
        !game.res.behaviours().is_replaceable(state) && !game.native_block_collision(at).is_empty()
    }) else {
        return;
    };
    let anchor = rope::at_depth(pos, depth);
    let mut blocks = capture(game, pos, anchor);
    for block in &mut blocks {
        let seat = offset(anchor, relative(block));
        if !create_elevator_seats::is_seat(&game.native_block(seat)) {
            continue;
        }
        let occupant = game
            .mobs
            .iter()
            .find(|mob| {
                mob.alive()
                    && matches!(game.persist.raw.get(&mob.id),
            Some(Tag::Compound(data)) if coords(data,"CreateSeat") == Some(seat))
            })
            .map(|mob| mob.id);
        if let Some(id) = occupant {
            let uuid = game.uuid_for(id);
            block.insert("SeatOccupant".into(), Tag::IntArray(uuid.to_vec()));
        }
    }
    let mut contacts = blocks.iter().filter_map(|block| {
        let state = block
            .get(&"BlockState".into())
            .and_then(|data| game.state_from_nbt(data))?;
        if game.native_state_block(state) != Some(CONTACT) {
            return None;
        }
        let face = facing(game, state)?;
        let normal = face.normal();
        (normal[1] == 0).then_some((
            offset(offset(anchor, relative(block)), normal),
            face.opposite(),
        ))
    });
    let Some((contact, face)) = contacts.next() else {
        return;
    };
    if contacts.next().is_some() {
        return;
    }
    let floor_delta = contact[1] - anchor[1];
    let align = (pos[1] - 1 + floor_delta - max)..=(pos[1] - 1 + floor_delta);
    let floors: Vec<_> = align
        .map(|y| [contact[0], y, contact[2]])
        .filter(|&at| {
            matches!(game.native_block(at).as_str(), FLOOR | CONTACT)
                && facing(game, game.world.block(at[0], at[1], at[2])) == Some(face)
        })
        .collect();
    if floors.is_empty() {
        return;
    }
    super::create_elevator_collision::capture(game, &mut blocks, anchor);
    super::create_elevator_doors::capture(&mut blocks);
    let Some(payload) = rope::spawn_payload(game, pos, anchor, blocks) else {
        return;
    };
    create_elevator_seats::attach_cabin(game, pos, anchor, &payload);
    for block in &payload.blocks {
        let [dx, dy, dz] = relative(block);
        if dy == 0 && (dx != 0 || dz != 0) {
            let at = [pos[0] + dx, pos[1], pos[2] + dz];
            if game.native_block(at) == PULLEY {
                game.native_with_mod_block_entity(at, |mirror| {
                    mirror
                        .nbt
                        .insert("MirrorParent".into(), Tag::IntArray(pos.to_vec()));
                });
            }
        }
    }
    for &floor in &floors {
        convert_floor(game, floor);
    }
    entity.nbt.insert(
        "Floors".into(),
        Tag::List(
            floors
                .into_iter()
                .map(|p| Tag::IntArray(p.to_vec()))
                .collect(),
        ),
    );
    entity
        .nbt
        .insert("FloorDelta".into(), Tag::Int(floor_delta));
    entity
        .nbt
        .insert("TargetFloor".into(), Tag::Int(contact[1]));
    entity
        .nbt
        .insert("ArrivalPowerAt".into(), Tag::Long(game.world.game_time + 5));
    entity
        .nbt
        .insert("CabinY".into(), Tag::Double(f64::from(anchor[1]).to_bits()));
    entity.nbt.insert("Arrived".into(), Tag::Byte(1));
    set_float(&mut entity.nbt, "Offset", (depth - 1) as f32);
    floor_controls::move_controls(game, pos, &payload, f64::from(anchor[1]));
    let y = f64::from(anchor[1]);
    publish_belt(game, pos, entity, &payload, y, y, true);
    rope::save_payload(game, pos, payload);
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity, rpm: f32) {
    if let Some(parent) = coords(&entity.nbt, "MirrorParent") {
        if game.native_block(parent) != PULLEY || rope::payload(game, parent).is_none() {
            entity.nbt.remove(&"MirrorParent".into());
        }
        return;
    }
    let clicked = entity.nbt.remove(&"Clicked".into()).is_some();
    let Some(mut payload) = rope::payload(game, pos) else {
        if clicked {
            assemble(game, pos, entity, rpm);
        }
        return;
    };
    let Some(Tag::Double(bits)) = entity.nbt.get(&"CabinY".into()) else {
        return;
    };
    let mut y = f64::from_bits(*bits);
    let previous_y = y;
    let now = game.world.game_time;
    let anchor = rope::at_depth(pos, 1);
    let landing = [pos[0], y.round() as i32, pos[2]];
    if clicked && rope::land_payload(game, &payload, landing) {
        super::create_elevator_indicator::disassemble(game, landing);
        create_elevator_seats::land_cabin(game, pos, landing, &payload);
        floor_controls::remove_controls(game, pos);
        entity.nbt.remove(&"FloorNamesReady".into());
        publish_belt(game, pos, entity, &payload, y, y.round(), false);
        entity.nbt.remove(&"CabinY".into());
        for key in ["CabinHasMoved", "DoorContact", "DoorMotion", "DoorArrived"] {
            entity.nbt.remove(&key.into());
        }
        return;
    }
    seat_passengers(game, &payload, [f64::from(pos[0]), y, f64::from(pos[2])]);
    let floor_delta = int(&entity.nbt, "FloorDelta").unwrap_or(0);
    let mut target = int(&entity.nbt, "TargetFloor").unwrap_or(y.round() as i32 + floor_delta);
    let floors: Vec<[i32; 3]> = match entity.nbt.get(&"Floors".into()) {
        Some(Tag::List(floors)) => floors
            .iter()
            .filter_map(|tag| match tag {
                Tag::IntArray(pos) => pos.as_slice().try_into().ok(),
                _ => None,
            })
            .collect(),
        _ => Vec::new(),
    };
    // Contraption actors see the cabin pose from before this pulley tick.
    let door_location = [f64::from(pos[0]), y, f64::from(pos[2])];
    super::create_elevator_doors::tick(
        game,
        &mut payload,
        floors.iter().copied().find(|pos| pos[1] == target),
        door_location,
        &mut entity.nbt,
    );
    if int(&entity.nbt, "FloorNamesReady") != Some(1) {
        floor_controls::init_names(game, &floors);
        entity.nbt.insert("FloorNamesReady".into(), Tag::Byte(1));
    }
    for &floor in &floors {
        let powered = game.native_neighbor_signal(game.native_dimension(), floor) > 0;
        let old = game.native_block_property(floor, "powered").as_deref() == Some("true");
        if old != powered {
            set_power(game, floor, "powered", powered);
            if powered {
                target = floor[1];
            }
        }
    }
    if let Some(Tag::Int(selected)) = entity.nbt.remove(&"SelectedFloor".into()) {
        if floors.iter().any(|pos| pos[1] == selected && game.native_block(*pos) == FLOOR) {
            target = selected;
        }
    }
    if int(&entity.nbt, "TargetFloor") != Some(target) {
        entity.nbt.insert("TargetFloor".into(), Tag::Int(target));
        entity.nbt.remove(&"ArrivalPowerAt".into());
        for &floor in &floors {
            set_power(game, floor, "calling", floor[1] == target);
            set_power(game, floor, "powering", false);
        }
    }
    if long(&entity.nbt, "ArrivalPowerAt").is_some_and(|when| when <= now) {
        for &floor in &floors {
            if floor[1] == target {
                set_power(game, floor, "powering", true);
            }
        }
        floor_controls::floor_reached(game, &floors, target);
        entity.nbt.remove(&"ArrivalPowerAt".into());
    }
    let offset = float(&entity.nbt, "Offset").unwrap_or(0.0);
    let target_y = target - floor_delta;
    let diff = (anchor[1] - target_y) as f32 - offset;
    let max = (rpm * 2.0 / 512.0).abs().min(1.99);
    let acceleration = 0.0075 + max * (0.0175 - 0.0075);
    let braking = (2.0 * diff.abs() * acceleration).sqrt();
    let mut prior = float(&entity.nbt, "PreviousTravel").unwrap_or(0.0);
    let mut velocity = || {
        prior = diff
            .clamp(-max, max)
            .clamp(prior - acceleration, prior + acceleration)
            .clamp(-braking, braking);
        prior
    };
    let next_offset = offset + velocity();
    let limit = rope::level_range(game, pos) as f32;
    let at_limit = next_offset <= 0.0 || next_offset >= limit;
    let new_offset = next_offset.clamp(0.0, limit);
    if at_limit {
        // Java's linear actuator resets the cabin to its exact travel limit
        // before the elevator applies its small arrival correction.
        y = f64::from(anchor[1]) - f64::from(new_offset);
    }
    let arrived = diff.abs() < 0.5;
    if arrived {
        let correction = f64::from(target_y) - y;
        y += if correction.abs() > 1.0 / 128.0 {
            correction * 0.25
        } else {
            correction
        };
        if int(&entity.nbt, "Arrived") != Some(1) {
            super::create_elevator_indicator::arrive(game, [pos[0], pos[1] - new_offset as i32, pos[2]]);
            entity
                .nbt
                .insert("ArrivalPowerAt".into(), Tag::Long(now + 1));
        }
    } else {
        let motion = velocity();
        if !at_limit {
            y -= f64::from(motion);
        }
        set_float(&mut entity.nbt, "CabinMotionY", -velocity());
    }
    let was_arrived = int(&entity.nbt, "Arrived") == Some(1);
    entity.nbt.insert("DoorArrived".into(), Tag::Byte(i8::from(was_arrived)));
    entity.nbt.insert("DoorMotion".into(), Tag::Double((y - previous_y).to_bits()));
    entity
        .nbt
        .insert("Arrived".into(), Tag::Byte(i8::from(arrived)));
    set_float(&mut entity.nbt, "PreviousTravel", prior);
    set_float(&mut entity.nbt, "Offset", new_offset);
    entity.nbt.insert("CabinY".into(), Tag::Double(y.to_bits()));
    super::create_elevator_collision::carry_local(
        game,
        &payload.blocks,
        [f64::from(pos[0]), previous_y, f64::from(pos[2])],
        y,
    );
    let location = [f64::from(pos[0]), y, f64::from(pos[2])];
    rope::move_payload_at(game, anchor, &mut payload, location);
    super::create_elevator_doors::animate(game, &mut payload, door_location);
    create_elevator_seats::move_cabin(
        game,
        pos,
        &payload,
        [f64::from(pos[0]), y, f64::from(pos[2])],
    );
    floor_controls::move_controls(game, pos, &payload, y);
    publish_belt(game, pos, entity, &payload, previous_y, y, true);
    rope::save_payload(game, pos, payload);
}

const COIL: &str = "create:block/elevator_pulley/rope_coil";
const COIL_SCROLL: &str = "create:block/elevator_pulley/rope_coil_scroll";
const BELT: &str = "create:block/elevator_pulley/rope_scroll";
const HALF_BELT: &str = "create:block/elevator_pulley/rope_half_scroll";
const MAGNET: &str = "create:block/elevator_pulley/pulley_magnet";
const BELT_SPRITE: &str = "create:block/elevator_pulley_belt_scroll";
const COIL_SPRITE: &str = "create:block/elevator_pulley_coil_scroll";

pub(super) fn models(models: &mut Vec<String>) {
    models.extend([COIL, COIL_SCROLL, BELT, HALF_BELT, MAGNET].map(String::from));
}

fn set_belt(entity: &mut ModBlockEntity, from: f64, to: f64, running: bool) -> bool {
    let mut changed = false;
    for (key, value) in [
        ("BeltFrom", Tag::Double(from.to_bits())),
        ("BeltTo", Tag::Double(to.to_bits())),
        ("BeltRunning", Tag::Byte(i8::from(running))),
    ] {
        if entity.nbt.get(&key.into()) != Some(&value) {
            entity.nbt.insert(key.into(), value);
            changed = true;
        }
    }
    changed
}

fn publish_belt(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
    payload: &Payload,
    from_y: f64,
    to_y: f64,
    running: bool,
) {
    let origin = f64::from(pos[1] - 1);
    let from = origin - from_y;
    let to = origin - to_y;
    if set_belt(entity, from, to, running) {
        game.native_block_entity_sync(pos);
    }
    for block in &payload.blocks {
        let [x, y, z] = relative(block);
        if y != 0 || (x == 0 && z == 0) {
            continue;
        }
        let at = [pos[0] + x, pos[1], pos[2] + z];
        if game.native_block(at) != PULLEY {
            continue;
        }
        if game.native_with_mod_block_entity(at, |mirror| {
            coords(&mirror.nbt, "MirrorParent") == Some(pos) && set_belt(mirror, from, to, running)
        }) == Some(true)
        {
            game.native_block_entity_sync(at);
        }
    }
}

fn belt_length(entity: &ModBlockEntity, key: &str) -> f64 {
    match entity.nbt.get(&key.into()) {
        Some(Tag::Double(bits)) => f64::from_bits(*bits),
        _ => 0.0,
    }
}

pub(super) fn update_tag(entity: &ModBlockEntity) -> Compound {
    ["BeltFrom", "BeltTo", "BeltRunning", "VisualSpeed"]
        .into_iter()
        .filter_map(|key| {
            entity
                .nbt
                .get(&key.into())
                .map(|value| (key.into(), value.clone()))
        })
        .collect()
}

pub(super) fn bounds(entity: &ModBlockEntity, bounds: &mut [f32; 6]) {
    let length = belt_length(entity, "BeltFrom").max(belt_length(entity, "BeltTo")) as f32;
    bounds[1] = bounds[1].min(-length);
}

fn scroll_model(
    game: &Game<'_>,
    draw: &mut BlockEntityDraw,
    model: &str,
    sprite: &str,
    phase: f32,
) {
    let start = draw.vertices_mut().len();
    game.native_draw_model(draw, model, 0xFFFFFF);
    if let Some(rect) = game.gui.atlas.sprites.get(sprite) {
        // Java maps the source sprite onto one half of the scroll sprite.
        let offset = phase * (rect.v1 - rect.v0);
        for vertex in &mut draw.vertices_mut()[start..] {
            vertex.uv[1] = rect.v0 + (vertex.uv[1] - rect.v0) * 0.5 + offset;
        }
    }
}

pub(super) fn render(
    game: &Game<'_>,
    pos: [i32; 3],
    state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    let face = facing(game, state).unwrap_or(Direction::North);
    let axis = if matches!(face, Direction::North | Direction::South) {
        0
    } else {
        2
    };
    let speed = float(&entity.nbt, "VisualSpeed").unwrap_or(0.0);
    let shaft_angle = super::create_visuals::wheel_angle(draw.game_time, draw.partial, speed, 0.0);
    super::create_visuals::draw_rotating(game, draw, axis, shaft_angle, "create:block/shaft");

    let previous = belt_length(entity, "BeltFrom");
    let current = belt_length(entity, "BeltTo");
    let length = (previous + f64::from(draw.partial) * (current - previous)).max(0.0) as f32;
    let running = int(&entity.nbt, "BeltRunning") == Some(1);
    let angle = match face {
        Direction::West => 270.0,
        Direction::East => 90.0,
        Direction::South => 180.0,
        _ => 0.0,
    };
    let belt_phase = (-(length + 0.5)).rem_euclid(1.0) / 2.0;
    let coil_phase = (-(length + 3.0 / 16.0)).rem_euclid(0.5);
    let base_light = draw.light;
    draw.push();
    draw.rotate_about([0.0, 1.0, 0.0], angle, [0.5; 3]);
    if length == 0.0 {
        game.native_draw_model(draw, COIL, 0xFFFFFF);
    } else {
        scroll_model(game, draw, COIL_SCROLL, COIL_SPRITE, coil_phase);
    }
    let segment = |draw: &mut BlockEntityDraw, model, at: f32, rolling| {
        let (block, sky) = game.native_light([pos[0], pos[1] - at as i32, pos[2]]);
        draw.light = (u32::from(sky) * 16) | (u32::from(block) * 16 << 8);
        draw.push();
        draw.translate([0.0, -at, 0.0]);
        if rolling {
            scroll_model(game, draw, model, BELT_SPRITE, belt_phase);
        } else {
            game.native_draw_model(draw, model, 0xFFFFFF);
        }
        draw.pop();
    };
    if running || length == 0.0 {
        segment(draw, MAGNET, length, false);
    }
    if length != 0.0 {
        let fraction = length.fract();
        if !(0.25..=0.75).contains(&fraction) {
            let at = if fraction > 0.75 {
                fraction - 1.0
            } else {
                fraction
            };
            segment(draw, HALF_BELT, at, true);
        }
        if running {
            for i in 0..(length - 0.25).ceil() as i32 {
                segment(draw, BELT, length - i as f32, true);
            }
        }
    }
    draw.light = base_light;
    draw.pop();
}
