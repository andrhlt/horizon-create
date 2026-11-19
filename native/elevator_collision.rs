use std::cell::RefCell;
use std::collections::HashMap;
use std::sync::OnceLock;

use horizon_client::collisions::SceneCollisions;
use horizon_core::geometry::{Aabb, Vec3};
use horizon_world::nbt::{Compound, Tag};
use serde::{Deserialize, Serialize};

use super::Game;
use super::create_bearing::relative;
use super::create_elevator_seats::is_seat;
use super::create_elevator_contact_motion::{FOOT_CLEARANCE, resolve};
use super::create_machines::{float, int, mod_entity, offset};

const COLLISION: &str = "CreateElevatorCollision";
const CHANNEL: &str = "create:elevator_colliders";

#[derive(Clone, Copy, Debug, PartialEq, Deserialize, Serialize)]
struct Shape {
    display: u32,
    bounds: [f64; 6],
    #[serde(default, skip_serializing_if = "Option::is_none")]
    local_bounds: Option<[f64; 6]>,
}

#[derive(Clone, Copy, Debug, PartialEq, Deserialize, Serialize)]
struct Anchor {
    display: u32,
    position: [f64; 3],
    collision_previous_y: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    rotation: Option<[f32; 4]>,
}

#[derive(Default)]
struct View {
    shapes: Vec<Shape>,
    anchors: Vec<Anchor>,
    received_world_tick: i64,
    traced_offset: Option<(u32, f64)>,
    last_contact: Option<(DeckContact, f64)>,
    pending_contact: Option<DeckContact>,
    consumed_world_tick: Option<i64>,
    last_static_floor: Option<(u64, Aabb)>,
}

#[derive(Clone, Copy)]
struct DeckContact {
    display: u32,
    top: f64,
    motion: f64,
    local_top: f64,
    previous_offset: Option<f64>,
}

#[derive(Deserialize, Serialize)]
struct Update {
    world_tick: i64,
    shapes: Option<Vec<Shape>>,
    anchors: Vec<Anchor>,
}

thread_local! {
    static SERVER: RefCell<HashMap<(u128, i32, String), View>> = RefCell::new(HashMap::new());
    static CLIENT: RefCell<View> = RefCell::new(View::default());
}

pub(super) fn capture(game: &Game<'_>, blocks: &mut [Compound], origin: [i32; 3]) {
    for block in blocks {
        let rel = relative(block);
        let at = offset(origin, rel);
        // Java's seat players can pass through the cushion, so the
        // cabin floor beneath it catches the player when they dismount.
        if is_seat(&game.native_block(at)) {
            continue;
        }
        let shapes = game.native_block_collision(at);
        if shapes.is_empty() {
            continue;
        }
        let mut bounds = Vec::with_capacity(shapes.len() * 6);
        for shape in shapes {
            bounds.extend(
                shape
                    .into_iter()
                    .enumerate()
                    .map(|(axis, n)| (n + f64::from(rel[axis % 3])).to_bits() as i64),
            );
        }
        block.insert(COLLISION.into(), Tag::LongArray(bounds));
    }
}

// The pulley resets the contraption's previous pose at an extension limit.
fn collision_previous_y(game: &Game<'_>, load: &Tag, y: f64) -> f64 {
    let Some(Tag::IntArray(position)) = load.get("Pulley") else {
        return y;
    };
    let Ok(position) = <[i32; 3]>::try_from(position.as_slice()) else {
        return y;
    };
    let Some(pulley) = mod_entity(game, position) else {
        return y;
    };
    if let Some(extension) = float(&pulley.nbt, "Offset")
        && (extension <= 0.0 || extension >= super::create_rope::level_range(game, position) as f32)
    {
        return y;
    }
    match pulley.nbt.get(&"DoorMotion".into()) {
        Some(Tag::Double(motion)) => y - f64::from_bits(*motion),
        _ => y,
    }
}

fn visit(game: &Game<'_>, mut each: impl FnMut(Shape, Anchor)) {
    for cabin in &game.others {
        let Some(load) = game
            .persist
            .raw
            .get(&cabin.id)
            .and_then(|tag| tag.get("CreateRopeLoad"))
        else {
            continue;
        };
        let Some(Tag::List(blocks)) = load.get("Blocks") else {
            continue;
        };
        let display = blocks.iter().find_map(|block| match block {
            Tag::Compound(block) => int(block, "Display").map(|value| value as u32),
            _ => None,
        });
        let Some(display) = display else {
            continue;
        };
        let position = cabin.position.components();
        let anchor = Anchor {
            display,
            position,
            collision_previous_y: collision_previous_y(game, load, position[1]),
            rotation: None,
        };
        for block in blocks {
            for bounds in collision_bounds(block.get(COLLISION)) {
                each(Shape { display, bounds, local_bounds: None }, anchor);
            }
        }
    }
    // Train collision boxes follow the carriage pose, independently of its
    // display entities. Rotation is applied to every captured shape corner.
    for carriage in &game.others {
        let Some(data) = super::create_train::carriage(game, carriage.id) else { continue };
        let Some(pose) = super::create_train::Pose::for_collision(game, data) else { continue };
        let Some(Tag::List(blocks)) = data.get(&"Blocks".into()) else { continue };
        let position = pose.position(glam::Vec3::ZERO);
        let anchor = Anchor { display: carriage.id, position, collision_previous_y: position[1], rotation: Some(pose.rotation.to_array()) };
        for block in blocks {
            for bounds in train_collision_bounds(game, block, pose) {
                each(Shape { display: carriage.id, bounds: train_bounds(pose, bounds, position), local_bounds: Some(bounds) }, anchor);
            }
        }
    }
}

// Earlier saved carriages have block states but no captured collision boxes.
fn train_collision_bounds(game: &Game<'_>, block: &Tag, pose: super::create_train::Pose) -> Vec<[f64; 6]> {
    if let Some(captured) = block.get(COLLISION) {
        return collision_bounds(Some(captured)).collect();
    }
    let Tag::Compound(data) = block else { return Vec::new() };
    if super::create_train::state_name(data).is_some_and(|name| is_seat(&name)) {
        return Vec::new();
    }
    let Some(state) = block.get("BlockState").and_then(|state| game.state_from_nbt(state)) else { return Vec::new() };
    let rel = relative(data);
    let world = pose.position(glam::Vec3::new(rel[0] as f32, rel[1] as f32, rel[2] as f32));
    let pos = world.map(|value| value.floor() as i32);
    let mut scene = SceneCollisions { world: &game.world, binding: game.collision, subject: None };
    let Ok(shape) = game.collision.collision_shape(&mut scene, state, pos) else { return Vec::new() };
    shape.boxes().iter().map(|bounds| {
        let min = bounds.min_position();
        let max = bounds.max_position();
        [min.x + f64::from(rel[0]), min.y + f64::from(rel[1]), min.z + f64::from(rel[2]),
         max.x + f64::from(rel[0]), max.y + f64::from(rel[1]), max.z + f64::from(rel[2])]
    }).collect()
}

fn train_bounds(pose: super::create_train::Pose, bounds: [f64; 6], origin: [f64; 3]) -> [f64; 6] {
    let mut result = [f64::INFINITY, f64::INFINITY, f64::INFINITY,
                      f64::NEG_INFINITY, f64::NEG_INFINITY, f64::NEG_INFINITY];
    for x in [bounds[0], bounds[3]] {
        for y in [bounds[1], bounds[4]] {
            for z in [bounds[2], bounds[5]] {
                let at = pose.position(glam::Vec3::new((x - 0.5) as f32, y as f32, (z - 0.5) as f32));
                for axis in 0..3 {
                    result[axis] = result[axis].min(at[axis] - origin[axis]);
                    result[axis + 3] = result[axis + 3].max(at[axis] - origin[axis]);
                }
            }
        }
    }
    // A horizontal turn must preserve the exact floor height. Quaternion
    // roundoff otherwise embeds a standing player a fraction inside the deck.
    let up = pose.rotation * glam::Vec3::Y;
    if up.x.abs() < 1e-6 && up.z.abs() < 1e-6 {
        result[1] = bounds[1];
        result[4] = bounds[4];
    }
    result
}

fn collision_bounds(tag: Option<&Tag>) -> impl Iterator<Item = [f64; 6]> + '_ {
    let bits = match tag {
        Some(Tag::LongArray(bounds)) => bounds.as_slice(),
        _ => &[],
    };
    bits.chunks_exact(6)
        .map(|bits| std::array::from_fn(|axis| f64::from_bits(bits[axis] as u64)))
}

fn near(shape: Shape, anchor: [f64; 3], player: [f64; 3]) -> bool {
    // Player collision only queries boxes close to the body. Allow room
    // for travel while an update crosses the client connection.
    let radius = [4.0, 2.0, 4.0];
    (0..3).all(|axis| {
        let at = player[axis] - anchor[axis];
        shape.bounds[axis] <= at + radius[axis] && shape.bounds[axis + 3] >= at - radius[axis]
    })
}

fn absolute(shape: Shape, anchor: [f64; 3]) -> Aabb {
    let at = |axis| shape.bounds[axis] + anchor[axis % 3];
    Aabb::new(
        Vec3::new(at(0), at(1), at(2)),
        Vec3::new(at(3), at(4) + FOOT_CLEARANCE, at(5)),
    )
}

// For a pitched carriage, a block's axis-aligned top is the highest corner,
// not the surface beneath the player's feet. Resolve that local floor plane.
fn collision_for_player(shape: Shape, anchor: Anchor, body: Aabb) -> Option<Aabb> {
    let normal_box = absolute(shape, anchor.position);
    let (Some(local), Some(rotation)) = (shape.local_bounds, anchor.rotation) else { return Some(normal_box) };
    let rotation = precise_rotation(rotation);
    let normal = rotation * glam::DVec3::Y;
    if normal.x.abs() < 1e-6 && normal.z.abs() < 1e-6 { return Some(normal_box) }
    if normal.y.abs() < 0.25 { return Some(normal_box) }
    let min = body.min_position();
    let max = body.max_position();
    let x = (min.x + max.x) * 0.5;
    let z = (min.z + max.z) * 0.5;
    let point = rotation * glam::DVec3::new(local[0] - 0.5, local[4], local[2] - 0.5);
    let x0 = anchor.position[0] + point.x;
    let y0 = anchor.position[1] + point.y;
    let z0 = anchor.position[2] + point.z;
    let y = y0 - (normal.x * (x - x0) + normal.z * (z - z0)) / normal.y;
    let contact = rotation.inverse() * glam::DVec3::new(x-anchor.position[0], y-anchor.position[1], z-anchor.position[2]);
    let cx = contact.x + 0.5;
    let cz = contact.z + 0.5;
    if (min.y - y - FOOT_CLEARANCE).abs() > 0.5 { return Some(normal_box) }
    if cx < local[0] || cx > local[3] || cz < local[2] || cz > local[5] { return None }
    let low = normal_box.min_position();
    let high = normal_box.max_position();
    Some(Aabb::new(low, Vec3::new(high.x, y + FOOT_CLEARANCE, high.z)))
}

pub(super) fn sync(game: &mut Game<'_>) {
    let players = game.native_server_players();
    let mut cabins = Vec::new();
    if players
        .iter()
        .any(|player| player.dimension == game.native_dimension())
    {
        visit(game, |shape, anchor| cabins.push((shape, anchor)));
    }

    SERVER.with_borrow_mut(|sent| {
        sent.retain(|(uuid, entity, dimension), _| {
            players.iter().any(|player| {
                player.uuid == *uuid
                    && player.entity_id == *entity
                    && player.dimension == *dimension
            })
        });
        for player in players {
            if player.dimension != game.native_dimension() {
                continue;
            }
            let mut current = View::default();
            for &(shape, anchor) in &cabins {
                if !near(shape, anchor.position, player.position) {
                    continue;
                }
                current.shapes.push(shape);
                if current.anchors.last() != Some(&anchor) {
                    current.anchors.push(anchor);
                }
            }
            let key = (player.uuid, player.entity_id, player.dimension.clone());
            let old = sent.get(&key);
            let changed_shapes = old.map_or(!current.shapes.is_empty(), |old| {
                old.shapes != current.shapes
            });
            let changed_anchors = old.map_or(!current.anchors.is_empty(), |old| {
                old.anchors != current.anchors
            });
            if !changed_shapes && !changed_anchors {
                continue;
            }
            let update = Update {
                world_tick: game.world.game_time,
                shapes: changed_shapes.then(|| current.shapes.clone()),
                anchors: current.anchors.clone(),
            };
            if let Ok(data) = serde_json::to_vec(&update)
                && game
                    .native_net_send_to_player(player.uuid, CHANNEL, &data)
                    .is_ok()
            {
                sent.insert(key, current);
            }
        }
    });
}

fn supports(box_at: Aabb, body: Aabb) -> bool {
    supports_with_tolerance(box_at, body, 1.0e-6)
}

fn supports_with_tolerance(box_at: Aabb, body: Aabb, vertical: f64) -> bool {
    const EPSILON: f64 = 1.0e-6;
    let (min, max) = (box_at.min_position(), box_at.max_position());
    let (feet, head) = (body.min_position(), body.max_position());
    (feet.y - max.y).abs() <= vertical
        && head.x > min.x + EPSILON
        && feet.x < max.x - EPSILON
        && head.z > min.z + EPSILON
        && feet.z < max.z - EPSILON
}

fn supported_by_shape(shape: Shape, anchor: Anchor, body: Aabb) -> bool {
    let Some(bounds) = collision_for_player(shape, anchor, body) else { return false };
    let pitched = anchor.rotation.is_some_and(|rotation| {
        let up = glam::Quat::from_array(rotation) * glam::Vec3::Y;
        up.x.abs() >= 1e-6 || up.z.abs() >= 1e-6
    });
    // The contact plane uses f32 carriage transforms; allow their rounding
    // error without changing the horizontal footprint or elevator tolerance.
    supports_with_tolerance(bounds, body, if pitched { 2.0e-5 } else { 1.0e-6 })
}

fn standing_body(game: &Game<'_>) -> Option<Aabb> {
    let player = game.player.as_ref()?;
    (game.riding.is_none()
        && player.health.health() > 0.0
        && !player.flying
        && !player.spectator
        && !player.sleeping
        && player.velocity.y <= 0.0)
        .then(|| player.bounds())
}

fn carry(game: &mut Game<'_>, body: Aabb, dy: f64) {
    carry_motion(game, body, Vec3::new(0.0, dy, 0.0));
}

fn carry_motion(game: &mut Game<'_>, body: Aabb, delta: Vec3) {
    if delta == Vec3::ZERO {
        return;
    }
    // The cabin floor moved with the rider. Clip its push against the
    // stationary world, like Create's contact-point motion.
    let mut scene = SceneCollisions {
        world: &game.world,
        binding: game.collision,
        subject: None,
    };
    let Ok(movement) = scene.resolve(body, delta, 0.0, true) else {
        return;
    };
    if let Some(player) = game.player.as_mut() {
        player.position = player.position.add_vector(movement);
        if movement.y == delta.y {
            player.ground.on_ground = true;
            player.fall_distance = 0.0;
        }
    }
}

pub(super) fn receive(game: &mut Game<'_>, channel: &str, data: &[u8]) {
    if channel != CHANNEL {
        return;
    }
    let Ok(update) = serde_json::from_slice::<Update>(data) else {
        return;
    };
    CLIENT.with_borrow_mut(|registered| {
        // Preserve a recent, stationary static-floor contact when that exact
        // floor is replaced by a newly assembled carriage.
        if let Some(body) = standing_body(game)
            && let Some((tick, old_body)) = registered.last_static_floor
            && game.ticks.saturating_sub(tick) <= 4
            && (body.min_position().x - old_body.min_position().x).abs() < 0.01
            && (body.min_position().z - old_body.min_position().z).abs() < 0.01
            && body.min_position().y <= old_body.min_position().y + 1e-6
            && let Some(shapes) = update.shapes.as_ref()
        {
            'anchors: for anchor in &update.anchors {
                if anchor.rotation.is_none() || registered.anchors.iter().any(|old| old.display == anchor.display) { continue }
                for &shape in shapes.iter().filter(|shape| shape.display == anchor.display) {
                    let Some(bounds) = collision_for_player(shape, *anchor, old_body) else { continue };
                    let top = bounds.max_position().y;
                    if (top - old_body.min_position().y - FOOT_CLEARANCE).abs() <= 1e-6 && over(bounds, old_body) {
                        let lift = top - body.min_position().y;
                        if lift > 0.0 {
                            carry_motion(game, body, Vec3::new(0.0, lift, 0.0));
                            if let Some(player) = game.player.as_mut()
                                && (player.bounds().min_position().y - top).abs() < 1e-8
                            { player.velocity.y = 0.0; }
                        }
                        registered.last_static_floor = None;
                        break 'anchors;
                    }
                }
            }
        }
        if let Some(body) = standing_body(game) {
            for current in &update.anchors {
                let Some(previous) = registered
                    .anchors
                    .iter()
                    .find(|old| old.display == current.display)
                else {
                    continue;
                };
                if (current.position == previous.position && current.rotation == previous.rotation)
                    || (!game.clock.frozen()
                        && current.position[0] == previous.position[0]
                        && current.position[2] == previous.position[2]
                        && current.rotation == previous.rotation)
                {
                    continue;
                }
                if registered.shapes.iter().any(|&shape| {
                    shape.display == current.display
                        && supported_by_shape(shape, *previous, body)
                }) {
                    carry_motion(game, body, anchor_motion(*previous, *current, body));
                    break;
                }
            }
        }
        if let Some(shapes) = update.shapes {
            registered.shapes = shapes;
        }
        registered.anchors = update.anchors;
        registered.received_world_tick = update.world_tick;
    });
}

pub(super) fn clear() {
    CLIENT.with_borrow_mut(|registered| *registered = View::default());
}

pub(super) fn carry_local(game: &mut Game<'_>, blocks: &[Compound], old: [f64; 3], y: f64) {
    let Some(body) = standing_body(game) else {
        return;
    };
    if y == old[1] {
        return;
    }
    if blocks.iter().any(|block| {
        collision_bounds(block.get(&COLLISION.into()))
            .any(|bounds| supports(absolute(Shape { display: 0, bounds, local_bounds: None }, old), body))
    }) {
        carry(game, body, y - old[1]);
    }
}

fn precise_rotation(value: [f32; 4]) -> glam::DQuat {
    glam::DQuat::from_xyzw(value[0] as f64, value[1] as f64, value[2] as f64, value[3] as f64).normalize()
}

fn anchor_motion(previous: Anchor, current: Anchor, body: Aabb) -> Vec3 {
    let min = body.min_position();
    let max = body.max_position();
    let point = [(min.x + max.x) * 0.5, min.y, (min.z + max.z) * 0.5];
    let mut offset = [0.0; 3];
    if let (Some(old), Some(new)) = (previous.rotation, current.rotation) {
        let local = glam::DVec3::from_array(std::array::from_fn(|i| point[i] - previous.position[i]));
        let rotation = precise_rotation(new) * precise_rotation(old).inverse();
        let rotated = rotation * local;
        let values = rotated.to_array();
        for i in 0..3 { offset[i] = values[i] - local[i]; }
        // A horizontal turn has no vertical contact-point motion.
        let up = rotation * glam::DVec3::Y;
        if up.x.abs() < 1e-6 && up.z.abs() < 1e-6 { offset[1] = 0.0; }
    }
    Vec3::new(current.position[0] - previous.position[0] + offset[0],
              current.position[1] - previous.position[1] + offset[1],
              current.position[2] - previous.position[2] + offset[2])
}

pub(super) fn carry_train(
    game: &mut Game<'_>,
    blocks: &[Tag],
    before: super::create_train::Pose,
    after: super::create_train::Pose,
) {
    let Some(body) = standing_body(game) else { return };
    let previous = before.position(glam::Vec3::ZERO);
    let supported = blocks.iter().any(|block| train_collision_bounds(game, block, before).into_iter().any(|bounds| {
        let shape = Shape { display: 0, bounds: train_bounds(before, bounds, previous), local_bounds: Some(bounds) };
        let anchor = Anchor { display: 0, position: previous, collision_previous_y: previous[1], rotation: Some(before.rotation.to_array()) };
        supported_by_shape(shape, anchor, body)
    }));
    if supported {
        let next = after.position(glam::Vec3::ZERO);
        let old = Anchor { display: 0, position: previous, collision_previous_y: previous[1], rotation: Some(before.rotation.to_array()) };
        let new = Anchor { display: 0, position: next, collision_previous_y: next[1], rotation: Some(after.rotation.to_array()) };
        carry_motion(game, body, anchor_motion(old, new, body));
    }
}

pub(super) fn append_server(game: &Game<'_>, boxes: &mut Vec<Aabb>) {
    visit(game, |shape, anchor| {
        boxes.push(absolute(shape, anchor.position))
    });
}

pub(super) fn append(game: &Game<'_>, boxes: &mut Vec<Aabb>) {
    let Some(player) = &game.player else {
        return;
    };
    let at = player.position.components();
    if game.remote.is_some() {
        CLIENT.with_borrow(|view| {
            boxes.extend(view.shapes.iter().filter_map(|&shape| {
                if view.pending_contact.is_some_and(|contact| {
                    contact.display == shape.display && contact.local_top == shape.bounds[4]
                }) {
                    return None;
                }
                let anchor = *view.anchors.iter().find(|anchor| anchor.display == shape.display)?;
                if near(shape, anchor.position, at) { collision_for_player(shape, anchor, player.bounds()) } else { None }
            }));
        });
    } else {
        visit(game, |shape, anchor| {
            if near(shape, anchor.position, at) {
                if let Some(bounds) = collision_for_player(shape, anchor, player.bounds()) { boxes.push(bounds); }
            }
        });
    }
}

fn over(bounds: Aabb, body: Aabb) -> bool {
    let min = bounds.min_position();
    let max = bounds.max_position();
    let feet = body.min_position();
    let head = body.max_position();
    head.x > min.x && feet.x < max.x && head.z > min.z && feet.z < max.z
}

pub(super) fn begin_motion(game: &Game<'_>) {
    CLIENT.with_borrow_mut(|view| {
        if let Some(player) = game.player.as_ref()
            && player.ground.on_ground && standing_body(game).is_some()
        {
            let body = player.bounds();
            let feet = body.min_position();
            let high = body.max_position();
            let x = ((feet.x + high.x) * 0.5).floor() as i32;
            let y = (feet.y - 1e-5).floor() as i32;
            let z = ((feet.z + high.z) * 0.5).floor() as i32;
            if game.native_block_collision([x, y, z]).iter().any(|bounds| {
                (f64::from(y) + bounds[4] - feet.y).abs() <= 1e-6
            }) {
                view.last_static_floor = Some((game.ticks, body));
            }
        }
        view.pending_contact = None;
        let player = game.player.as_ref().filter(|player| {
            !game.clock.frozen()
                && game.riding.is_none()
                && player.health.health() > 0.0
                && !player.flying
                && !player.spectator
                && !player.sleeping
                && !player.fall_flying
        });
        let Some(player) = player else {
            view.last_contact = None;
            return;
        };
        let body = player.bounds();
        let feet = body.min_position().y;
        let fresh = view.consumed_world_tick != Some(view.received_world_tick);
        view.pending_contact = view
            .shapes
            .iter()
            .filter_map(|&shape| {
                let anchor = view
                    .anchors
                    .iter()
                    .find(|anchor| anchor.display == shape.display)?;
                if !over(absolute(shape, anchor.position), body) {
                    return None;
                }
                let local_top = shape.bounds[4];
                let top = local_top + anchor.position[1];
                let previous = view.last_contact.filter(|(contact, _)| {
                    contact.display == anchor.display && contact.local_top == local_top
                });
                let old_top = previous
                    .map_or(anchor.collision_previous_y + local_top, |(contact, _)| {
                        contact.top
                    });
                let supported = previous
                    .is_some_and(|(contact, _)| (feet - contact.top).abs() <= 0.55)
                    || (feet - old_top - FOOT_CLEARANCE).abs() <= 1e-6
                    || (feet - top - FOOT_CLEARANCE).abs() <= 1e-6;
                supported.then_some(DeckContact {
                    display: anchor.display,
                    top,
                    local_top,
                    motion: if fresh {
                        anchor.position[1] - anchor.collision_previous_y
                    } else {
                        0.0
                    },
                    previous_offset: previous.map(|(_, offset)| offset),
                })
            })
            .min_by(|a, b| (feet - a.top).abs().total_cmp(&(feet - b.top).abs()));
        view.consumed_world_tick = Some(view.received_world_tick);
    });
}

pub(super) fn finish_motion(game: &mut Game<'_>, jump: bool) {
    let Some(player) = &game.player else {
        return;
    };
    let body = player.bounds();
    let (supported, previous) = CLIENT.with_borrow_mut(|view| {
        let previous = view.last_contact.take();
        let supported = select_contact(view, body);
        (supported, previous)
    });
    let Some(supported) = supported else {
        return;
    };
    let input_y = player.position.y;
    let input_velocity = player.velocity.y;
    let Some(contact) = resolve(
        input_y,
        input_velocity,
        supported.top,
        supported.motion,
        supported.previous_offset,
    ) else {
        // Coasting on a delayed packet can leave the rider briefly above the
        // deck with upward velocity. Release the last support on a jump.
        if !jump {
            CLIENT.with_borrow_mut(|view| {
                view.last_contact = previous.map(|(_, offset)| (supported, offset));
            });
        }
        return;
    };
    carry(game, body, contact.feet_y - input_y);
    if let Some(player) = game.player.as_mut()
        && (player.position.y - contact.feet_y).abs() <= 1e-8
    {
        player.ground.on_ground = true;
        player.fall_distance = 0.0;
        player.velocity.y = contact.velocity_y;
        CLIENT.with_borrow_mut(|view| {
            view.last_contact = Some((supported, player.position.y - supported.top));
        });
        if tracing() {
            CLIENT.with_borrow(|view| {
                eprintln!(
                    "CREATE_STANDING_CONTACT {},{},{:.15},{:.15},{:.15},{:.15},{:.15},{:.15}",
                    game.ticks,
                    view.received_world_tick,
                    supported.top,
                    supported.motion,
                    input_y,
                    input_velocity,
                    contact.feet_y,
                    contact.velocity_y
                );
            });
        }
    }
}

fn select_contact(view: &mut View, body: Aabb) -> Option<DeckContact> {
    let contact = view.pending_contact.take()?;
    let anchor = view
        .anchors
        .iter()
        .find(|anchor| anchor.display == contact.display)?;
    view.shapes
        .iter()
        .any(|&shape| {
            shape.display == contact.display
                && shape.bounds[4] == contact.local_top
                && over(absolute(shape, anchor.position), body)
        })
        .then_some(contact)
}

fn tracing() -> bool {
    static TRACE: OnceLock<bool> = OnceLock::new();
    *TRACE.get_or_init(|| std::env::var_os("HORIZON_CREATE_STANDING_TRACE").is_some())
}

pub(super) fn trace_client_motion(game: &Game<'_>) {
    if !tracing() {
        return;
    }
    let Some(player) = &game.player else {
        return;
    };
    let body = player.bounds();
    let feet = body.min_position();
    let head = body.max_position();
    CLIENT.with_borrow_mut(|view| {
        let deck = view
            .shapes
            .iter()
            .filter_map(|&shape| {
                let anchor = view
                    .anchors
                    .iter()
                    .find(|anchor| anchor.display == shape.display)?;
                let bounds = absolute(shape, anchor.position);
                let min = bounds.min_position();
                let max = bounds.max_position();
                (head.x > min.x
                    && feet.x < max.x
                    && head.z > min.z
                    && feet.z < max.z
                    && (feet.y - max.y).abs() <= 0.55)
                    .then_some((anchor, max.y - FOOT_CLEARANCE))
            })
            .min_by(|(_, a), (_, b)| (feet.y - a).abs().total_cmp(&(feet.y - b).abs()));
        if let Some((anchor, deck)) = deck {
            let previous_offset = view.traced_offset
                .filter(|&(display, _)| display == anchor.display)
                .map(|(_, offset)| offset);
            let contact = resolve(feet.y, player.velocity.y, deck, anchor.position[1] - anchor.collision_previous_y,
                                  previous_offset);
            view.traced_offset = Some((anchor.display, feet.y - deck));
            eprintln!(
                "CREATE_STANDING_RESULT {},{},{},{:.15},{:.15},{:.15},{:.15},{:.15},{},{},{:.15},{:.15}",
                game.ticks,
                view.received_world_tick,
                anchor.display,
                anchor.position[1],
                anchor.collision_previous_y,
                deck,
                feet.y,
                player.velocity.y,
                player.ground.on_ground,
                game.riding.is_some(),
                contact.as_ref().map_or(feet.y, |contact| contact.feet_y),
                contact.map_or(player.velocity.y, |contact| contact.velocity_y),
            );
        } else {
            view.traced_offset = None;
        }
    });
}
