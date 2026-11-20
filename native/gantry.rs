use horizon_core::geometry::Direction;
use horizon_world::level::flags;
use horizon_world::nbt::{Compound, Tag};

use super::Game;
use super::create_bearing::{
    attached_glue, capture_attached, display, move_glue, relative, restore,
};
use super::create_depot::compound;
use super::create_fan::facing;
use super::create_machines::{int, mod_entity, offset};

pub(super) const SHAFT: &str = "create:gantry_shaft";
pub(super) const CARRIAGE: &str = "create:gantry_carriage";
pub(super) const PINION: &str = "create:gantry_pinion";
const MOVING: &str = "CreateGantry";

fn set_num(data: &mut Compound, key: &str, value: f64) {
    data.insert(key.into(), Tag::Double(value.to_bits()));
}

fn number(data: &Compound, key: &str) -> f64 {
    match data.get(&key.into()) {
        Some(Tag::Double(bits)) => f64::from_bits(*bits),
        _ => 0.0,
    }
}

fn pos(data: &Compound, key: &str) -> Option<[i32; 3]> {
    let Tag::IntArray(pos) = data.get(&key.into())? else {
        return None;
    };
    pos.as_slice().try_into().ok()
}

fn side(game: &Game<'_>, at: [i32; 3]) -> Option<Direction> {
    facing(game, game.world.block(at[0], at[1], at[2]))
}

fn drive(game: &Game<'_>, shaft: [i32; 3]) -> Option<(Direction, f32, bool, Option<f32>)> {
    if game.native_block(shaft) != SHAFT
        || game.native_block_property(shaft, "powered").as_deref() == Some("true")
    {
        return None;
    }
    let facing = side(game, shaft)?;
    let (rpm, sequence_limit) = super::create_machines::drive_speed_and_distance(game, shaft);
    let speed = (-rpm / 512.0).clamp(-0.49, 0.49);
    if speed == 0.0 {
        return None;
    }
    let can_move = match game.native_block_property(shaft, "part")?.as_str() {
        "start" => speed > 0.0,
        "end" => speed < 0.0,
        "middle" => true,
        _ => false,
    };
    Some((facing, speed, can_move, sequence_limit))
}

fn matches_shaft(game: &Game<'_>, at: [i32; 3], facing: Direction) -> bool {
    game.native_block(at) == SHAFT && side(game, at) == Some(facing)
}

pub(super) fn shaft_shape(game: &mut Game<'_>, at: [i32; 3]) {
    let Some(dir) = side(game, at) else {
        return;
    };
    let neighbor = |neighbor: Direction| matches_shaft(game, offset(at, neighbor.normal()), dir);
    let part = match (neighbor(dir.opposite()), neighbor(dir)) {
        (true, true) => "middle",
        (false, true) => "start",
        (true, false) => "end",
        _ => "single",
    };
    game.native_set_block_property_with(at, "part", part, 2);
}

pub(super) fn power_shafts(game: &mut Game<'_>) {
    let ticking = game.block_ticking_area();
    let unloaded_networks: Vec<_> = game
        .world
        .block_entity_tickers()
        .iter()
        .filter_map(|entry| {
            let (x, y, z) = entry.0;
            let pos = [x, y, z];
            (ticking(x, z)
                && game.native_block(pos) == SHAFT
                && mod_entity(game, pos).is_some_and(|entity| entity.data.is_empty()))
            .then_some(pos)
        })
        .collect();
    for pos in unloaded_networks {
        // Gantry shafts have no kinetic ticker. Rebuild their saved network on
        // load so a running carriage can resume after a world reopen.
        super::create_machines::refresh_connected_network(game, pos);
    }
    let runs: Vec<_> = game
        .world
        .block_entity_tickers()
        .iter()
        .filter_map(|entry| {
            let (x, y, z) = entry.0;
            let pos = [x, y, z];
            if !ticking(x, z) || game.native_block(pos) != SHAFT {
                return None;
            }
            let face = side(game, pos)?;
            (!matches_shaft(game, offset(pos, face.opposite().normal()), face))
                .then_some((pos, face))
        })
        .collect();
    let dimension = game.native_dimension();
    for (first, facing) in runs {
        let axis = facing.normal();
        let mut run = Vec::new();
        let mut pos = first;
        while matches_shaft(game, pos, facing) {
            run.push(pos);
            pos = offset(pos, axis);
        }
        let powered = run
            .iter()
            .any(|&at| game.native_neighbor_signal(dimension, at) != 0);
        for at in run {
            game.native_set_block_property_with(
                at,
                "powered",
                if powered { "true" } else { "false" },
                flags::UPDATE_CLIENTS,
            );
        }
    }
}

fn space_for(
    game: &Game<'_>,
    anchor: [i32; 3],
    blocks: &[Compound],
    moving: &[[i32; 3]],
    motion: [i32; 3],
) -> bool {
    blocks.iter().all(|saved| {
        let at = offset(anchor, relative(saved));
        let state = game.world.block(at[0], at[1], at[2]);
        moving.contains(&at)
            || game.res.behaviours().is_replaceable(state)
            || super::create_drill::allows_obstruction(game, blocks, anchor, at, motion)
    })
}

fn assemble(game: &mut Game<'_>, origin: [i32; 3]) {
    let Some(body) = side(game, origin) else {
        return;
    };
    let support = body.opposite().normal();
    let shaft = offset(origin, support);
    let Some((track, speed, true, sequence_limit)) = drive(game, shaft) else {
        return;
    };
    let direction = if speed > 0.0 { track } else { track.opposite() };
    let next = offset(origin, direction.normal());
    let mut blocks = capture_attached(game, shaft, origin, Some(offset(origin, body.normal())));
    let source: Vec<_> = blocks
        .iter()
        .map(|block| offset(origin, relative(block)))
        .collect();
    if blocks.is_empty() || !space_for(game, next, &blocks, &source, direction.normal()) {
        return;
    }
    let dimension = game.native_dimension();
    let Some(air) = game.native_default_state("minecraft:air") else {
        return;
    };
    let Some(id) = game.native_summon(
        dimension,
        "minecraft:marker",
        origin.map(f64::from),
        Compound::from([
            (MOVING.into(), Tag::Compound(Compound::new())),
            (
                "Tags".into(),
                Tag::List(vec![Tag::String("create_gantry_payload".into())]),
            ),
        ]),
    ) else {
        return;
    };
    let glue = attached_glue(game, &source, origin);
    for world in source {
        game.native_set_block(
            dimension,
            world,
            air,
            flags::UPDATE_ALL | flags::UPDATE_SKIP_BLOCK_ENTITY_SIDEEFFECTS,
        );
    }
    for block in &mut blocks {
        display(game, origin, block, 1, 0.0);
    }
    let mut data = Compound::from([
        ("Age".into(), Tag::Int(0)),
        ("Glue".into(), Tag::List(glue)),
        ("Origin".into(), Tag::IntArray(origin.to_vec())),
        ("Axis".into(), Tag::IntArray(track.normal().to_vec())),
        ("Support".into(), Tag::IntArray(support.to_vec())),
    ]);
    set_num(&mut data, "Offset", 0.0);
    if let Some(limit) = sequence_limit {
        set_num(&mut data, "SequencedOffsetLimit", f64::from(limit));
    }
    save(game, id, data, blocks);
}

fn save(game: &mut Game<'_>, id: u32, mut data: Compound, blocks: Vec<Compound>) {
    data.insert(
        "Blocks".into(),
        Tag::List(blocks.into_iter().map(Tag::Compound).collect()),
    );
    if let Some(Tag::Compound(tag)) = game.persist.raw.get_mut(&id) {
        tag.insert(MOVING.into(), Tag::Compound(data));
    }
}

fn target(origin: [i32; 3], axis: [i32; 3], distance: f64) -> [i32; 3] {
    std::array::from_fn(|i| {
        (f64::from(origin[i]) + f64::from(axis[i]) * distance + 0.5).floor() as i32
    })
}

fn move_one(game: &mut Game<'_>, id: u32, mut data: Compound) {
    let (Some(origin), Some(axis), Some(support)) = (
        pos(&data, "Origin"),
        pos(&data, "Axis"),
        pos(&data, "Support"),
    ) else {
        return;
    };
    let Some(Tag::List(saved)) = data.remove(&"Blocks".into()) else {
        return;
    };
    let mut blocks: Vec<_> = saved
        .into_iter()
        .filter_map(|entry| match entry {
            Tag::Compound(block) => Some(block),
            _ => None,
        })
        .collect();
    let age = int(&data, "Age").unwrap_or(0).saturating_add(1);
    data.insert("Age".into(), Tag::Int(age));
    let distance = number(&data, "Offset");
    let current = target(origin, axis, distance);
    let dimension = game.native_dimension();
    let mut next = distance;
    let mut stop = true;
    let sequence_limit = match data.get(&"SequencedOffsetLimit".into()) {
        Some(Tag::Double(bits)) => Some(f64::from_bits(*bits)),
        _ => None,
    };
    if let Some((direction, speed, allowed, _)) = drive(game, offset(current, support))
        && direction.normal() == axis
    {
        let raw_change = if age > 2 { f64::from(speed) } else { 0.0 };
        let change = sequence_limit.map_or(raw_change, |limit| raw_change.clamp(-limit, limit));
        let candidate = distance + change;
        let next_block = target(origin, axis, candidate);
        let grid_offset = (0..3)
            .map(|i| f64::from(current[i] - origin[i]) * f64::from(axis[i]))
            .sum::<f64>();
        // The pinion compares the next world coordinate with the center
        // of its current shaft block. Equality counts as crossing west/down/north.
        let axis_sign = f64::from(axis.into_iter().sum::<i32>());
        let crossing = change != 0.0
            && (grid_offset * axis_sign < candidate * axis_sign)
                != (change * axis_sign < 0.0);
        if (allowed || !crossing)
            && space_for(
                game,
                next_block,
                &blocks,
                &[],
                axis.map(|step| step * if change > 0.0 { 1 } else { -1 }),
            )
        {
            next = candidate;
            stop = false;
            if let Some(limit) = sequence_limit {
                set_num(
                    &mut data,
                    "SequencedOffsetLimit",
                    (limit - change.abs()).max(0.0),
                );
            }
        }
    }
    let contact_origin =
        std::array::from_fn(|i| f64::from(origin[i]) + f64::from(axis[i]) * distance);
    let planned_origin =
        std::array::from_fn(|i| f64::from(origin[i]) + f64::from(axis[i]) * next);
    super::create_contact::moving(game, &blocks, contact_origin, &mut data, age > 2 && !stop);
    let previous = number(&data, "PreviousOffset");
    let previous_origin =
        std::array::from_fn(|i| f64::from(origin[i]) + f64::from(axis[i]) * previous);
    super::create_mounted_dispenser::translate_actors(
        game,
        &mut blocks,
        previous_origin,
        contact_origin,
    );
    let drill_stalled = if stop {
        // StopMoving cancels BlockBreakingMovementBehaviour progress before
        // the actor is restored to the world.
        super::create_drill::translate(
            game,
            &mut blocks,
            contact_origin,
            contact_origin,
            1.0,
        );
        false
    } else {
        super::create_drill::translate(
            game,
            &mut blocks,
            contact_origin,
            planned_origin,
            1.0,
        )
    };
    if !stop && (drill_stalled
        || super::create_roller::tick(game, &mut blocks, previous_origin, contact_origin, id)) {
        next = distance;
    }
    if stop && restore(game, current, &blocks, 1, 0.0) {
        if let Some(Tag::List(glue)) = data.remove(&"Glue".into()) {
            move_glue(game, &glue, current.map(f64::from));
        }
        game.native_remove_entity(dimension, id);
        return;
    }
    let location = std::array::from_fn(|i| f64::from(origin[i]) + f64::from(axis[i]) * next);
    game.native_move_entity(dimension, id, location, 0.0, 0.0);
    for block in &mut blocks {
        display(game, origin, block, 1, 0.0);
        if let Some(display_id) = int(block, "Display") {
            game.native_move_entity(dimension, display_id as u32, location, 0.0, 0.0);
        }
    }
    set_num(&mut data, "PreviousOffset", distance);
    set_num(&mut data, "Offset", next);
    save(game, id, data, blocks);
}

pub(super) fn move_existing(game: &mut Game<'_>) {
    let cars: Vec<_> = game
        .others
        .iter()
        .filter_map(|entity| {
            let Tag::Compound(data) = game.persist.raw.get(&entity.id)?.get(MOVING)? else {
                return None;
            };
            Some((entity.id, data.clone()))
        })
        .collect();
    for (id, data) in cars {
        move_one(game, id, data);
    }
}

pub(super) fn assemble_ready(game: &mut Game<'_>) {
    let in_area = game.block_ticking_area();
    let ready: Vec<_> = game
        .world
        .block_entity_tickers()
        .iter()
        .filter_map(|entry| {
            let (x, y, z) = entry.0;
            let at = [x, y, z];
            (in_area(x, z) && mod_entity(game, at).is_some_and(|entity| entity.id == PINION))
                .then_some(at)
        })
        .collect();
    for carriage in ready {
        if game.native_block(carriage) == CARRIAGE {
            assemble(game, carriage);
        }
    }
}
