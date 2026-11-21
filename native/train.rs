use glam::{Quat, Vec3};
use horizon_core::random::RandomSource;
use horizon_world::level::flags;
use horizon_world::nbt::{Compound, Tag};

use super::create_bearing::{capture_from, relative, restore};
use super::create_depot::compound;
use super::create_elevator_doors as doors;
use super::create_elevator_seats as seats;
use super::create_machines::{int, mod_entity, offset, string};
use super::create_station::{LARGE_BOGEY, SMALL_BOGEY, along};
use super::create_train_conductor as conductor;
use super::create_train_portable_items as portable_items;
use super::create_train_schedule_runtime as schedule;
use super::create_train_track::{self, Point, StationRoute};
use super::native_entities::NativeDisplay;
use super::{Game, Hand, Mapping};

pub(super) const CARRIAGE: &str = "CreateTrain";
const PART_OF: &str = "CreateTrainPartOf";
pub(super) const CONTROLS: &str = "create:controls";
const ACCELERATION: f64 = (3.0_f32 / 400.0) as f64;
const MAX_SPEED: f64 = (28.0_f32 / 20.0) as f64;
const TOP_SPEED: f64 = (MAX_SPEED as f32 * 0.75) as f64;
const TURN_SPEED: f64 = (14.0_f32 / 20.0) as f64;

pub(super) fn coords(data: &Compound, key: &str) -> Option<[i32; 3]> {
    let Tag::IntArray(values) = data.get(&key.into())? else {
        return None;
    };
    values.as_slice().try_into().ok()
}

fn decimal(data: &Compound, key: &str) -> f64 {
    match data.get(&key.into()) {
        Some(Tag::Double(bits)) => f64::from_bits(*bits),
        _ => 0.0,
    }
}

fn number(data: &mut Compound, key: &str, value: f64) {
    data.insert(key.into(), Tag::Double(value.to_bits()));
}

fn anchor(data: &Compound, axis: [i32; 3]) -> Option<[i32; 3]> {
    let track = coords(data, "ArrivedTrack").or_else(|| coords(data, "Track"))?;
    let spacing = if backwards_dock(data) {
        bogey_offsets(data)
            .last()
            .copied()
            .unwrap_or_else(|| int(data, "BogeySpacing").unwrap_or(0))
    } else {
        0
    };
    Some(offset(along(track, axis, 1 + spacing), [0, 1, 0]))
}

fn backwards_dock(data: &Compound) -> bool {
    int(data, "ArrivedBackwards") == Some(1)
}

fn front_point(points: &[Point], backwards: bool) -> Point {
    if backwards {
        points[points.len() - 1].reversed()
    } else {
        points[0]
    }
}

pub(super) fn controls_facing(axis: [i32; 3]) -> &'static str {
    match axis {
        [1, 0, 0] => "east",
        [-1, 0, 0] => "west",
        [0, 0, 1] => "south",
        _ => "north",
    }
}

fn double_ended(data: &Compound, axis: [i32; 3]) -> bool {
    let backward = controls_facing(axis.map(|component| -component));
    matches!(data.get(&"Blocks".into()), Some(Tag::List(blocks)) if blocks.iter().any(|value| {
        let Tag::Compound(block) = value else { return false; };
        state_name(block).as_deref() == Some(CONTROLS)
            && compound(block, "BlockState")
                .and_then(|state| compound(state, "Properties"))
                .is_some_and(|properties| {
                    matches!(properties.get(&"facing".into()), Some(Tag::String(facing)) if facing.to_string_lossy() == backward)
                })
    }))
}

pub(super) fn place_controls(game: &mut Game<'_>, pos: [i32; 3], stack: &crate::items::ItemStack) {
    if stack.item.as_ref() != CONTROLS {
        return;
    }
    let look = super::create_track::face_vector(game.yaw);
    let side = if game.native_sneaking() {
        look
    } else {
        look.scale(-1.0)
    };
    let facing = if side.x.abs() > side.z.abs() {
        if side.x > 0.0 { "east" } else { "west" }
    } else if side.z > 0.0 {
        "south"
    } else {
        "north"
    };
    game.native_set_block_property(pos, "facing", facing);
}

pub(super) fn state_name(block: &Compound) -> Option<String> {
    let Tag::String(name) = compound(block, "BlockState")?.get(&"Name".into())? else {
        return None;
    };
    Some(name.to_string_lossy())
}

pub(super) fn carriage<'g>(game: &'g Game<'_>, id: u32) -> Option<&'g Compound> {
    match game.persist.raw.get(&id)?.get(CARRIAGE)? {
        Tag::Compound(data) => Some(data),
        _ => None,
    }
}

pub(super) fn carriage_mut<'g>(game: &'g mut Game<'_>, id: u32) -> Option<&'g mut Compound> {
    let Tag::Compound(entity) = game.persist.raw.get_mut(&id)? else {
        return None;
    };
    let Tag::Compound(carriage) = entity.get_mut(&CARRIAGE.into())? else {
        return None;
    };
    Some(carriage)
}

pub(super) fn restore_door_animation(game: &mut Game<'_>, tag: &mut Tag, kind: &str) {
    let Tag::Compound(raw) = tag else { return; };
    if kind == "minecraft:interaction" {
        let Some(Tag::IntArray(uuid)) = raw.get(&"UUID".into()) else { return; };
        let Ok(uuid) = <[i32; 4]>::try_from(uuid.as_slice()) else { return; };
        let Some(Tag::Compound(train)) = raw.get_mut(&CARRIAGE.into()) else { return; };
        let saved_pose = Pose::for_collision(game, train);
        let Some(Tag::List(blocks)) = train.get_mut(&"Blocks".into()) else { return; };
        let mut sliding = false;
        for block in blocks.iter_mut() {
            if let Tag::Compound(block) = block
                && state_name(block).as_deref().is_some_and(doors::sliding)
            {
                doors::restore_train_panel(block);
                sliding = true;
            }
        }
        if sliding {
            // Some saved display parts can load before their carriage.
            for (index, part) in parts_for_uuid(game, uuid) {
                if let Some(Tag::Compound(display)) = game.persist.raw.get_mut(&part) {
                    restore_door_display(blocks, index, display, saved_pose);
                }
            }
        }
    } else if kind == "minecraft:block_display" {
        let (Some(Tag::IntArray(owner)), Some(index)) =
            (raw.get(&PART_OF.into()), int(raw, "CreatePartIndex"))
        else { return; };
        let Ok(owner) = owner.as_slice().try_into() else { return; };
        let Some(train) = carriage_by_uuid(game, owner).and_then(|id| carriage(game, id)) else { return; };
        let Some(Tag::List(blocks)) = train.get(&"Blocks".into()) else { return; };
        restore_door_display(blocks, index, raw, Pose::for_collision(game, train));
    }
}

fn restore_door_display(blocks: &[Tag], index: i32, raw: &mut Compound, saved_pose: Option<Pose>) {
    if index < 0 || index % 10 != 0 {
        return;
    }
    let Some(Tag::Compound(block)) = blocks.get((index / 10) as usize) else { return; };
    let Some(name) = state_name(block).filter(|name| doors::sliding(name)) else { return; };
    let Some((_, local_pose)) = doors::train_visual(block) else { return; };
    let Some(Tag::Compound(transform)) = raw.get_mut(&"transformation".into()) else { return; };
    let rotation = |key: &str| {
        let Some(Tag::List(values)) = transform.get(&key.into()) else { return None; };
        Some(Quat::from_array(std::array::from_fn(|i| match values.get(i) {
            Some(Tag::Float(bits)) => f32::from_bits(*bits),
            _ => 0.0,
        })))
    };
    let Some(mut parent) = rotation("left_rotation") else { return; };
    if doors::folding_model(&name).is_some() && rotation("right_rotation") == Some(Quat::IDENTITY) {
        // Earlier folding renders stored the combined rotation in the left slot.
        if let Some(pose) = saved_pose {
            parent = pose.rotation;
        }
    }
    if !parent.is_normalized() {
        return;
    }
    let translation = (parent * Vec3::from_array(local_pose.translation)).to_array();
    transform.insert(
        "translation".into(),
        Tag::List(translation.into_iter().map(|value| Tag::Float(value.to_bits())).collect()),
    );
    transform.insert(
        "left_rotation".into(),
        Tag::List(parent.to_array().into_iter().map(|value| Tag::Float(value.to_bits())).collect()),
    );
    transform.insert(
        "right_rotation".into(),
        Tag::List(local_pose.left_rotation.into_iter().map(|value| Tag::Float(value.to_bits())).collect()),
    );
    raw.insert("interpolation_duration".into(), Tag::Int(0));
}

fn carriage_by_uuid(game: &Game<'_>, uuid: [i32; 4]) -> Option<u32> {
    game.others.iter().find_map(|entity| {
        (game.persist.uuid_of(entity.id) == Some(uuid) && carriage(game, entity.id).is_some())
            .then_some(entity.id)
    })
}

pub(super) fn has_seat(game: &Game<'_>, train: [i32; 4], at: [i32; 3]) -> bool {
    let Some(Tag::List(blocks)) = carriage_by_uuid(game, train)
        .and_then(|id| carriage(game, id))
        .and_then(|data| data.get(&"Blocks".into()))
    else {
        return false;
    };
    blocks.iter().any(|block| matches!(block, Tag::Compound(block)
        if relative(block) == at && state_name(block).as_deref().is_some_and(super::create_elevator_seats::is_seat)))
}

pub(super) fn clear_seat_occupant(game: &mut Game<'_>, train: [i32; 4], at: [i32; 3]) {
    if let Some(id) = carriage_by_uuid(game, train)
        && let Some(Tag::Compound(entity)) = game.persist.raw.get_mut(&id)
        && let Some(Tag::Compound(data)) = entity.get_mut(&CARRIAGE.into())
        && let Some(Tag::List(blocks)) = data.get_mut(&"Blocks".into())
    {
        for block in blocks {
            if let Tag::Compound(block) = block
                && relative(block) == at
            {
                block.remove(&"SeatOccupant".into());
            }
        }
    }
}

fn driver(data: &Compound) -> Option<&[i32]> {
    let Tag::IntArray(uuid) = data.get(&"Driver".into())? else {
        return None;
    };
    Some(uuid)
}

pub(super) fn at_station(game: &Game<'_>, station: [i32; 3]) -> Option<u32> {
    game.others.iter().find_map(|entity| {
        let data = carriage(game, entity.id)?;
        let dock = coords(data, "ArrivedStation").or_else(|| coords(data, "Station"))?;
        let track = coords(data, "Track")?;
        let axis = coords(data, "Axis")?;
        let dock_track = coords(data, "ArrivedTrack").unwrap_or(track);
        (dock == station
            && decimal(data, "Speed") == 0.0
            && front_point(&track_points(game, data, track, axis), backwards_dock(data))
                .location()
                .distance(
                    Point::start(dock_track, coords(data, "ArrivedAxis").unwrap_or(axis), 0.5)
                        .location(),
                )
                < 1.0e-6)
            .then_some(entity.id)
    })
}

pub(super) fn assemble(
    game: &mut Game<'_>,
    station: [i32; 3],
    origin: [i32; 3],
    axis: [i32; 3],
    bogeys: &[i32],
) -> Result<(), &'static str> {
    if bogeys.first() != Some(&1) {
        return Err("Place the front bogey next to the station");
    }
    if bogeys.windows(2).any(|pair| pair[1] - pair[0] < 3) {
        return Err("Bogeys must be at least three blocks apart");
    }
    if bogeys.len() > super::create_station::MAX_BOGEYS {
        return Err("A train can use at most twenty bogeys");
    }
    let anchor = offset(along(origin, axis, 1), [0, 1, 0]);
    let mut blocks = Vec::new();
    let mut seen = std::collections::HashSet::new();
    for &index in bogeys {
        let bogey_pos = offset(along(origin, axis, index), [0, 1, 0]);
        let component = capture_from(game, origin, anchor, [bogey_pos]);
        let mut component_bogeys: Vec<_> = component
            .iter()
            .filter_map(|block| {
                matches!(
                    state_name(block).as_deref(),
                    Some(SMALL_BOGEY | LARGE_BOGEY)
                )
                .then(|| relative(block))
                .and_then(|position| {
                    bogeys
                        .iter()
                        .position(|&bogey| position == axis.map(|step| step * (bogey - 1)))
                })
            })
            .collect();
        component_bogeys.sort_unstable();
        component_bogeys.dedup();
        if component_bogeys.is_empty()
            || component_bogeys.len() > 2
            || component_bogeys
                .windows(2)
                .any(|pair| pair[1] != pair[0] + 1)
        {
            return Err("Each glued carriage must contain one or two bogeys");
        }
        for block in component {
            if seen.insert(relative(&block)) {
                blocks.push(block);
            }
        }
    }
    if bogeys.iter().any(|&index| {
        !blocks
            .iter()
            .any(|block| relative(block) == axis.map(|step| step * (index - 1)))
    }) {
        return Err("Glue each carriage to its bogeys");
    }
    super::create_elevator_collision::capture(game, &mut blocks, anchor);
    doors::capture(&mut blocks);
    let mut attached = Vec::new();
    let mut controls = None;
    let facing = controls_facing(axis);
    for block in &blocks {
        match state_name(block).as_deref() {
            Some(SMALL_BOGEY | LARGE_BOGEY) => attached.push(relative(block)),
            Some(CONTROLS) => {
                let Some(state) =
                    compound(block, "BlockState").and_then(|state| compound(state, "Properties"))
                else {
                    continue;
                };
                if matches!(state.get(&"facing".into()), Some(Tag::String(dir)) if dir.to_string_lossy() == facing)
                {
                    controls = Some(relative(block));
                }
            }
            Some(super::create_track::TRACK | super::create_station::STATION) => {
                return Err("Tracks and stations must stay on the ground");
            }
            _ => (),
        }
    }
    if attached.len() != bogeys.len()
        || !bogeys
            .iter()
            .all(|&i| attached.contains(&axis.map(|step| step * (i - 1))))
    {
        return Err("Glue the carriage to its bogeys");
    }
    let Some(controls) = controls else {
        return Err("Attach Train Controls facing the front of the carriage");
    };
    let Some(air) = game.native_default_state("minecraft:air") else {
        return Err("The world could not assemble the carriage");
    };
    conductor::capture(game, anchor, axis, &mut blocks);
    let offsets: Vec<_> = bogeys.iter().map(|distance| distance - 1).collect();
    let spacing = offsets.get(1).copied().unwrap_or(0);
    let mut data = Compound::from([
        ("Axis".into(), Tag::IntArray(axis.to_vec())),
        ("Track".into(), Tag::IntArray(origin.to_vec())),
        ("Station".into(), Tag::IntArray(station.to_vec())),
        ("Controls".into(), Tag::IntArray(controls.to_vec())),
        ("BogeySpacing".into(), Tag::Int(spacing)),
        ("BogeyOffsets".into(), Tag::IntArray(offsets.clone())),
        (
            "Blocks".into(),
            Tag::List(blocks.iter().cloned().map(Tag::Compound).collect()),
        ),
    ]);
    number(&mut data, "Speed", 0.0);
    number(&mut data, "Distance", -0.0);
    let points = starts_for(&data, origin, axis, 0.0);
    wheels(&mut data, origin, axis, &points);
    let pose = Pose::new(axis, &points);
    let at = pose.controls(controls);
    let dimension = game.native_dimension();
    let Some(id) = game.native_summon(
        dimension,
        "minecraft:interaction",
        at,
        Compound::from([
            (CARRIAGE.into(), Tag::Compound(data)),
            ("width".into(), Tag::Float(1.0_f32.to_bits())),
            ("height".into(), Tag::Float(1.0_f32.to_bits())),
            ("response".into(), Tag::Byte(1)),
        ]),
    ) else {
        return Err("The world could not create the carriage");
    };
    for block in &blocks {
        game.native_set_block(
            dimension,
            offset(anchor, relative(block)),
            air,
            flags::UPDATE_ALL,
        );
    }
    seats::attach_train(game, id, anchor, &blocks);
    draw(game, id, &blocks, axis, &offsets, 0.0, &points, false);
    Ok(())
}

pub(super) fn disassemble(game: &mut Game<'_>, id: u32) -> bool {
    let Some(data) = carriage(game, id).cloned() else {
        return false;
    };
    let Some(original_axis) = coords(&data, "Axis") else {
        return false;
    };
    let dock_axis = coords(&data, "ArrivedAxis").unwrap_or(original_axis);
    let Some(anchor) = anchor(&data, dock_axis) else {
        return false;
    };
    let orientation = if backwards_dock(&data) {
        dock_axis.map(|axis| -axis)
    } else {
        dock_axis
    };
    let dot = f64::from(original_axis[0] * orientation[0] + original_axis[2] * orientation[2]);
    let cross = f64::from(original_axis[2] * orientation[0] - original_axis[0] * orientation[2]);
    let angle = cross.atan2(dot);
    let Some(Tag::List(blocks)) = data.get(&"Blocks".into()) else {
        return false;
    };
    let blocks: Vec<_> = blocks
        .iter()
        .filter_map(|block| match block {
            Tag::Compound(block) => Some(block.clone()),
            _ => None,
        })
        .map(|mut block| {
            if original_axis[0].abs() != dock_axis[0].abs()
                && matches!(
                    state_name(&block).as_deref(),
                    Some(SMALL_BOGEY | LARGE_BOGEY)
                )
                && let Some(Tag::Compound(state)) = block.get_mut(&"BlockState".into())
                && let Some(Tag::Compound(properties)) = state.get_mut(&"Properties".into())
            {
                let axis = if dock_axis[0] == 0 { "z" } else { "x" };
                properties.insert("axis".into(), Tag::String(axis.into()));
            }
            block
        })
        .collect();
    if !restore(game, anchor, &blocks, 1, angle) {
        return false;
    }
    conductor::restore_riders(game, anchor, &blocks, angle);
    seats::land_train(game, id, anchor, &blocks, angle);
    let station = coords(&data, "ArrivedStation").or_else(|| coords(&data, "Station"));
    if let Some(station) = station {
        conductor::drop_assigned(game, &data, station);
    }
    let dimension = game.native_dimension();
    let parts = parts(game, id);
    for (_, part) in parts {
        game.native_remove_entity(dimension, part);
    }
    game.native_remove_entity(dimension, id)
}

fn bogey_offsets(data: &Compound) -> Vec<i32> {
    match data.get(&"BogeyOffsets".into()) {
        Some(Tag::IntArray(offsets)) if !offsets.is_empty() => offsets.clone(),
        _ => {
            let spacing = int(data, "BogeySpacing").unwrap_or(0);
            if spacing > 0 {
                vec![0, spacing]
            } else {
                vec![0]
            }
        }
    }
}

fn starts_for(data: &Compound, origin: [i32; 3], axis: [i32; 3], distance: f64) -> Vec<Point> {
    bogey_offsets(data)
        .into_iter()
        .flat_map(|offset| [0.5 + f64::from(offset), 2.5 + f64::from(offset)])
        .map(|at| Point::start(origin, axis, at - distance))
        .collect()
}

fn track_points(game: &Game<'_>, data: &Compound, origin: [i32; 3], axis: [i32; 3]) -> Vec<Point> {
    if let Some(Tag::List(tags)) = data.get(&"TrackPoints".into()) {
        if let Some(points) = tags
            .iter()
            .map(|tag| Point::read(game, tag))
            .collect::<Option<Vec<_>>>()
            && points.len() >= 2
            && points.len() % 2 == 0
        {
            return points;
        }
    }
    starts_for(data, origin, axis, decimal(data, "Distance"))
}

pub(super) fn wheel_positions<'g>(
    game: &'g Game<'_>,
    exclude: Option<u32>,
) -> impl Iterator<Item = Vec<Point>> + 'g {
    wheel_positions_with_id(game, exclude).map(|(_, wheels)| wheels)
}

pub(super) fn wheel_positions_with_id<'g>(
    game: &'g Game<'_>,
    exclude: Option<u32>,
) -> impl Iterator<Item = (u32, Vec<Point>)> + 'g {
    game.others.iter().filter_map(move |entity| {
        if exclude == Some(entity.id) {
            return None;
        }
        let data = carriage(game, entity.id)?;
        let origin = coords(data, "Track")?;
        let axis = coords(data, "Axis")?;
        Some((entity.id, track_points(game, data, origin, axis)))
    })
}

const SIGNAL_RESERVATIONS: &str = "SignalReservations";

#[derive(Clone, Copy)]
struct SignalReservation {
    pos: [i32; 3],
    since: i64,
    until: Option<i64>,
}

fn reservations(data: &Compound) -> impl Iterator<Item = SignalReservation> + '_ {
    let values = match data.get(&SIGNAL_RESERVATIONS.into()) {
        Some(Tag::List(values)) => values.as_slice(),
        _ => &[],
    };
    values.iter().filter_map(|entry| {
        let Tag::Compound(entry) = entry else {
            return None;
        };
        let Tag::Long(since) = entry.get(&"Since".into())? else {
            return None;
        };
        let until = match entry.get(&"Until".into()) {
            Some(Tag::Long(value)) => Some(*value),
            _ => None,
        };
        Some(SignalReservation {
            pos: coords(entry, "Signal")?,
            since: *since,
            until,
        })
    })
}

pub(super) fn reservation_age(game: &Game<'_>, pos: [i32; 3], exclude: Option<u32>) -> Option<i64> {
    let now = game.world.game_time;
    game.others
        .iter()
        .filter(|entity| exclude != Some(entity.id))
        .filter_map(|entity| carriage(game, entity.id))
        .flat_map(reservations)
        .filter(|entry| entry.pos == pos && entry.until.is_none_or(|until| until > now))
        .map(|entry| now - entry.since)
        .max()
}

fn update_reservations(
    data: &mut Compound,
    planned: Vec<super::create_train_signal::SignalStop>,
    travelled: f64,
    now: i64,
) {
    let previous: std::collections::HashMap<_, _> =
        reservations(data).map(|entry| (entry.pos, entry)).collect();
    let mut entries: Vec<_> = previous
        .values()
        .filter(|entry| entry.until.is_some_and(|until| until > now))
        .copied()
        .collect();

    for signal in planned {
        if entries.iter().any(|entry| entry.pos == signal.pos) {
            continue;
        }
        let since = previous.get(&signal.pos).map_or(now, |entry| entry.since);
        // The reserved section becomes occupied at the same boundary. Keep the
        // lamp red until the occupied section is published two ticks later.
        let until = (signal.distance <= travelled).then_some(now + 2);
        entries.push(SignalReservation {
            pos: signal.pos,
            since,
            until,
        });
    }
    if entries.is_empty() {
        data.remove(&SIGNAL_RESERVATIONS.into());
        return;
    }
    let tags = entries
        .into_iter()
        .map(|entry| {
            let mut tag = Compound::from([
                ("Signal".into(), Tag::IntArray(entry.pos.to_vec())),
                ("Since".into(), Tag::Long(entry.since)),
            ]);
            if let Some(until) = entry.until {
                tag.insert("Until".into(), Tag::Long(until));
            }
            Tag::Compound(tag)
        })
        .collect();
    data.insert(SIGNAL_RESERVATIONS.into(), Tag::List(tags));
}

fn wheels(data: &mut Compound, origin: [i32; 3], axis: [i32; 3], points: &[Point]) {
    let points_xyz: Vec<_> = points
        .iter()
        .map(|point| {
            let at = point.location().components();
            std::array::from_fn::<_, 3, _>(|i| at[i] - f64::from(origin[i]))
        })
        .collect();
    data.insert(
        "TrackPoints".into(),
        Tag::List(points.iter().map(|p| p.tag()).collect()),
    );
    data.insert(
        "WheelPoints".into(),
        Tag::List(
            points_xyz
                .iter()
                .map(|at| {
                    let along =
                        (at[0] - 0.5) * f64::from(axis[0]) + (at[2] - 0.5) * f64::from(axis[2]);
                    Tag::Double((0.5 + along).to_bits())
                })
                .collect(),
        ),
    );
    data.insert(
        "WheelPointsXYZ".into(),
        Tag::List(
            points_xyz
                .into_iter()
                .map(|at| Tag::List(at.into_iter().map(|v| Tag::Double(v.to_bits())).collect()))
                .collect(),
        ),
    );
}

#[derive(Clone, Copy)]
pub(super) struct Pose {
    pivot: [f64; 3],
    pub(super) rotation: Quat,
}

fn direction(from: [f64; 3], to: [f64; 3]) -> Vec3 {
    Vec3::from_array(std::array::from_fn(|i| (to[i] - from[i]) as f32)).normalize()
}

impl Pose {
    pub(super) fn for_collision(game: &Game<'_>, data: &Compound) -> Option<Self> {
        let axis = coords(data, "Axis")?;
        let origin = coords(data, "Track")?;
        Some(Self::new(axis, &track_points(game, data, origin, axis)))
    }

    pub(super) fn for_port_scan(game: &Game<'_>, data: &Compound) -> Option<Self> {
        if decimal(data, "Speed").abs() > 0.25 {
            return None;
        }
        let axis = coords(data, "Axis")?;
        let origin = coords(data, "Track")?;
        Some(Self::new(axis, &track_points(game, data, origin, axis)))
    }

    fn new(axis: [i32; 3], points: &[Point]) -> Self {
        let pivot = create_train_track::center(&points[..2]).components();
        let heading = if points.len() > 2 {
            direction(
                pivot,
                create_train_track::center(&points[points.len() - 2..]).components(),
            )
        } else {
            direction(
                points[0].location().components(),
                points[1].location().components(),
            )
        };
        Self {
            pivot,
            rotation: Quat::from_rotation_arc(Vec3::from_array(axis.map(|v| v as f32)), heading),
        }
    }

    pub(super) fn position(self, relative: Vec3) -> [f64; 3] {
        let delta = (self.rotation * relative).to_array();
        std::array::from_fn(|i| self.pivot[i] + f64::from(delta[i]))
    }

    fn controls(self, relative: [i32; 3]) -> [f64; 3] {
        self.position(Vec3::from_array(relative.map(|v| v as f32)))
    }

    fn block(self, relative: [i32; 3]) -> [f64; 3] {
        self.position(Vec3::from_array(relative.map(|v| v as f32)) - Vec3::new(0.5, 0.0, 0.5))
    }
}

fn parts(game: &Game<'_>, id: u32) -> Vec<(i32, u32)> {
    game.persist.uuid_of(id).map_or_else(Vec::new, |uuid| parts_for_uuid(game, uuid))
}

fn parts_for_uuid(game: &Game<'_>, uuid: [i32; 4]) -> Vec<(i32, u32)> {
    game.others
        .iter()
        .filter_map(|other| {
            let data = game.persist.raw.get(&other.id)?;
            let Some(Tag::IntArray(owner)) = data.get(PART_OF) else {
                return None;
            };
            (owner.as_slice() == uuid).then_some((int_tag(data, "CreatePartIndex")?, other.id))
        })
        .collect()
}

fn int_tag(data: &Tag, name: &str) -> Option<i32> {
    match data.get(name)? {
        Tag::Int(value) => Some(*value),
        _ => None,
    }
}

fn draw(
    game: &mut Game<'_>,
    id: u32,
    blocks: &[Compound],
    axis: [i32; 3],
    bogey_offsets: &[i32],
    distance: f64,
    points: &[Point],
    ports_only: bool,
) {
    let uuid = game.uuid_for(id);
    let dimension = game.native_dimension();
    let existing = parts(game, id);
    let pose = Pose::new(axis, points);
    let default_heading = if axis[0] == 0 {
        Quat::IDENTITY
    } else {
        Quat::from_rotation_y(std::f32::consts::FRAC_PI_2)
    };
    for (index, block) in blocks.iter().enumerate() {
        let Some(state) = compound(block, "BlockState") else {
            continue;
        };
        let kind = state_name(block);
        let is_port = matches!(
            kind.as_deref(),
            Some(portable_items::ITEM | portable_items::FLUID)
        );
        let is_door = kind.as_deref().is_some_and(doors::sliding);
        let is_trapdoor = kind.as_deref().is_some_and(train_trapdoor);
        if ports_only && !is_port {
            continue;
        }
        let mut state = state.clone();
        if kind.as_deref() == Some(CONTROLS) {
            if let Some(Tag::Compound(properties)) = state.get_mut(&"Properties".into()) {
                properties.insert("open".into(), Tag::String("true".into()));
                properties.insert("virtual".into(), Tag::String("true".into()));
            }
        }
        let relative = relative(block);
        let bogey = matches!(kind.as_deref(), Some(SMALL_BOGEY | LARGE_BOGEY));
        let (pos, rotation) = if bogey {
            let offset = relative[0] * axis[0] + relative[2] * axis[2];
            let index = bogey_offsets
                .iter()
                .position(|candidate| *candidate == offset)
                .unwrap_or(0)
                * 2;
            let pose = Pose::new(axis, &points[index..index + 2]);
            (pose.block([0; 3]), pose.rotation)
        } else {
            (pose.block(relative), pose.rotation)
        };
        let heading = rotation * default_heading;
        let mut show = |sub: i32, state: &Compound, pose: NativeDisplay| {
            let index = index as i32 * 10 + sub;
            let part = existing
                .iter()
                .find(|(part_index, _)| *part_index == index)
                .map(|(_, part)| *part);
            let id = if let Some(id) = part {
                game.native_move_entity(dimension, id, pos, 0.0, 0.0);
                if (is_port || is_door)
                    && let Some(Tag::Compound(display)) = game.persist.raw.get_mut(&id)
                {
                    let tag = Tag::Compound(state.clone());
                    if display.get(&"block_state".into()) != Some(&tag) {
                        display.insert("block_state".into(), tag);
                    }
                }
                Some(id)
            } else {
                game.native_summon(
                    dimension,
                    "minecraft:block_display",
                    pos,
                    Compound::from([
                        ("block_state".into(), Tag::Compound(state.clone())),
                        (PART_OF.into(), Tag::IntArray(uuid.to_vec())),
                        ("CreatePartIndex".into(), Tag::Int(index)),
                    ]),
                )
            };
            if let Some(id) = id {
                game.native_set_display(dimension, id, &pose);
            }
        };
        match kind.as_deref() {
            Some(kind @ (portable_items::ITEM | portable_items::FLUID)) => {
                super::create_train_portable_visuals::draw_carriage_port(
                    kind, block, state, rotation, &mut show,
                );
            }
            Some(kind @ (SMALL_BOGEY | LARGE_BOGEY)) => {
                let large = kind == LARGE_BOGEY;
                let wheel_radius = if large { 12.5 } else { 6.5 } / 16.0;
                let wheel_angle = ((-distance * f64::from(axis[0] + axis[2]) / wheel_radius)
                    .to_degrees()
                    % 360.0) as f32;
                for (sub, part) in super::create_bogey::parts(large, wheel_angle)
                    .iter()
                    .enumerate()
                {
                    let model = if let Some(dir) = part.model.strip_prefix("shaft_") {
                        Compound::from([
                            ("Name".into(), Tag::String("create:shaft".into())),
                            (
                                "Properties".into(),
                                Tag::Compound(Compound::from([(
                                    "axis".into(),
                                    Tag::String(dir.into()),
                                )])),
                            ),
                        ])
                    } else {
                        Compound::from([(
                            "Name".into(),
                            Tag::String(format!("create:carriage_{}", part.model).as_str().into()),
                        )])
                    };
                    let spin =
                        Quat::from_axis_angle(Vec3::AXES[part.axis], part.angle.to_radians());
                    let pivot = Vec3::from_array(part.pivot);
                    let translation = Vec3::new(0.5, super::create_bogey::Y_OFFSET, 0.5)
                        + heading * (Vec3::from_array(part.at) + pivot - spin * pivot);
                    show(
                        sub as i32,
                        &model,
                        NativeDisplay {
                            translation: translation.to_array(),
                            left_rotation: (heading * spin).to_array(),
                            interpolation: 1,
                            teleport: 1,
                            ..NativeDisplay::default()
                        },
                    );
                }
                show(
                    9,
                    &state,
                    NativeDisplay {
                        teleport: 1,
                        ..NativeDisplay::default()
                    },
                );
            }
            _ => {
                let visual = doors::train_visual(block);
                let mut display = visual
                    .as_ref()
                    .map_or_else(NativeDisplay::default, |(_, pose)| *pose);
                display.translation = (rotation * Vec3::from_array(display.translation)).to_array();
                // Keep carriage rotation separate so a cold load can restore the fold.
                display.right_rotation = display.left_rotation;
                display.left_rotation = rotation.to_array();
                display.teleport = 1;
                display.interpolation = 1;
                show(0, visual.as_ref().map_or(&state, |(state, _)| state), display);
                if kind.as_deref().and_then(doors::folding_model).is_some() {
                    // A folded pane uses a synthetic model and a local rotation.
                    // Give the guest's exact ray picker the original door state and carriage pose.
                    show(
                        2,
                        &state,
                        NativeDisplay {
                            left_rotation: rotation.to_array(),
                            scale: [0.0; 3],
                            teleport: 1,
                            ..NativeDisplay::default()
                        },
                    );
                }
            }
        }
        if is_trapdoor {
            draw_trapdoor_proxies(game, id, index, block, pose, &existing);
        }
        if is_door {
            draw_train_door_proxy(game, id, index, block, pose, &existing);
        }
    }
}

fn train_trapdoor(name: &str) -> bool {
    matches!(
        name,
        "create:train_trapdoor" | "create:framed_glass_trapdoor"
    )
}

fn trapdoor_state(block: &Compound) -> Option<(bool, bool, String)> {
    let state = compound(block, "BlockState")?;
    let props = compound(state, "Properties")?;
    Some((
        string(props, "open").as_deref() == Some("true"),
        string(props, "half").as_deref() == Some("top"),
        string(props, "facing")?,
    ))
}

fn draw_trapdoor_proxies(
    game: &mut Game<'_>,
    train: u32,
    index: usize,
    block: &Compound,
    pose: Pose,
    existing: &[(i32, u32)],
) {
    let Some((open, top, facing)) = trapdoor_state(block) else {
        return;
    };
    let uuid = game.uuid_for(train);
    let dimension = game.native_dimension();
    let rel = relative(block);
    for strip in 0..6 {
        let part_index = index as i32 * 10 + 1 + strip;
        let old = existing
            .iter()
            .find(|(idx, _)| *idx == part_index)
            .map(|(_, id)| *id);
        let needed = open || strip == 0;
        let valid = old.is_some_and(|id| {
            game.persist
                .raw
                .get(&id)
                .is_some_and(|tag| matches!(tag, Tag::Compound(tag) if int(tag, "CreateTrainTrapdoorOpen") == Some(i32::from(open))))
        });
        if let Some(id) = old.filter(|_| !needed || !valid) {
            game.native_remove_entity(dimension, id);
        }
        if !needed {
            continue;
        }
        let mut point = Vec3::from_array(rel.map(|v| v as f32)) - Vec3::new(0.5, 0.0, 0.5);
        let (width, height) = if open {
            let along = 0.09375 + strip as f32 * 0.1625;
            match facing.as_str() {
                "north" => {
                    point.x += along;
                    point.z += 0.90625;
                }
                "south" => {
                    point.x += along;
                    point.z += 0.09375;
                }
                "west" => {
                    point.x += 0.90625;
                    point.z += along;
                }
                "east" => {
                    point.x += 0.09375;
                    point.z += along;
                }
                _ => continue,
            }
            (0.1875_f32, 1.0_f32)
        } else {
            point.x += 0.5;
            point.z += 0.5;
            if top {
                point.y += 0.8125;
            }
            (1.0_f32, 0.1875_f32)
        };
        let at = pose.position(point);
        if let Some(id) = old.filter(|_| valid) {
            game.native_move_entity(dimension, id, at, 0.0, 0.0);
        } else {
            game.native_summon(
                dimension,
                "minecraft:interaction",
                at,
                Compound::from([
                    (PART_OF.into(), Tag::IntArray(uuid.to_vec())),
                    ("CreatePartIndex".into(), Tag::Int(part_index)),
                    ("CreateTrainTrapdoorOpen".into(), Tag::Int(i32::from(open))),
                    ("CreateTrainTrapdoorPos".into(), Tag::IntArray(rel.to_vec())),
                    ("width".into(), Tag::Float(width.to_bits())),
                    ("height".into(), Tag::Float(height.to_bits())),
                    ("response".into(), Tag::Byte(1)),
                ]),
            );
        }
    }
}

fn draw_train_door_proxy(
    game: &mut Game<'_>,
    train: u32,
    index: usize,
    block: &Compound,
    pose: Pose,
    existing: &[(i32, u32)],
) {
    let Some((open, lo, hi)) = doors::train_door_shape(block) else {
        return;
    };
    let part = index as i32 * 10 + 1;
    let old = existing
        .iter()
        .find(|(idx, _)| *idx == part)
        .map(|(_, id)| *id);
    let valid = old.is_some_and(|id| matches!(game.persist.raw.get(&id), Some(Tag::Compound(tag)) if int(tag, "CreateTrainTrapdoorOpen") == Some(i32::from(open))));
    let dimension = game.native_dimension();
    if let Some(id) = old.filter(|_| !valid) {
        game.native_remove_entity(dimension, id);
    }
    let rel = relative(block);
    let point = Vec3::from_array(rel.map(|v| v as f32)) - Vec3::new(0.5, 0.0, 0.5)
        + Vec3::new(
            ((lo[0] + hi[0]) * 0.5) as f32,
            lo[1] as f32,
            ((lo[2] + hi[2]) * 0.5) as f32,
        );
    let at = pose.position(point);
    if let Some(id) = old.filter(|_| valid) {
        game.native_move_entity(dimension, id, at, 0.0, 0.0);
    } else {
        let uuid = game.uuid_for(train);
        game.native_summon(
            dimension,
            "minecraft:interaction",
            at,
            Compound::from([
                (PART_OF.into(), Tag::IntArray(uuid.to_vec())),
                ("CreatePartIndex".into(), Tag::Int(part)),
                ("CreateTrainTrapdoorOpen".into(), Tag::Int(i32::from(open))),
                ("CreateTrainDoorPos".into(), Tag::IntArray(rel.to_vec())),
                ("width".into(), Tag::Float(1.0_f32.to_bits())),
                ("height".into(), Tag::Float(1.0_f32.to_bits())),
                ("response".into(), Tag::Byte(1)),
            ]),
        );
    }
}

fn interactive_shape(cell: &Compound) -> Option<(bool, [f64; 3], [f64; 3])> {
    if let Some(shape) = doors::train_door_shape(cell) {
        return Some(shape);
    }
    let (open, top, facing) = trapdoor_state(cell)?;
    let (lo, hi) = super::create_train_trapdoor_exact::bounds(open, top, &facing)?;
    Some((open, lo, hi))
}

pub(super) fn pick_trapdoor(
    game: &Game<'_>,
    current: Option<(f64, Option<i32>)>,
) -> Option<(f64, Option<i32>)> {
    use horizon_core::geometry::{Aabb, Vec3 as GeometryVec3};
    let Some((eye, direction)) = game.aim() else {
        return current;
    };
    let mut best = current;
    for entity in &game.others {
        let Some(Tag::Compound(proxy)) = game.persist.raw.get(&entity.id) else {
            continue;
        };
        let Some(rel) =
            coords(proxy, "CreateTrainTrapdoorPos").or_else(|| coords(proxy, "CreateTrainDoorPos"))
        else {
            continue;
        };
        let Some(Tag::IntArray(owner)) = proxy.get(&PART_OF.into()) else {
            continue;
        };
        let Ok(owner) = <[i32; 4]>::try_from(owner.as_slice()) else {
            continue;
        };
        let Some(data) = carriage_by_uuid(game, owner).and_then(|id| carriage(game, id)) else {
            continue;
        };
        let (Some(axis), Some(origin), Some(Tag::List(blocks))) = (
            coords(data, "Axis"),
            coords(data, "Track"),
            data.get(&"Blocks".into()),
        ) else {
            continue;
        };
        let Some(cell) = blocks.iter().find_map(|tag| match tag {
            Tag::Compound(cell) if relative(cell) == rel => Some(cell),
            _ => None,
        }) else {
            continue;
        };
        let Some((_, lo, hi)) = interactive_shape(cell) else {
            continue;
        };
        let pose = Pose::new(axis, &track_points(game, data, origin, axis));
        let origin = pose.block(rel);
        let local_eye = (pose.rotation.conjugate()
            * Vec3::from_array(std::array::from_fn(|i| (eye[i] - origin[i]) as f32)))
        .to_array()
        .map(f64::from);
        let local_dir = (pose.rotation.conjugate() * Vec3::from_array(direction.map(|v| v as f32)))
            .to_array()
            .map(f64::from);
        let bounds = Aabb::new(
            GeometryVec3::new(lo[0], lo[1], lo[2]),
            GeometryVec3::new(hi[0], hi[1], hi[2]),
        );
        let Some(distance) = super::ray_box(local_eye, local_dir, game.entity_reach, bounds) else {
            continue;
        };
        if game.before_block(distance) && best.is_none_or(|(prior, _)| distance < prior) {
            best = Some((distance, Some(entity.id as i32)));
        }
    }
    best
}

pub(super) fn interact_trapdoor(game: &mut Game<'_>, entity: u32, location: [f64; 3]) -> bool {
    if game.spectator() {
        return false;
    }
    let Some(Tag::Compound(proxy)) = game.persist.raw.get(&entity) else {
        return false;
    };
    let door = coords(proxy, "CreateTrainDoorPos").is_some();
    let Some(rel) =
        coords(proxy, "CreateTrainTrapdoorPos").or_else(|| coords(proxy, "CreateTrainDoorPos"))
    else {
        return false;
    };
    let Some(Tag::IntArray(owner)) = proxy.get(&PART_OF.into()) else {
        return false;
    };
    let Ok(owner) = <[i32; 4]>::try_from(owner.as_slice()) else {
        return false;
    };
    let Some(id) = carriage_by_uuid(game, owner) else {
        return false;
    };
    let Some(mut data) = carriage(game, id).cloned() else {
        return false;
    };
    let (Some(axis), Some(origin)) = (coords(&data, "Axis"), coords(&data, "Track")) else {
        return false;
    };
    let points = track_points(game, &data, origin, axis);
    let pose = Pose::new(axis, &points);
    let Some(target) = game.others.iter().find(|other| other.id == entity) else {
        return false;
    };
    let at = target.position.components();
    let clicked = std::array::from_fn::<_, 3, _>(|i| at[i] + location[i]);
    let block_origin = pose.block(rel);
    let local = pose.rotation.conjugate()
        * Vec3::from_array(std::array::from_fn(|i| {
            (clicked[i] - block_origin[i]) as f32
        }));
    let Some(Tag::List(blocks)) = data.get_mut(&"Blocks".into()) else {
        return false;
    };
    let Some(cell) = blocks.iter_mut().find_map(|block| match block {
        Tag::Compound(cell)
            if relative(cell) == rel
                && state_name(cell)
                    .as_deref()
                    .is_some_and(|name| train_trapdoor(name) || doors::sliding(name)) =>
        {
            Some(cell)
        }
        _ => None,
    }) else {
        return false;
    };
    let Some((open, lo, hi)) = interactive_shape(cell) else {
        return false;
    };
    let values = local.to_array();
    if (0..3).any(|i| f64::from(values[i]) < lo[i] - 0.01 || f64::from(values[i]) > hi[i] + 0.01) {
        return false;
    }
    if door {
        doors::toggle_train_door(blocks, rel);
    } else if let Some(Tag::Compound(state)) = cell.get_mut(&"BlockState".into())
        && let Some(Tag::Compound(props)) = state.get_mut(&"Properties".into())
    {
        props.insert(
            "open".into(),
            Tag::String(if open { "false" } else { "true" }.into()),
        );
    }
    let offsets = bogey_offsets(&data);
    let distance = decimal(&data, "Distance");
    let blocks: Vec<_> = match data.get(&"Blocks".into()) {
        Some(Tag::List(blocks)) => blocks
            .iter()
            .filter_map(|v| match v {
                Tag::Compound(c) => Some(c.clone()),
                _ => None,
            })
            .collect(),
        _ => return false,
    };
    if let Some(Tag::Compound(tag)) = game.persist.raw.get_mut(&id) {
        tag.insert(CARRIAGE.into(), Tag::Compound(data));
    }
    draw(game, id, &blocks, axis, &offsets, distance, &points, false);
    if let Some(eye) = game.eye_position() {
        let at = [
            eye[0].floor() + 0.5,
            (eye[1] - 1.62).floor() + 0.5,
            eye[2].floor() + 0.5,
        ];
        let pitch = game.world.random.next_float() * 0.1 + 0.9;
        if !door || !open {
            game.native_play_sound_in_place(
                if door {
                    "minecraft:block.iron_door.open"
                } else if open {
                    "minecraft:block.wooden_trapdoor.close"
                } else {
                    "minecraft:block.wooden_trapdoor.open"
                },
                at,
                4,
                0.3,
                pitch,
            );
        }
    }
    true
}

pub(super) fn hitbox(game: &Game<'_>, id: u32) -> Option<([f64; 3], [f64; 3], [f64; 3])> {
    if carriage(game, id).is_none()
        && !matches!(game.persist.raw.get(&id), Some(Tag::Compound(tag)) if (tag.contains_key(&"CreateTrainTrapdoorPos".into()) || tag.contains_key(&"CreateTrainDoorPos".into())))
    {
        return None;
    }
    let entity = game.others.iter().find(|other| other.id == id)?;
    let pos = entity.position.components();
    let interaction = entity.interaction?;
    let half = f64::from(interaction.width) / 2.0;
    Some((
        [pos[0] - half, pos[1], pos[2] - half],
        [
            pos[0] + half,
            pos[1] + f64::from(interaction.height),
            pos[2] + half,
        ],
        pos,
    ))
}

pub(super) fn click(game: &mut Game<'_>, id: u32) -> bool {
    if game.hand != Hand::Main || game.spectator() || carriage(game, id).is_none() {
        return false;
    }
    let uuid = game.acting_player_uuid();
    let Some(Tag::Compound(tag)) = game.persist.raw.get_mut(&id) else {
        return false;
    };
    let Some(Tag::Compound(data)) = tag.get_mut(&CARRIAGE.into()) else {
        return false;
    };
    let prompt = match driver(data) {
        Some(current) if current != uuid => "These controls are already in use",
        Some(_) => {
            data.remove(&"Driver".into());
            "Released Train Controls"
        }
        None => {
            schedule::pause_for_controls(data);
            data.insert("Driver".into(), Tag::IntArray(uuid.to_vec()));
            "Use W/S to drive and A/D to steer. Sneak to release the controls."
        }
    };
    game.message = Some((prompt.into(), std::time::Instant::now()));
    true
}

fn controls(game: &mut Game<'_>, data: &Compound, at: [f64; 3]) -> Option<(i32, i32, bool)> {
    let uuid: [i32; 4] = driver(data)?.try_into().ok()?;
    let local = game.player.is_some() && game.acting_player_uuid() == uuid;
    let (position, forward, backward, left, right, space, sneak) = if local {
        let player = game.native_player()?;
        (
            [player.x, player.y, player.z],
            game.keys.held(Mapping::Forward),
            game.keys.held(Mapping::Back),
            game.keys.held(Mapping::Left),
            game.keys.held(Mapping::Right),
            game.keys.held(Mapping::Jump),
            game.native_sneaking(),
        )
    } else {
        let host = game.lan.as_ref()?;
        let target_uuid = uuid
            .into_iter()
            .fold(0_u128, |id, word| (id << 32) | (word as u32) as u128);
        let guest = host
            .hub
            .guests
            .iter()
            .find(|g| g.uuid == target_uuid && host.hub.here(g) && !g.spectator())?;
        (
            guest.position,
            guest.input & 1 != 0,
            guest.input & 2 != 0,
            guest.input & 4 != 0,
            guest.input & 8 != 0,
            guest.input & 16 != 0,
            guest.input & 32 != 0,
        )
    };
    let distance = (0..3).map(|i| (position[i] - at[i]).powi(2)).sum::<f64>();
    (!sneak && distance < 64.0).then_some((
        i32::from(forward) - i32::from(backward),
        i32::from(left) - i32::from(right),
        space,
    ))
}

struct Approach {
    station: [i32; 3],
    track: [i32; 3],
    axis: [i32; 3],
    route: StationRoute,
    remaining: f64,
}

fn manual_approach(
    game: &Game<'_>,
    id: u32,
    data: &Compound,
    lead: Point,
    speed: f64,
) -> Option<Approach> {
    let current = coords(data, "ApproachStation");
    let braking = speed * speed / (2.0 * ACCELERATION);
    game.world
        .block_entities
        .keys()
        .filter_map(|&(x, y, z)| {
            let station = [x, y, z];
            let (track, front) = super::create_station::target(game, station)?;
            let axis = super::create_station::assembly_axis(game, track, front)?;
            let active = current == Some(station);
            let limit = if active {
                f64::INFINITY
            } else {
                32.0_f64.max(1.5 * braking)
            };
            let route = lead.forward_station(game, track, axis, limit)?;
            let distance = route.distance;
            if (!active && distance < 0.75 * braking)
                || at_station(game, station).is_some_and(|other| other != id)
                || game.others.iter().any(|other| {
                    other.id != id
                        && carriage(game, other.id).and_then(|data| coords(data, "ApproachStation"))
                            == Some(station)
                })
            {
                return None;
            }
            let remaining = if active {
                decimal(data, "ApproachDistance")
            } else {
                distance
            };
            Some(Approach {
                station,
                track,
                axis,
                route,
                remaining,
            })
        })
        .min_by(|a, b| {
            (current != Some(a.station))
                .cmp(&(current != Some(b.station)))
                .then_with(|| a.route.station_order(&b.route))
                .then_with(|| a.station.cmp(&b.station))
        })
}

fn schedule_approach(
    game: &mut Game<'_>,
    id: u32,
    data: &mut Compound,
    points: &[Point],
    axis: [i32; 3],
) -> Option<(Approach, bool)> {
    let station = coords(data, "ArrivedStation")
        .or_else(|| coords(data, "Station"))
        .filter(|station| at_station(game, *station) == Some(id));
    let instruction = schedule::tick(game, id, data, station)?;
    let path = |station, backwards| {
        let (track, front) = super::create_station::target(game, station)?;
        let axis = super::create_station::assembly_axis(game, track, front)?;
        let route =
            front_point(points, backwards).forward_station(game, track, axis, f64::INFINITY)?;
        Some(Approach {
            station,
            track,
            axis,
            remaining: route.distance,
            route,
        })
    };

    match instruction {
        schedule::Instruction::InTransit => {
            let backwards = int(data, "ApproachBackwards") == Some(1);
            if let Some(mut goal) = coords(data, "ApproachStation")
                .and_then(|station| path(station, backwards))
                .filter(|_| conductor::present(game, data, backwards))
            {
                goal.remaining = decimal(data, "ApproachDistance");
                return Some((goal, backwards));
            }
        }
        schedule::Instruction::Destination(filter) => {
            let forward = conductor::present(game, data, false);
            let backward = double_ended(data, axis) && conductor::present(game, data, true);
            if forward || backward {
                let stations = game.world.block_entities.keys().filter_map(|&(x, y, z)| {
                    let pos = [x, y, z];
                    super::create_station::target(game, pos)?;
                    if game.native_block_property(pos, "assembling").as_deref() == Some("true") {
                        return None;
                    }
                    let entity = mod_entity(game, pos)?;
                    let label = match entity.nbt.get(&"Name".into()) {
                        Some(Tag::String(name)) => name.to_string_lossy(),
                        _ => "Track Station".into(),
                    };
                    schedule::matching_name(&filter, &label).then_some(pos)
                });
                let mut goal: Option<(Approach, bool, f64)> = None;
                for station in stations {
                    if at_station(game, station) == Some(id) {
                        schedule::arrive(data);
                        return None;
                    }
                    if at_station(game, station).is_some() {
                        continue;
                    }
                    for backwards in [true, false] {
                        if (if backwards { backward } else { forward })
                            && let Some(candidate) = path(station, backwards)
                        {
                            let penalty = super::create_train_signal::forced_red_cost(
                                game,
                                front_point(points, backwards),
                                &candidate.route,
                            );
                            let cost = candidate.remaining + penalty;
                            if goal.as_ref().is_none_or(|(_, _, best)| cost < *best) {
                                goal = Some((candidate, backwards, cost));
                            }
                        }
                    }
                }
                if let Some((goal, backwards, _)) = goal {
                    schedule::depart(data);
                    return Some((goal, backwards));
                }
            }
        }
    }
    schedule::retry(data);
    None
}

fn approach_speed(speed: f64, remaining: f64, curve_ahead: Option<f64>, throttle: f64) -> f64 {
    let target_distance = remaining + 0.25;
    if target_distance - speed.abs() < 1.0 / 32.0 {
        return target_distance.max(1.0 / 32.0);
    }
    let scaled = MAX_SPEED * (target_distance / 10.0);
    if target_distance < 10.0 && speed > scaled {
        return speed + (scaled - speed) * 0.5;
    }
    let braking = speed * speed / (2.0 * ACCELERATION);
    let top_speed = MAX_SPEED * throttle;
    let turn_speed = TURN_SPEED.min(top_speed);
    let target = if target_distance <= braking {
        0.0
    } else if curve_ahead.is_some_and(|distance| {
        distance <= braking - turn_speed * turn_speed / (2.0 * ACCELERATION)
    }) {
        turn_speed
    } else {
        top_speed
    };
    speed + (target - speed).clamp(-ACCELERATION, ACCELERATION)
}

pub(super) enum TickPhase {
    Early,
    AfterBlocks,
    Restored(u32),
}

pub(super) fn begin_cargo_block_phase(game: &mut Game<'_>) {
    let attached: Vec<_> = game
        .others
        .iter()
        .filter_map(|entity| {
            let data = carriage(game, entity.id)?;
            portable_items::has_port(data).then(|| (entity.id, data.clone()))
        })
        .collect();
    for (id, data) in attached {
        portable_items::begin_block_phase(game, id, &data);
    }
}

pub(super) fn refresh_port(game: &mut Game<'_>, station: [i32; 3]) {
    let eligible: Vec<_> = game
        .others
        .iter()
        .filter_map(|entity| {
            let data = carriage(game, entity.id)?;
            (decimal(data, "Speed").abs() <= 0.25 && portable_items::has_port(data))
                .then(|| (entity.id, data.clone()))
        })
        .collect();
    for (id, mut data) in eligible {
        let Some(pose) = Pose::for_port_scan(game, &data) else {
            continue;
        };
        if portable_items::refresh_port(game, id, &mut data, pose, station) {
            if let Some(Tag::Compound(tag)) = game.persist.raw.get_mut(&id) {
                tag.insert(CARRIAGE.into(), Tag::Compound(data));
            }
            return;
        }
    }
}

pub(super) fn tick(game: &mut Game<'_>, phase: TickPhase) {
    let trains: Vec<_> = game
        .others
        .iter()
        .filter_map(|entity| {
            let data = carriage(game, entity.id)?;
            let due = match phase {
                TickPhase::Early => !portable_items::has_port(data),
                TickPhase::AfterBlocks => portable_items::has_port(data),
                TickPhase::Restored(after) => entity.id > after && !portable_items::has_port(data),
            };
            due.then(|| (entity.id, data.clone()))
        })
        .collect();
    let dimension = game.native_dimension();
    for (id, mut data) in trains {
        let (Some(axis), Some(origin), Some(control)) = (
            coords(&data, "Axis"),
            coords(&data, "Track"),
            coords(&data, "Controls"),
        ) else {
            continue;
        };
        // Java checks stationary mail before the schedule tick and retries every
        // 21 ticks after arrival, including when the schedule has completed.
        if let Some(station) = coords(&data, "ArrivedStation")
            .or_else(|| coords(&data, "Station"))
            .filter(|&station| at_station(game, station) == Some(id))
        {
            let elapsed = int(&data, "MailTransferTicks").unwrap_or(0) + 1;
            if elapsed > 20 {
                super::create_train_postbox_registry::deliver_on_arrival(game, &mut data, station);
                data.insert("MailTransferTicks".into(), Tag::Int(0));
            } else {
                data.insert("MailTransferTicks".into(), Tag::Int(elapsed));
            }
        }
        let speed = decimal(&data, "Speed");
        let distance = decimal(&data, "Distance");
        let spacing = int(&data, "BogeySpacing").unwrap_or(0);
        let mut points = track_points(game, &data, origin, axis);
        let before = Pose::new(axis, &points);
        let mut doors_changed = false;
        if matches!(data.get(&"Blocks".into()), Some(Tag::List(blocks)) if blocks.iter().any(|block| {
            matches!(block, Tag::Compound(block) if state_name(block).as_deref().is_some_and(doors::sliding))
        })) {
            let station = coords(&data, "ArrivedStation")
                .or_else(|| coords(&data, "Station"))
                .filter(|&station| at_station(game, station) == Some(id));
            doors_changed = doors::tick_train(game, &mut data, station, speed, before);
        }
        let feedback_dock = coords(&data, "ArrivedStation").or_else(|| coords(&data, "Station"))
            .filter(|&station| at_station(game, station) == Some(id));
        let input = controls(game, &data, before.controls(control));
        if input.is_none() {
            data.remove(&"Driver".into());
        }
        let speed_limit = if points[0].in_curve() || points[points.len() - 1].in_curve() {
            TURN_SPEED
        } else {
            TOP_SPEED
        };
        let (drive, steer, space) = input.unwrap_or_default();
        let programmed = schedule_approach(game, id, &mut data, &points, axis);
        let automatic = programmed.is_some();
        let backwards = programmed.as_ref().map_or_else(
            || {
                space
                    && if coords(&data, "ApproachStation").is_some() {
                        int(&data, "ApproachBackwards") == Some(1)
                    } else {
                        let intent = if drive == 0 { speed } else { f64::from(drive) };
                        intent < 0.0 && double_ended(&data, axis)
                    }
            },
            |(_, backwards)| *backwards,
        );
        let direction = if backwards { -1.0 } else { 1.0 };
        let stopped_at_dock = space
            && speed == 0.0
            && front_point(&points, backwards_dock(&data))
                .location()
                .distance(
                    Point::start(
                        coords(&data, "ArrivedTrack").unwrap_or(origin),
                        coords(&data, "ArrivedAxis").unwrap_or(axis),
                        0.5,
                    )
                    .location(),
                )
                < 1e-6;
        let approach = programmed.map(|(goal, _)| goal).or_else(|| {
            if space && !stopped_at_dock {
                manual_approach(game, id, &data, front_point(&points, backwards), speed)
            } else {
                None
            }
        });
        arrival_audio(game, &mut data, axis, before, approach.as_ref(), backwards);
        let throttle = match data.get(&"Throttle".into()) {
            Some(Tag::Double(bits)) => f64::from_bits(*bits),
            _ => 1.0,
        };
        let rated = TOP_SPEED * throttle;
        let target = match if stopped_at_dock { 0 } else { drive } {
            1 => speed_limit.min(rated),
            -1 => -(speed_limit / 4.0).min(rated),
            _ => 0.0,
        };
        let acceleration = if target * speed < 0.0 {
            ACCELERATION * 2.0
        } else {
            ACCELERATION
        };
        let mut next_speed = speed + (target - speed).clamp(-acceleration, acceleration);
        let mut signal = None;
        let mut reserved = Vec::new();
        let mut predeparture = 0.0_f64;
        if let Some(goal) = &approach {
            if automatic {
                if coords(&data, "ArrivedStation")
                    .or_else(|| coords(&data, "Station"))
                    .is_some_and(|station| at_station(game, station) == Some(id))
                {
                    predeparture = 4.5;
                }
                let braking = speed * speed / (2.0 * ACCELERATION);
                let scan = (braking + 3.0 - braking % 3.0).max(predeparture);
                let prior: Vec<_> = reservations(&data).map(|entry| entry.pos).collect();
                (signal, reserved) = super::create_train_signal::scan_route(
                    game,
                    id,
                    front_point(&points, backwards),
                    &goal.route,
                    scan.min(goal.route.distance),
                    &prior,
                );
            }
            next_speed = match signal {
                Some(stop) if stop.distance < predeparture => 0.0,
                Some(stop) => {
                    approach_speed(
                        speed * direction,
                        stop.distance,
                        goal.route.curve_ahead,
                        throttle,
                    ) * direction
                }
                None => {
                    approach_speed(
                        speed * direction,
                        goal.remaining,
                        goal.route.curve_ahead,
                        throttle,
                    ) * direction
                }
            };
        }
        let approaching = approach
            .as_ref()
            .filter(|_| next_speed.is_sign_negative() == backwards);
        let route = approaching.and_then(|goal| {
            front_point(&points, !backwards).reversed().forward_station(
                game,
                goal.track,
                goal.axis,
                f64::INFINITY,
            )
        });
        let (moved, blocked) = create_train_track::drive(
            game,
            &mut points,
            next_speed,
            spacing,
            if approaching.is_some() { 0 } else { steer },
            approaching.map(|goal| signal.map_or(goal.route.distance, |stop| stop.distance)),
            route
                .as_ref()
                .or_else(|| approaching.map(|goal| &goal.route)),
        );
        if moved != 0.0 {
            data.remove(&"ArrivedStation".into());
            data.remove(&"ArrivedTrack".into());
            data.remove(&"ArrivedAxis".into());
            data.remove(&"ArrivedBackwards".into());
        }
        data.remove(&"ApproachStation".into());
        data.remove(&"ApproachDistance".into());
        data.remove(&"ApproachBackwards".into());
        if blocked {
            next_speed = 0.0;
            if automatic {
                schedule::retry(&mut data);
            }
        } else if let Some(goal) = approach {
            let stop = Point::start(goal.track, goal.axis, 0.5).location();
            if front_point(&points, backwards).location().distance(stop) < 1e-8 {
                next_speed = 0.0;
                if automatic {
                    schedule::arrive(&mut data);
                }
                data.insert(
                    "ArrivedStation".into(),
                    Tag::IntArray(goal.station.to_vec()),
                );
                super::create_train_postbox_registry::deliver_on_arrival(
                    game,
                    &mut data,
                    goal.station,
                );
                data.insert("MailTransferTicks".into(), Tag::Int(0));
                data.insert("ArrivedTrack".into(), Tag::IntArray(goal.track.to_vec()));
                data.insert("ArrivedAxis".into(), Tag::IntArray(goal.axis.to_vec()));
                data.insert("ArrivedBackwards".into(), Tag::Byte(i8::from(backwards)));
            } else {
                data.insert(
                    "ApproachStation".into(),
                    Tag::IntArray(goal.station.to_vec()),
                );
                data.insert("ApproachBackwards".into(), Tag::Byte(i8::from(backwards)));
                number(
                    &mut data,
                    "ApproachDistance",
                    goal.remaining - moved * direction,
                );
            }
        }
        if automatic && !blocked && coords(&data, "ApproachStation").is_some() {
            update_reservations(&mut data, reserved, moved * direction, game.world.game_time);
        } else {
            data.remove(&SIGNAL_RESERVATIONS.into());
        }
        let previously_waiting = coords(&data, "WaitingForSignal");
        let previous_wait_ticks = int(&data, "SignalWaitTicks").unwrap_or(0);
        data.remove(&"WaitingForSignal".into());
        data.remove(&"DistanceToSignal".into());
        data.remove(&"SignalWaitTicks".into());
        if let Some(stop) = signal {
            let travelled = moved * direction;
            let mut remaining = stop.distance - travelled;
            if remaining < 1.0e-8 {
                next_speed = 0.0;
                // Crossing updates the distance to zero before the travelled
                // distance is subtracted. The following tick reports zero.
                remaining = 0.0 - travelled;
            }
            let mut wait_ticks = if previously_waiting == Some(stop.pos) {
                previous_wait_ticks
            } else {
                0
            };
            wait_ticks += i32::from(stop.distance < predeparture)
                + i32::from(previously_waiting == Some(stop.pos) && stop.distance <= 1.0 / 16.0);
            // Java refreshes navigation after 50 ticks waiting at a cross signal.
            // The refresh clears the old wait while keeping the train in place.
            if !stop.cross || wait_ticks % 100 != 50 {
                data.insert("WaitingForSignal".into(), Tag::IntArray(stop.pos.to_vec()));
                number(&mut data, "DistanceToSignal", remaining);
                data.insert("SignalWaitTicks".into(), Tag::Int(wait_ticks));
            }
        }
        let next = distance + moved;
        number(&mut data, "Speed", next_speed);
        super::create_train_feedback::update(game, &data, feedback_dock, drive, space);
        number(&mut data, "Distance", next);
        wheels(&mut data, origin, axis, &points);
        let pose = Pose::new(axis, &points);
        if moved != 0.0
            && let Some(Tag::List(blocks)) = data.get(&"Blocks".into())
        {
            super::create_elevator_collision::carry_train(game, blocks, before, pose);
        }
        let port_changed = !matches!(phase, TickPhase::Early)
            && portable_items::update(game, id, &mut data, pose, next_speed, moved != 0.0);
        if let Some(Tag::List(blocks)) = data.get(&"Blocks".into()) {
            conductor::move_riders(game, blocks, |seat| pose.controls(seat));
            seats::move_train(
                game,
                id,
                blocks,
                |seat| pose.controls(seat),
                |seat| before.controls(seat),
            );
        }
        if moved != 0.0 {
            game.native_move_entity(dimension, id, pose.controls(control), 0.0, 0.0);
        }
        let missing_trapdoor_proxies = matches!(data.get(&"Blocks".into()), Some(Tag::List(blocks)) if blocks.iter().enumerate().any(|(index, block)| {
            matches!(block, Tag::Compound(cell) if (state_name(cell).as_deref().is_some_and(train_trapdoor) || state_name(cell).as_deref() == Some("create:train_door")))
                && !parts(game, id).iter().any(|(part, _)| *part == index as i32 * 10 + 1)
        }));
        if moved != 0.0 || port_changed || doors_changed || missing_trapdoor_proxies {
            if let Some(Tag::List(blocks)) = data.get(&"Blocks".into()) {
                let blocks: Vec<_> = blocks
                    .iter()
                    .filter_map(|tag| match tag {
                        Tag::Compound(block) => Some(block.clone()),
                        _ => None,
                    })
                    .collect();
                draw(
                    game,
                    id,
                    &blocks,
                    axis,
                    &bogey_offsets(&data),
                    next,
                    &points,
                    moved == 0.0 && !doors_changed && !missing_trapdoor_proxies,
                );
            }
        }
        if let Some(Tag::Compound(tag)) = game.persist.raw.get_mut(&id) {
            tag.insert(CARRIAGE.into(), Tag::Compound(data));
        }
    }
}

// ArrivalSoundQueue: longitudinal block positions play at half the tick rate,
// reversed when the train approaches backwards. Keep progress in the train save.
fn arrival_audio(
    game: &mut Game<'_>,
    data: &mut Compound,
    axis: [i32; 3],
    pose: Pose,
    approach: Option<&Approach>,
    backwards: bool,
) {
    let sources: Vec<_> = match data.get(&"Blocks".into()) {
        Some(Tag::List(blocks)) => blocks
            .iter()
            .filter_map(|block| {
                let Tag::Compound(block) = block else {
                    return None;
                };
                let name = state_name(block)?;
                if !matches!(
                    name.as_str(),
                    "minecraft:bell"
                        | "create:peculiar_bell"
                        | "create:haunted_bell"
                        | "minecraft:note_block"
                        | "create:steam_whistle"
                ) {
                    return None;
                }
                let pos = relative(block);
                let tick = (0..3).map(|i| pos[i] * axis[i]).sum::<i32>();
                Some((tick, block.clone()))
            })
            .collect(),
        _ => Vec::new(),
    };
    if let Some(goal) = approach {
        if goal.remaining.abs() < 60.0 && coords(data, "AnnouncedStation") != Some(goal.station) {
            data.insert(
                "AnnouncedStation".into(),
                Tag::IntArray(goal.station.to_vec()),
            );
            if let Some(first) = sources
                .iter()
                .map(|(tick, _)| *tick)
                .reduce(|a, b| if backwards { a.max(b) } else { a.min(b) })
            {
                data.insert("ArrivalSoundTick".into(), Tag::Int(first));
                data.insert(
                    "ArrivalSoundReversed".into(),
                    Tag::Byte(i8::from(backwards)),
                );
            }
        }
    } else {
        data.remove(&"AnnouncedStation".into());
    }
    let age = int(data, "ArrivalSoundAge").unwrap_or(0) + 1;
    data.insert("ArrivalSoundAge".into(), Tag::Int(age));
    if age % 2 == 0 {
        return;
    }
    let Some(tick) = int(data, "ArrivalSoundTick") else {
        return;
    };
    for (_, block) in sources.iter().filter(|(at, _)| *at == tick) {
        let props = compound(block, "BlockState").and_then(|state| compound(state, "Properties"));
        let property = |key: &str| props.and_then(|props| string(props, key));
        let (sound, pitch) = match state_name(block).as_deref() {
            Some("create:haunted_bell") => ("create:haunted_bell_use".to_owned(), 1.0),
            Some("minecraft:note_block") => {
                let note = property("note")
                    .and_then(|note| note.parse::<i32>().ok())
                    .unwrap_or(0);
                let instrument = property("instrument").unwrap_or_else(|| "harp".into());
                (
                    format!("minecraft:block.note_block.{instrument}"),
                    2.0_f32.powf((note - 12) as f32 / 12.0),
                )
            }
            Some("create:steam_whistle") => {
                let size = property("size").unwrap_or_else(|| "medium".into());
                let pitch = compound(block, "Entity")
                    .and_then(|entity| int(entity, "Pitch"))
                    .unwrap_or(0);
                (
                    if size == "large" {
                        "create:whistle_train_low"
                    } else {
                        "create:whistle_train"
                    }
                    .to_owned(),
                    2.0_f32.powf(((if size == "small" { 12 } else { 0 }) - pitch) as f32 / 12.0),
                )
            }
            _ => ("minecraft:block.bell.use".to_owned(), 1.0),
        };
        game.native_play_sound_in_place(&sound, pose.controls([0, 0, 0]), 6, 5.0, pitch);
    }
    let reverse = int(data, "ArrivalSoundReversed") == Some(1);
    let remains = sources
        .iter()
        .any(|(at, _)| if reverse { *at < tick } else { *at > tick });
    if remains {
        data.insert(
            "ArrivalSoundTick".into(),
            Tag::Int(tick + if reverse { -1 } else { 1 }),
        );
    } else {
        data.remove(&"ArrivalSoundTick".into());
    }
}
