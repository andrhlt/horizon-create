use horizon_assets::item_model::DisplayContext;
use horizon_core::{
    geometry::{Aabb, Direction, Vec3, traverse_blocks},
    position::BlockPos,
};
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;

use crate::containers::ModBlockEntity;
use crate::items::ItemStack;

use super::Game;
use super::{create_belt, create_belt_funnel};
use super::create_depot::{DEPOT, compound, encode, receive_stack, receiver_empty};
use super::create_fan::facing;
use super::create_machines::{float, int, mod_entity, offset, reading, set_float};
use super::create_package_style::ENTITY as PACKAGE;
use super::create_spout::{self, Action};
use super::native_block_entity_draw::BlockEntityDraw;

pub(super) const EJECTOR: &str = "create:weighted_ejector";
const LID: &str = "create:block/weighted_ejector/top";
const SHAFT: &str = "create:block/shaft";
const PLAYER_LAUNCH: &str = "create:ejector_player_launch";

fn name(nbt: &Compound) -> String {
    match nbt.get(&"State".into()) {
        Some(Tag::String(state)) => state.to_string_lossy(),
        _ => "RETRACTING".into(),
    }
}

pub(super) fn charged(entity: &ModBlockEntity) -> bool {
    name(&entity.nbt) == "CHARGED"
}

pub(super) const STACK_SIZE: i32 = 64;

pub(super) fn stack_size(entity: Option<&ModBlockEntity>) -> i32 {
    entity
        .and_then(|entity| int(&entity.nbt, "ScrollValue"))
        .unwrap_or(0)
        .clamp(0, STACK_SIZE)
}

pub(super) fn set_stack_size(game: &mut Game<'_>, pos: [i32; 3], size: i32) {
    let size = size.clamp(0, STACK_SIZE);
    let changed = game.native_with_mod_block_entity(pos, |entity| {
        if entity.id != EJECTOR || stack_size(Some(entity)) == size {
            return false;
        }
        entity.nbt.insert("ScrollValue".into(), Tag::Int(size));
        true
    });
    if changed == Some(true) {
        super::create_speed_controller::setting_feedback(game, pos);
        game.native_block_entity_sync(pos);
        game.native_update_output_neighbors(game.native_dimension(), pos);
    }
}

pub(super) fn stack_box(game: &Game<'_>, pos: [i32; 3], side: [i32; 3]) -> Option<[f64; 3]> {
    let direction = facing(game, game.world.block(pos[0], pos[1], pos[2]))?.normal();
    if side == [0, 1, 0] && !mod_entity(game, pos).is_some_and(charged) {
        return Some([
            0.5 - f64::from(direction[0]) * 5.0 / 16.0,
            10.5 / 16.0,
            0.5 - f64::from(direction[2]) * 5.0 / 16.0,
        ]);
    }
    (side[0] * direction[0] != 0 || side[2] * direction[2] != 0).then_some([
        0.5 + f64::from(side[0]) * 7.5 / 16.0,
        6.0 / 16.0,
        0.5 + f64::from(side[2]) * 7.5 / 16.0,
    ])
}

pub(super) fn distances(nbt: &Compound) -> (i32, i32) {
    let forward = int(nbt, "HorizontalDistance").unwrap_or(1).clamp(0, 32);
    let up = int(nbt, "VerticalDistance").unwrap_or(0).clamp(-32, 32);
    (forward, up)
}

fn lid(nbt: &Compound) -> f32 {
    compound(nbt, "Lid")
        .and_then(|lid| float(lid, "Value"))
        .unwrap_or(1.0)
}

fn flight(nbt: &Compound) -> Vec<(ItemStack, i32)> {
    let Some(Tag::List(items)) = nbt.get(&"LaunchedItems".into()) else {
        return Vec::new();
    };
    items
        .iter()
        .filter_map(|item| {
            let Tag::Compound(item) = item else {
                return None;
            };
            Some((
                ItemStack::from_nbt(compound(item, "Stack")?)?,
                int(item, "Time")?,
            ))
        })
        .collect()
}

struct Incoming {
    stack: ItemStack,
    pos: f32,
}

fn incoming(nbt: &Compound) -> Vec<Incoming> {
    let Some(Tag::List(stacks)) = nbt.get(&"Incoming".into()) else {
        return Vec::new();
    };
    stacks
        .iter()
        .filter_map(|entry| {
            let Tag::Compound(entry) = entry else {
                return None;
            };
            Some(Incoming {
                stack: ItemStack::from_nbt(compound(entry, "Item")?)?,
                pos: float(entry, "Pos").unwrap_or(0.0),
            })
        })
        .collect()
}

fn save_incoming(nbt: &mut Compound, stacks: &[Incoming]) {
    let tags = stacks
        .iter()
        .map(|entry| {
            let mut tag = Compound::from([("Item".into(), encode(&entry.stack))]);
            set_float(&mut tag, "Pos", entry.pos);
            Tag::Compound(tag)
        })
        .collect();
    nbt.insert("Incoming".into(), Tag::List(tags));
}

fn stack_limit(game: &Game<'_>, stack: &ItemStack) -> u32 {
    stack.data()
        .and_then(|data| data.other("minecraft:max_stack_size"))
        .and_then(|tag| match tag {
            Tag::Int(size) => Some((*size).clamp(1, 99) as u32),
            _ => None,
        })
        .unwrap_or_else(|| game.native_max_stack_size(&stack.item).unwrap_or(64))
}

fn accepted_amount(entity: &ModBlockEntity, stack: &ItemStack, max: u32, pending: &[Incoming]) -> u32 {
    if !charged(entity) || entity.items.is_empty() {
        return 0;
    }
    let existing = entity.items[0]
        .as_ref()
        .or_else(|| pending.first().map(|entry| &entry.stack));
    if existing.is_some_and(|held| !held.same_item_same_components(stack)) {
        return 0;
    }

    let configured = stack_size(Some(entity)) as u32;
    // Java initially limits the insert to the empty held stack's maximum of one.
    let held_limit = if entity.items[0].is_some() { max } else { 1 };
    let limit = held_limit.min(if configured == 0 { 64 } else { configured });
    let stored = entity
        .items
        .iter()
        .flatten()
        .map(|stack| stack.count)
        .sum::<u32>()
        + pending.iter().map(|entry| entry.stack.count).sum::<u32>();
    stack.count.min(limit.saturating_sub(stored))
}

fn accept(entity: &mut ModBlockEntity, stack: &ItemStack, max: u32, position: f32) -> u32 {
    let mut pending = incoming(&entity.nbt);
    let added = accepted_amount(entity, stack, max, &pending);
    if added == 0 {
        return 0;
    }
    let stack = ItemStack {
        count: added,
        ..stack.clone()
    };
    if entity.items[0].is_none() {
        entity.items[0] = Some(stack);
        set_float(&mut entity.nbt, "BeltPosition", position);
    } else {
        pending.push(Incoming { stack, pos: position });
        save_incoming(&mut entity.nbt, &pending);
    }
    added
}

pub(super) fn insert(game: &mut Game<'_>, pos: [i32; 3], stack: &ItemStack) -> u32 {
    let max = stack_limit(game, stack);
    game.native_with_mod_block_entity(pos, |entity| accept(entity, stack, max, 0.0))
        .unwrap_or(0)
}

pub(super) fn receive_landed_stack(game: &mut Game<'_>, pos: [i32; 3], stack: &ItemStack) -> u32 {
    let max = stack_limit(game, stack);
    let inserted = game
        .native_with_mod_block_entity(pos, |entity| accept(entity, stack, max, 0.5))
        .unwrap_or(0);
    if inserted != 0 {
        game.native_block_entity_sync(pos);
    }
    inserted
}

fn collect_landed_stacks(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    if !charged(entity) {
        return;
    }
    let [x, y, z] = pos.map(f64::from);
    let mut i = 0;
    while let Some(item) = game.dropped.get(i) {
        let at = item.position;
        // A stationary ground item attempts its next collision every four
        // ticks. The skipped ticks still build vertical speed by gravity.
        let contacted = item.on_ground && item.vertical_collision && item.velocity.y == 0.0;
        if contacted && (x..x + 1.0).contains(&at.x) && (z..z + 1.0).contains(&at.z)
            && (y..y + 1.0).contains(&at.y)
        {
            let inserted = accept(entity, &item.stack, stack_limit(game, &item.stack), 0.5);
            if inserted == item.stack.count {
                game.remove_dropped(i);
                continue;
            }
            game.dropped[i].stack.count -= inserted;
        }
        i += 1;
    }
}

fn advance_incoming(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    let mut pending = incoming(&entity.nbt);
    if pending.is_empty() {
        return;
    }
    pending.retain_mut(|entry| {
        let difference = 0.5 - entry.pos;
        if difference > 1.0 / 512.0 {
            entry.pos += difference / 4.0;
        }
        if difference >= 1.0 / 16.0 {
            return true;
        }

        match entity.items.first_mut() {
            Some(Some(held)) if held.same_item_same_components(&entry.stack) => {
                held.count += entry.stack.count;
            }
            Some(slot @ None) => {
                *slot = Some(entry.stack.clone());
                set_float(&mut entity.nbt, "BeltPosition", entry.pos);
            }
            _ => {
                let [x, y, z] = pos.map(f64::from);
                game.add_item_entity(entry.stack.clone(), [x + 0.5, y + 1.0, z + 0.5], None, 10);
            }
        }
        false
    });
    save_incoming(&mut entity.nbt, &pending);
}

fn payload(stack: &ItemStack, age: i32) -> Tag {
    Tag::Compound(Compound::from([
        ("Stack".into(), encode(stack)),
        ("Time".into(), Tag::Int(age)),
    ]))
}

pub(super) struct Trajectory {
    speed: [f64; 2],
    pub(super) time: f64,
    target: [f64; 2],
}

impl Trajectory {
    pub(super) fn new(distance: i32, elevation: i32) -> Self {
        let [x, y] = [f64::from(distance), f64::from(elevation)];
        let error = -0.0007 * (x + 0.5).powi(2) + 0.484
            - y.min(5.0) / 5.0 * (0.076 * x - 0.0014 * x * x).min(1.0);
        let height = (y + (x + 0.5) / 8.0).max(0.0) + if distance <= 1 { 1.0 } else { 4.0 };
        let upward = (2.0 * height / 13.0).sqrt() + 0.015 * height;
        let peak = (98.0 / (25.0 * upward + 98.0)).ln() / 0.98_f64.ln();
        let time = (height - upward).sqrt() * 4.87 + 0.115 * (height - upward) + peak;
        let across = (x - error + 0.5) / (-10.6033 * (0.91_f64.powf(time) - 1.0));
        Self {
            speed: [across, upward],
            time,
            target: [x, y],
        }
    }

    fn launch_motion(&self, direction: Direction) -> Vec3 {
        let [across, up] = self.speed;
        let [dx, _, dz] = direction.normal().map(f64::from);
        Vec3::new(dx * across * 0.91, up * 0.98, dz * across * 0.91)
    }

    pub(super) fn world_point(&self, pos: [i32; 3], direction: Direction, time: f64) -> Vec3 {
        let [across, dy] = self.position(time);
        let along = direction.normal();
        Vec3::new(
            f64::from(pos[0]) + 0.5 + f64::from(along[0]) * across,
            f64::from(pos[1]) + 0.5 + dy,
            f64::from(pos[2]) + 0.5 + f64::from(along[2]) * across,
        )
    }

    fn velocity(&self, t: f64, direction: Direction) -> [f64; 3] {
        let [across, upward] = self.speed;
        let f = 0.98_f64.powf(t);
        let across = f64::from((across * 0.91_f64.powf(t)) as f32) * 0.5;
        let upward = f64::from((upward * f + ((f - 1.0) / (0.98 - 1.0)) * -0.0784) as f32) * 0.5;
        let along = direction.normal();
        [
            f64::from(along[0]) * across,
            upward,
            f64::from(along[2]) * across,
        ]
    }

    fn position(&self, t: f64) -> [f64; 2] {
        let [across, upward] = self.speed;
        let x = f64::from((across * -10.6033 * (0.91_f64.powf(t) - 1.0)) as f32);
        let f = 0.98_f64.powf(t);
        let y = f64::from((upward * (1.0 - f) * 49.4983 - 194.033 * f - 3.92 * t + 194.033) as f32);
        let correction = (t / self.time).clamp(0.0, 1.0).powi(3);
        [
            x + (self.target[0] - x) * correction,
            y + (self.target[1] - y) * correction * 0.5,
        ]
    }
}

pub(super) fn target(pos: [i32; 3], direction: Direction, horizontal: i32, vertical: i32) -> [i32; 3] {
    let along = direction.normal();
    offset(
        pos,
        [
            along[0] * horizontal.max(1),
            vertical,
            along[2] * horizontal.max(1),
        ],
    )
}

struct Impact {
    block: [i32; 3],
    drop_at: [f64; 3],
    age: f32,
}

fn impact(
    game: &Game<'_>,
    trajectory: &Trajectory,
    pos: [i32; 3],
    direction: Direction,
    age: i32,
) -> Option<Impact> {
    if age <= 2 {
        return None;
    }
    let from = trajectory.world_point(pos, direction, f64::from(age));
    let to = trajectory.world_point(pos, direction, f64::from(age + 1));
    let mut scene = horizon_client::collisions::SceneCollisions {
        world: &game.world,
        binding: game.collision,
        subject: None,
    };
    let hit = traverse_blocks(from, to, 16, |p: BlockPos| {
        let state = game.world.block(p.x, p.y, p.z);
        let shape = game
            .collision
            .collision_shape(&mut scene, state, [p.x, p.y, p.z])
            .ok()?;
        shape.clip(from, to, p)
    });
    let hit = hit.ok().flatten()?;
    let normal = hit.direction.normal();
    let [x, y, z] = hit.location.components();
    let drop_at = [
        x + f64::from(normal[0]) * 0.25,
        y + f64::from(normal[1]) * 0.25,
        z + f64::from(normal[2]) * 0.25,
    ];
    let age = (f64::from(age) + from.vector_to(hit.location).length() / from.vector_to(to).length())
        as f32;
    Some(Impact {
        block: [hit.block.x, hit.block.y, hit.block.z],
        drop_at,
        age,
    })
}

fn target_accepts(game: &Game<'_>, target: [i32; 3], stack: &ItemStack) -> bool {
    match game.native_block(target).as_str() {
        DEPOT => mod_entity(game, target).is_some_and(receiver_empty),
        EJECTOR => mod_entity(game, target).is_some_and(|receiver| {
            accepted_amount(receiver, stack, stack_limit(game, stack), &incoming(&receiver.nbt)) != 0
        }),
        create_belt::BELT => create_belt::feed_point(game, target).is_some_and(
            |(belt, index, movement, speed)| {
                create_belt::can_feed(game, belt, index, movement, Direction::Up, speed)
            },
        ),
        _ => true,
    }
}

fn deliver(
    game: &mut Game<'_>,
    target: [i32; 3],
    mut stack: ItemStack,
    drop: ([f64; 3], [f64; 3]),
) {
    let target_block = game.native_block(target);
    if target_block == DEPOT {
        let Some(left) = receive_stack(game, target, stack) else {
            game.native_with_mod_block_entity(target, |entity| {
                set_float(&mut entity.nbt, "BeltPosition", 0.5);
            });
            let at = target.map(|coordinate| f64::from(coordinate) + 0.5);
            game.native_play_sound_in_place("create:depot_plop", at, 4, 0.25, 1.25);
            game.native_block_entity_sync(target);
            return;
        };
        stack = left;
    } else if target_block == EJECTOR {
        let added = receive_landed_stack(game, target, &stack);
        stack.count -= added;
        if stack.count == 0 {
            return;
        }
    }
    if let Some((belt, index, move_to, speed)) = super::create_belt::feed_point(game, target)
        && super::create_belt::can_feed(game, belt, index, move_to, Direction::Up, speed)
    {
        super::create_belt::feed(game, belt, index, move_to, Direction::Up, speed, stack);
        return;
    }
    let mut remaining = stack;
    if matches!(target_block.as_str(), "create:chute" | "create:smart_chute") {
        let Some(left) = game.native_insert_item(target, Direction::Up, remaining) else {
            game.native_with_mod_block_entity(target, |entity| {
                set_float(&mut entity.nbt, "ItemPosition", 1.0);
                set_float(&mut entity.nbt, "BeltPosition", 0.4375);
            });
            return;
        };
        remaining = left;
    }
    let (position, motion) = drop;
    game.add_item_entity(remaining, position, Some(motion), 10);
}

fn mob_contact(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    let [x, y, z] = pos.map(f64::from);
    let center = Vec3::new(x + 0.5, y + 15.0 / 16.0, z + 0.5);
    let mut activate = false;
    for mob in &mut game.mobs {
        if mob.kind.id == PACKAGE || mob.removed || !mob.alive() || !mob.on_ground
            || mob.supporting != Some(pos)
            || mob.position.x.floor() as i32 != pos[0]
            || mob.position.z.floor() as i32 != pos[2]
        {
            continue;
        }
        mob.on_ground = false;
        mob.supporting = None;
        if center.vector_to(mob.position).length_squared() <= 0.25 * 0.25 {
            activate = true;
        } else {
            mob.position = center.add_vector(mob.position).scale(0.5);
            // The Java contact runs before the mob's ordinary gravity and drag.
            let vy = (-0.125 - mob.effective_gravity()) * f64::from(0.98_f32);
            mob.velocity = Vec3::new(0.0, vy, 0.0);
            mob.needs_sync = true;
        }
    }
    activate
}

fn launch_mobs(game: &mut Game<'_>, pos: [i32; 3], direction: Direction, trajectory: &Trajectory) {
    let [x, y, z] = pos.map(f64::from);
    let select = Aabb::new(
        Vec3::new(x + 1.0 / 16.0, y, z + 1.0 / 16.0),
        Vec3::new(x + 15.0 / 16.0, y + 1.0, z + 15.0 / 16.0),
    );
    let motion = trajectory.launch_motion(direction);
    for mob in &mut game.mobs {
        if mob.kind.id == PACKAGE || mob.removed || !mob.alive() || !select.intersects(mob.bounds()) {
            continue;
        }
        mob.on_ground = false;
        mob.supporting = None;
        mob.position = Vec3::new(x + 0.5, y + 1.0, z + 0.5);
        mob.velocity = motion;
        mob.legacy_fall_damage_until_landing = true;
        mob.needs_sync = true;
    }
}

pub(super) fn launch_local_player(game: &mut Game<'_>) {
    let Some(player) = &game.player else {
        return;
    };
    if player.spectator || player.flying || player.is_passenger || player.sleeping
        || player.shift_key_down || player.health.dead_or_dying() || !player.ground.on_ground
    {
        return;
    }
    let Some(support) = player.ground.supporting_block else {
        return;
    };
    let pos = [support.x, support.y, support.z];
    let position = player.position;
    if position.components().map(|coordinate| coordinate.floor() as i32) != pos
        || game.native_block(pos) != EJECTOR
        || game.native_neighbor_signal(game.native_dimension(), pos) != 0
    {
        return;
    }
    let Some(ejector) = mod_entity(game, pos).filter(|entity| charged(entity)) else {
        return;
    };
    let (horizontal, vertical) = distances(&ejector.nbt);
    if horizontal == 0 {
        return;
    }
    let Some(direction) = facing(game, game.world.block(pos[0], pos[1], pos[2])) else {
        return;
    };
    let [x, y, z] = pos.map(f64::from);
    let center = Vec3::new(x + 0.5, y + 15.0 / 16.0, z + 0.5);
    let off_center = center.vector_to(position).length_squared() > 0.25 * 0.25;
    // This runs after normal client travel. Java's contact happens inside travel.
    if !off_center
        && let Ok(payload) = serde_json::to_vec(&pos)
    {
        let _ = game.native_net_send_to_server(PLAYER_LAUNCH, &payload);
    }
    if let Some(player) = &mut game.player {
        player.ground.on_ground = false;
        player.ground.supporting_block = None;
        player.fall_distance = 0.0;
        if off_center {
            player.position = center.add_vector(player.position).scale(0.5);
            player.velocity = Vec3::new(0.0, (-0.125_f64 - 0.08) * f64::from(0.98_f32), 0.0);
        } else {
            player.position = Vec3::new(x + 0.5, y + 1.0, z + 0.5);
            player.velocity = Trajectory::new(horizontal, vertical).launch_motion(direction);
            player.ejector_fall = true;
            if game.armor[1].as_ref().is_some_and(|stack| stack.item.as_ref() == "minecraft:elytra") {
                let yaw = match direction {
                    Direction::East => 270.0,
                    Direction::North => 180.0,
                    Direction::West => 90.0,
                    _ => 0.0,
                };
                game.yaw = yaw;
                game.pitch = -35.0;
                player.yaw = yaw;
                player.head_yaw = yaw;
                player.pitch = -35.0;
                player.velocity = player.velocity.scale(0.75);
                player.fall_flying = true;
                player.fall_fly_ticks = 0;
            }
        }
    }
}

pub(super) fn receive_player_launch(game: &mut Game<'_>, uuid: u128, channel: &str, data: &[u8]) {
    if channel != PLAYER_LAUNCH || data.len() > 64 {
        return;
    }
    let Ok(pos) = serde_json::from_slice::<[i32; 3]>(data) else {
        return;
    };
    let [x, y, z] = pos.map(f64::from);
    let nearby = game.native_server_players().iter().any(|player| {
        let [px, py, pz] = player.position;
        player.uuid == uuid && player.dimension == game.native_dimension()
            && player.game_mode < 2 && !player.flying && player.health > 0.0
            && (px - x - 0.5).abs() < 1.5 && (pz - z - 0.5).abs() < 1.5
            && (0.75..=3.0).contains(&(py - y))
    });
    if !nearby || game.native_block(pos) != EJECTOR
        || game.native_neighbor_signal(game.native_dimension(), pos) != 0
    {
        return;
    }
    let queued = game.native_with_mod_block_entity(pos, |entity| {
        if !charged(entity) || distances(&entity.nbt).0 == 0 {
            return false;
        }
        entity.nbt.insert("LaunchQueued".into(), Tag::Byte(1));
        true
    });
    if queued == Some(true)
        && let Some(host) = &mut game.lan
        && let Some(guest) = host.hub.guests.iter_mut().find(|guest| guest.uuid == uuid)
        && let Some(body) = guest.motion.as_deref_mut()
    {
        // The player's same-tick takeoff sends an airborne move. The preceding
        // contact has already ended the fall and must not count toward landing.
        body.fall_distance = 0.0;
        body.ejector_fall = true;
        if guest.armor[1].as_ref().is_some_and(|stack| stack.item.as_ref() == "minecraft:elytra") {
            guest.fall_flying = true;
            body.fall_flying = true;
        }
    }
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity, rpm: f32) {
    let Some(direction) = facing(game, game.world.block(pos[0], pos[1], pos[2])) else {
        return;
    };
    collect_landed_stacks(game, pos, entity);
    advance_incoming(game, pos, entity);
    let mut state = name(&entity.nbt);
    let old_lid = lid(&entity.nbt);
    let mut previous_lid = old_lid;
    let mut next_lid = old_lid;
    let (horizontal, vertical) = distances(&entity.nbt);
    let trajectory = Trajectory::new(horizontal, vertical);
    let total_time = trajectory.time.max(3.0) as f32;
    let mut flying = flight(&entity.nbt);
    let target = target(pos, direction, horizontal, vertical);
    let above = offset(pos, [0, 1, 0]);
    let outlet = create_belt_funnel::outlet(game, above);
    let launch_side = direction.opposite();
    if let Some(side) = outlet.filter(|side| *side != launch_side)
        && float(&entity.nbt, "BeltPosition").is_some_and(|at| 0.5 - at < 1.0 / 16.0)
        && entity.items.first().is_some_and(Option::is_some)
    {
        create_belt_funnel::pull_first(game, above, side, &mut entity.items);
    }

    if state == "CHARGED"
        && (entity.nbt.remove(&"LaunchQueued".into()).is_some()
            || horizontal != 0
                && game.native_neighbor_signal(game.native_dimension(), pos) == 0
                && mob_contact(game, pos))
    {
        launch_mobs(game, pos, direction, &trajectory);
        if outlet == Some(launch_side) {
            for stack in &mut entity.items {
                if let Some(item) = stack {
                    *stack = create_belt_funnel::pull(game, above, launch_side, item);
                }
            }
            let mut pending = incoming(&entity.nbt);
            pending.retain_mut(|entry| {
                let Some(remainder) = create_belt_funnel::pull(game, above, launch_side, &entry.stack) else {
                    return false;
                };
                entry.stack = remainder;
                true
            });
            save_incoming(&mut entity.nbt, &pending);
        } else {
            for slot in &mut entity.items {
                if let Some(stack) = slot.take() {
                    flying.push((stack, 0));
                }
            }
            flying.extend(incoming(&entity.nbt).into_iter().map(|entry| (entry.stack, 0)));
            entity.nbt.remove(&"Incoming".into());
        }
        state = "LAUNCHING".into();
        let at = pos.map(|coordinate| f64::from(coordinate) + 0.5);
        game.native_play_sound_in_place("minecraft:block.wooden_trapdoor.close", at, 4, 0.35, 1.0);
        game.native_play_sound_in_place("minecraft:block.chest.open", at, 4, 0.1, 1.4);
    }
    let mut first = true;
    flying.retain_mut(|(stack, ticks)| {
        let hit = if std::mem::take(&mut first) {
            impact(game, &trajectory, pos, direction, *ticks)
        } else {
            None
        };
        if let Some(hit) = hit {
            set_float(&mut entity.nbt, "EarlyTargetTime", hit.age);
            entity
                .nbt
                .insert("EarlyTargetPos".into(), Tag::IntArray(hit.block.to_vec()));
            entity.nbt.insert(
                "EarlyTarget".into(),
                Tag::List(
                    hit.drop_at
                        .into_iter()
                        .map(|axis| Tag::Double(axis.to_bits()))
                        .collect(),
                ),
            );
            let end = f64::from(hit.age.min(total_time));
            deliver(
                game,
                hit.block,
                stack.clone(),
                (hit.drop_at, trajectory.velocity(end, direction)),
            );
            false
        } else if *ticks > total_time as i32 {
            let end = f64::from(total_time);
            let drop_at = trajectory.world_point(pos, direction, end).components();
            let motion = trajectory.velocity(end, direction);
            deliver(game, target, stack.clone(), (drop_at, motion));
            false
        } else {
            *ticks += 1;
            true
        }
    });
    match state.as_str() {
        "LAUNCHING" => {
            next_lid += (1.0 - next_lid) * 0.8;
            if next_lid > 1.0 - 1.0 / 16.0 {
                next_lid = 1.0;
                previous_lid = next_lid;
                state = "RETRACTING".into();
            }
        }
        "RETRACTING" => {
            if old_lid == 0.0 {
                state = "CHARGED".into();
            }
            let distance = ((horizontal * horizontal + vertical * vertical) as f32)
                .sqrt()
                .max(1.0);
            let windup_speed = rpm.abs() / 256.0 / distance;
            next_lid = (next_lid - windup_speed).max(0.0);
            let sound_rate = ((1.0 / (windup_speed * 5.0)) as i32).wrapping_add(1);
            if (game.world.game_time as i32) % sound_rate == 0 {
                let at = pos.map(|coordinate| f64::from(coordinate) + 0.5);
                game.native_play_sound_in_place(
                    "minecraft:block.wooden_button.click_off",
                    at,
                    4,
                    0.125,
                    1.5 - next_lid,
                );
            }
        }
        "CHARGED" => {
            let position = float(&entity.nbt, "BeltPosition").unwrap_or(0.0);
            let was_held = int(&entity.nbt, "SpoutLocked") == Some(1);
            if let Some(stack) = entity.items.first_mut().and_then(Option::as_mut) {
                let step = 0.5 - position;
                let can_press = step < 1.0 / 16.0;
                let mut held = false;
                let mut filled = false;
                if can_press {
                    match create_spout::offer(game, offset(pos, [0, 2, 0]), stack, was_held) {
                        Action::Hold => held = true,
                        Action::Output(out) => {
                            filled = true;
                            if stack.count == 0 {
                                *stack = out;
                            } else {
                                let limit = game.native_max_stack_size(&out.item).unwrap_or(64);
                                let left = super::create_machines::insert(
                                    &mut entity.items[1..],
                                    &out,
                                    limit,
                                );
                                if left > 0 {
                                    game.add_item_entity(
                                        ItemStack { count: left, ..out },
                                        pos.map(|axis| f64::from(axis) + 0.5),
                                        None,
                                        10,
                                    );
                                }
                            }
                        }
                        Action::Pass => {}
                    }
                }
                entity
                    .nbt
                    .insert("SpoutLocked".into(), Tag::Byte(i8::from(held)));
                let centered = if filled {
                    0.5
                } else if step > 1.0 / 512.0 {
                    position + step / 4.0
                } else {
                    position
                };
                if centered != position {
                    set_float(&mut entity.nbt, "BeltPosition", centered);
                }
                let minimum = stack_size(Some(entity)) as u32;
                let full = entity.items.iter().flatten().map(|s| s.count).sum::<u32>() >= minimum;
                let powered = game.native_neighbor_signal(game.native_dimension(), pos) > 0;
                if !held
                    && full
                    && !powered
                    && centered >= 0.49
                    && entity.items[0].as_ref().is_some_and(|stack| {
                        (outlet != Some(launch_side)
                            || create_belt_funnel::can_pull_all(game, above, launch_side, stack))
                            && target_accepts(game, target, stack)
                    })
                {
                    entity.nbt.insert("LaunchQueued".into(), Tag::Byte(1));
                }
            }
        }
        _ => {}
    }
    entity
        .nbt
        .insert("State".into(), Tag::String(state.as_str().into()));
    entity.nbt.insert(
        "LaunchedItems".into(),
        Tag::List(
            flying
                .iter()
                .map(|(item, age)| payload(item, *age))
                .collect(),
        ),
    );
    let nbt = entity
        .nbt
        .entry("Lid".into())
        .or_insert(Tag::Compound(Compound::new()));
    if let Tag::Compound(lid) = nbt {
        set_float(lid, "Previous", previous_lid);
        set_float(lid, "Value", next_lid);
    }
    game.native_block_entity_sync(pos);
}

pub(super) fn models(models: &mut Vec<String>) {
    models.push(LID.into());
}

pub(super) fn update_tag(entity: &ModBlockEntity) -> Compound {
    let mut tag = Compound::new();
    set_float(&mut tag, "VisualSpeed", reading(entity, 0));
    tag.insert("ScrollValue".into(), Tag::Int(stack_size(Some(entity))));
    for key in [
        "State",
        "HorizontalDistance",
        "VerticalDistance",
        "LaunchedItems",
        "Lid",
        "BeltPosition",
    ] {
        if let Some(value) = entity.nbt.get(&key.into()) {
            tag.insert(key.into(), value.clone());
        }
    }
    if let Some(stack) = entity.items.first().and_then(Option::as_ref) {
        tag.insert("Held".into(), encode(stack));
    }
    tag
}

pub(super) fn render(
    game: &Game<'_>,
    state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    let Some(direction) = facing(game, state) else {
        return;
    };
    let yaw = match direction {
        Direction::East => -90.0,
        Direction::North => 0.0,
        Direction::West => 90.0,
        _ => 180.0,
    };
    let axis = if matches!(direction, Direction::East | Direction::West) {
        2
    } else {
        0
    };
    let rpm = float(&entity.nbt, "VisualSpeed").unwrap_or(0.0);
    let spin = super::create_visuals::wheel_angle(draw.game_time, draw.partial, rpm, 0.0);
    super::create_visuals::draw_rotating(game, draw, axis, spin, SHAFT);
    let lift = lid(&entity.nbt);
    let previous = compound(&entity.nbt, "Lid")
        .and_then(|nbt| float(nbt, "Previous"))
        .unwrap_or(lift);
    let progress = previous + (lift - previous) * draw.partial;
    let angle = -70.0 * progress;
    let trace = std::env::var_os("CREATE_EJECTOR_LID_RENDER").is_some();
    let base = trace.then(|| draw.pose().inverse());
    let start = draw.vertices_mut().len();
    draw.push();
    draw.rotate_about([0.0, 1.0, 0.0], yaw, [0.5; 3]);
    draw.rotate_about([1.0, 0.0, 0.0], angle, [0.0, 11.25 / 16.0, 0.75 / 16.0]);
    game.native_draw_model(draw, LID, 0xffffff);
    if let Some(base) = base {
        let pose = base * draw.pose();
        let points = [glam::Vec3::ZERO, glam::Vec3::X, glam::Vec3::Y, glam::Vec3::Z]
            .map(|point| pose.transform_point3(point).to_array());
        let vertices = draw.vertices_mut().len() - start;
        let tick = draw.game_time;
        let normal = direction.normal();
        eprintln!("CREATE_EJECTOR_LID_HORIZON {tick},{},{},{progress:.8},{vertices},{points:?}", normal[0], normal[2]);
    }
    if let Some(stack) = compound(&entity.nbt, "Held").and_then(ItemStack::from_nbt) {
        draw.translate([0.5, 0.9, 0.5]);
        draw.rotate_about([1.0, 0.0, 0.0], 90.0, [0.0; 3]);
        draw.scale([0.5; 3]);
        game.native_draw_item(draw, &stack, DisplayContext::Fixed, None, 0);
    }
    draw.pop();
    let (horizontal, vertical) = distances(&entity.nbt);
    let trajectory = Trajectory::new(horizontal, vertical);
    let along = direction.normal().map(|component| component as f32);
    let facing_angle = match direction {
        Direction::North => 180.0,
        Direction::East => -270.0,
        Direction::West => -90.0,
        _ => 0.0,
    };
    let max_time = trajectory.time as f32;
    let item_pivot = [0.0, 2.0 / 16.0, -1.0 / 16.0];
    let flight_base = std::env::var_os("CREATE_EJECTOR_FLIGHT_RENDER")
        .is_some()
        .then(|| draw.pose().inverse());
    for (stack, age) in flight(&entity.nbt) {
        let time = age as f32 + draw.partial;
        if time > max_time {
            continue;
        }
        let [distance, height] = trajectory.position(f64::from(time)).map(|value| value as f32);
        draw.push();
        draw.translate([
            0.5 + along[0] * distance,
            0.5 + height,
            0.5 + along[2] * distance,
        ]);
        draw.translate(item_pivot);
        if super::create_package_style::dimensions(&stack.item).is_some() {
            draw.translate([0.0, 4.0 / 16.0, 0.0]);
            draw.scale([1.5; 3]);
            draw.rotate_about([0.0, 1.0, 0.0], time * 20.0, [0.0; 3]);
        } else {
            draw.scale([0.5; 3]);
            draw.rotate_about([0.0, 1.0, 0.0], facing_angle, [0.0; 3]);
            draw.rotate_about([1.0, 0.0, 0.0], time * 40.0, [0.0; 3]);
        }
        draw.translate(item_pivot.map(|component| -component));
        let start = draw.vertices_mut().len();
        game.native_draw_item(draw, &stack, DisplayContext::Fixed, None, 0);
        if let Some(base) = flight_base {
            let pose = base * draw.pose();
            let points = [glam::Vec3::ZERO, glam::Vec3::X, glam::Vec3::Y, glam::Vec3::Z]
                .map(|point| pose.transform_point3(point).to_array());
            let vertices = draw.vertices_mut().len() - start;
            let normal = direction.normal();
            eprintln!("CREATE_EJECTOR_FLIGHT_RENDER {},{},{},{time:.9},{max_time:.9},{vertices},{points:?}",
                normal[0], normal[2], stack.item);
        }
        draw.pop();
    }
}
