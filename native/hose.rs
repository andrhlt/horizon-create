use std::collections::{BTreeSet, VecDeque};

use horizon_core::geometry::Direction;
use horizon_core::position::BlockPos;
use horizon_core::ticks::TickArea;
use horizon_world::level::flags;
use horizon_world::nbt::{Compound, Tag};

use crate::containers::ModBlockEntity;

use super::Game;
use super::create_depot::compound;
use super::create_fan::facing;
use super::create_fluids::{BUCKET, Fluid, read_fluid};
use super::create_machines::{float, int, mod_entity, offset, set_float};

pub(super) const HOSE: &str = "create:hose_pulley";
pub(super) const CAPACITY: i32 = 1500;
const RANGE_SQUARED: i32 = 128 * 128;
const SEARCH_BATCH: usize = 1024;
const BODY_LIMIT: usize = 10000;
const WATER: &str = "minecraft:water";
const LAVA: &str = "minecraft:lava";
// Create's default BottomlessFluidMode is ALLOW_BY_TAG, whose pinned tag
// contains both vanilla fluids.
const BOTTOMLESS_FLUIDS: [&str; 2] = [WATER, LAVA];
const UPDATE_FLUID: i32 = flags::UPDATE_CLIENTS | flags::UPDATE_KNOWN_SHAPE;

pub(super) fn pipe_face(game: &Game<'_>, pos: [i32; 3]) -> Option<Direction> {
    Some(
        match facing(game, game.world.block(pos[0], pos[1], pos[2]))? {
            Direction::North => Direction::West,
            Direction::South => Direction::East,
            Direction::West => Direction::South,
            Direction::East => Direction::North,
            _ => return None,
        },
    )
}

pub(super) fn load_structure(nbt: &mut Compound) {
    for name in ["LastPos", "AffectedAreaFrom", "AffectedAreaTo"] {
        nbt.remove(&name.into());
    }
}

pub(super) fn tick(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
    rpm: f32,
    changed: bool,
) {
    let old = hose_length(entity);
    let new = if changed && rpm == 0.0 {
        old.round()
    } else {
        (old + rpm / 512.0).max(0.0)
    };
    let end = offset(pos, [0, -(new.ceil() as i32), 0]);
    let blocked = new > 0.0
        && !game
            .res
            .behaviours()
            .is_replaceable(game.world.block(end[0], end[1], end[2]));
    let length = if blocked { new.floor() } else { new };
    let moving = rpm != 0.0 && !blocked && new > 0.0;
    entity
        .nbt
        .insert("Moving".into(), Tag::Byte(i8::from(moving)));
    if changed || old != length {
        let mut value = Compound::new();
        set_float(&mut value, "Value", length);
        entity.nbt.insert("Offset".into(), Tag::Compound(value));
        if moving {
            entity.nbt.remove(&"HoseFillQueue".into());
            entity.nbt.remove(&"HoseFillVisited".into());
            entity.nbt.remove(&"HoseDrainQueue".into());
            entity.nbt.remove(&"HoseInfinite".into());
            entity.nbt.remove(&"HoseDrainReady".into());
        }
        game.native_block_entity_sync(pos);
    }
}

fn hose_length(entity: &ModBlockEntity) -> f32 {
    compound(&entity.nbt, "Offset")
        .and_then(|offset| float(offset, "Value"))
        .unwrap_or(0.0)
}

fn root(pos: [i32; 3], entity: &ModBlockEntity) -> [i32; 3] {
    offset(pos, [0, -(hose_length(entity).ceil() as i32), 0])
}

pub(super) fn contents(entity: &ModBlockEntity) -> Option<Fluid> {
    read_fluid(compound(compound(&entity.nbt, "Tank")?, "Fluid")?)
}

fn store(entity: &mut ModBlockEntity, fluid: &Fluid) {
    let mut tank = Compound::new();
    if fluid.amount > 0 {
        tank.insert("Fluid".into(), fluid.nbt());
    }
    entity.nbt.insert("Tank".into(), Tag::Compound(tank));
}

fn world_fluid(game: &Game<'_>, pos: [i32; 3]) -> Option<(&'static str, bool)> {
    let block = game.native_block(pos);
    if block == WATER || block == LAVA {
        return Some((
            if block == WATER { WATER } else { LAVA },
            game.native_block_property(pos, "level").as_deref() == Some("0"),
        ));
    }
    (game.native_block_property(pos, "waterlogged").as_deref() == Some("true"))
        .then_some((WATER, true))
}

pub(super) fn supply(game: &Game<'_>, pos: [i32; 3]) -> Option<Fluid> {
    let entity = mod_entity(game, pos)?;
    let stored = contents(entity);
    if int(&entity.nbt, "Moving") == Some(1)
        || stored.as_ref().is_some_and(|fluid| fluid.amount >= BUCKET)
    {
        return stored;
    }
    let Some((id, _)) = world_fluid(game, root(pos, entity)) else {
        return stored;
    };
    let mut fluid = stored.unwrap_or(Fluid {
        id: id.into(),
        amount: 0,
        components: None,
    });
    if fluid.id == id {
        fluid.amount += BUCKET;
    }
    Some(fluid)
}

pub(super) fn drain_ready(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    let now = game.world.game_time;
    game.native_with_mod_block_entity(pos, |entity| {
        if contents(entity).is_some() {
            return true;
        }
        // The network discovers the inlet as the hose validates its fluid body.
        let ready = entity
            .nbt
            .entry("HoseDrainReady".into())
            .or_insert(Tag::Long(now + 3));
        matches!(ready, Tag::Long(ready) if *ready <= now)
    })
    .unwrap_or(false)
}

#[derive(Clone, Copy)]
struct Entry {
    pos: [i32; 3],
    distance: i32,
}

fn distance_squared(a: [i32; 3], b: [i32; 3]) -> i32 {
    a.into_iter().zip(b).map(|(a, b)| (a - b) * (a - b)).sum()
}

struct Queue {
    heap: Vec<Entry>,
    root: [i32; 3],
    sign: i32,
}

impl Queue {
    fn key(&self, entry: Entry) -> (i32, i32, i32) {
        (
            entry.pos[1] * self.sign,
            entry.distance * self.sign,
            distance_squared(entry.pos, self.root) * self.sign,
        )
    }

    fn push(&mut self, entry: Entry) {
        let key = self.key(entry);
        let mut index = self.heap.len();
        self.heap.push(entry);
        while index > 0 {
            let parent = (index - 1) / 2;
            if key >= self.key(self.heap[parent]) {
                break;
            }
            self.heap[index] = self.heap[parent];
            index = parent;
        }
        self.heap[index] = entry;
    }

    fn pop(&mut self) -> Option<Entry> {
        let first = *self.heap.first()?;
        let last = self.heap.pop()?;
        if self.heap.is_empty() {
            return Some(first);
        }
        let key = self.key(last);
        let mut index = 0;
        while index * 2 + 1 < self.heap.len() {
            let mut child = index * 2 + 1;
            if child + 1 < self.heap.len()
                && self.key(self.heap[child + 1]) < self.key(self.heap[child])
            {
                child += 1;
            }
            if key <= self.key(self.heap[child]) {
                break;
            }
            self.heap[index] = self.heap[child];
            index = child;
        }
        self.heap[index] = last;
        Some(first)
    }

    fn load(entity: &ModBlockEntity, label: &str, root: [i32; 3], sign: i32) -> Self {
        let heap = match entity.nbt.get(&label.into()) {
            Some(Tag::IntArray(entries)) => entries
                .chunks_exact(4)
                .map(|entry| Entry {
                    pos: [entry[0], entry[1], entry[2]],
                    distance: entry[3],
                })
                .collect(),
            _ => Vec::new(),
        };
        Self { heap, root, sign }
    }

    fn save(&self, entity: &mut ModBlockEntity, label: &str) {
        let values = self
            .heap
            .iter()
            .flat_map(|entry| [entry.pos[0], entry.pos[1], entry.pos[2], entry.distance])
            .collect();
        entity.nbt.insert(label.into(), Tag::IntArray(values));
    }
}

fn discover_fluid(game: &Game<'_>, queue: &mut Queue, fluid: &Fluid) -> bool {
    let mut frontier = VecDeque::from([Entry {
        pos: queue.root,
        distance: 0,
    }]);
    let mut visited = BTreeSet::new();
    while let Some(entry) = frontier.pop_front() {
        if !visited.insert(entry.pos) {
            continue;
        }
        if !game.world.loaded(entry.pos[0], entry.pos[2]) {
            continue;
        }
        let Some((_, source)) = world_fluid(game, entry.pos).filter(|(id, _)| *id == fluid.id)
        else {
            continue;
        };
        if source {
            queue.push(entry);
        }
        if visited.len() >= BODY_LIMIT && BOTTOMLESS_FLUIDS.contains(&fluid.id.as_str()) {
            return true;
        }
        for direction in Direction::ALL
            .into_iter()
            .filter(|direction| *direction != Direction::Down)
        {
            let next = offset(entry.pos, direction.normal());
            if !visited.contains(&next)
                && distance_squared(queue.root, next) <= RANGE_SQUARED
                && world_fluid(game, next).is_some_and(|(id, source)| {
                    id == fluid.id
                        && (source
                            || direction != Direction::Up
                            || (next[0] == queue.root[0] && next[2] == queue.root[2]))
                })
            {
                frontier.push_back(Entry {
                    pos: next,
                    distance: entry.distance + 1,
                });
            }
        }
    }
    false
}

pub(super) fn drain(game: &mut Game<'_>, pos: [i32; 3], fluid: &Fluid, amount: i32) -> i32 {
    let Some(mut entity) = mod_entity(game, pos).cloned() else {
        return 0;
    };
    let drained = {
        let mut stored = contents(&entity).unwrap_or_else(|| Fluid {
            amount: 0,
            ..fluid.clone()
        });
        if stored.amount < BUCKET && int(&entity.nbt, "Moving") != Some(1) {
            let root = root(pos, &entity);
            let mut queue = Queue::load(&entity, "HoseDrainQueue", root, -1);
            let mut infinite = int(&entity.nbt, "HoseInfinite") == Some(1);
            if queue.heap.is_empty() && !infinite {
                infinite = discover_fluid(game, &mut queue, fluid);
                entity
                    .nbt
                    .insert("HoseInfinite".into(), Tag::Byte(i8::from(infinite)));
            }
            if infinite {
                stored.amount += BUCKET;
            } else {
                while let Some(entry) = queue.pop() {
                    if world_fluid(game, entry.pos) != Some((fluid.id.as_str(), true)) {
                        continue;
                    }
                    if let Some(state) = if game
                        .native_block_property(entry.pos, "waterlogged")
                        .is_some()
                    {
                        let state = game.world.block(entry.pos[0], entry.pos[1], entry.pos[2]);
                        game.with_level(|_, level, _| {
                            level.native_state_with_property(state, "waterlogged", "false")
                        })
                    } else {
                        game.native_default_state("minecraft:air")
                    } {
                        game.native_set_block(
                            game.native_dimension(),
                            entry.pos,
                            state,
                            UPDATE_FLUID,
                        );
                        stored.amount += BUCKET;
                        break;
                    }
                }
                queue.save(&mut entity, "HoseDrainQueue");
            }
        }
        let drained = stored.amount.min(amount);
        stored.amount -= drained;
        store(&mut entity, &stored);
        drained
    };
    game.native_with_mod_block_entity(pos, |target| target.nbt = std::mem::take(&mut entity.nbt));
    drained
}

#[derive(PartialEq, Eq)]
enum Space {
    Empty,
    Filled,
    Blocked,
}

fn space(game: &Game<'_>, pos: [i32; 3], fluid: &Fluid) -> Space {
    if !game.world.loaded(pos[0], pos[2]) {
        return Space::Blocked;
    }
    if let Some((id, still)) = world_fluid(game, pos) {
        return if still && id == fluid.id {
            Space::Filled
        } else if still {
            Space::Blocked
        } else {
            Space::Empty
        };
    }
    if game.native_block_property(pos, "waterlogged").as_deref() == Some("false")
        && fluid.id == WATER
        || game
            .res
            .behaviours()
            .is_replaceable(game.world.block(pos[0], pos[1], pos[2]))
    {
        Space::Empty
    } else {
        Space::Blocked
    }
}

pub(super) fn fill(game: &mut Game<'_>, pos: [i32; 3], mut fluid: Fluid) {
    let Some(mut entity) = mod_entity(game, pos).cloned() else {
        return;
    };
    {
        if fluid.amount >= BUCKET && int(&entity.nbt, "Moving") != Some(1) {
            let root = root(pos, &entity);
            let mut queue = Queue::load(&entity, "HoseFillQueue", root, 1);
            let mut visited: BTreeSet<[i32; 3]> = match entity.nbt.get(&"HoseFillVisited".into()) {
                Some(Tag::IntArray(entries)) => entries
                    .chunks_exact(3)
                    .map(|p| [p[0], p[1], p[2]])
                    .collect(),
                _ => BTreeSet::new(),
            };
            if queue.heap.is_empty() {
                queue.push(Entry {
                    pos: root,
                    distance: 0,
                });
                visited.clear();
            }
            for _ in 0..SEARCH_BATCH {
                let Some(entry) = queue.pop() else { break };
                if !visited.insert(entry.pos) || visited.len() >= BODY_LIMIT {
                    continue;
                }
                let here = space(game, entry.pos, &fluid);
                if here == Space::Blocked {
                    continue;
                }
                if here == Space::Empty {
                    if fluid.id == WATER && game.native_dimension() == "minecraft:the_nether" {
                        fluid.amount -= BUCKET;
                    } else if let Some(state) = if game
                        .native_block_property(entry.pos, "waterlogged")
                        .is_some()
                        && fluid.id == WATER
                    {
                        let state = game.world.block(entry.pos[0], entry.pos[1], entry.pos[2]);
                        game.with_level(|_, level, _| {
                            level.native_state_with_property(state, "waterlogged", "true")
                        })
                    } else {
                        game.native_default_state(&fluid.id)
                    } {
                        if game.native_set_block(
                            game.native_dimension(),
                            entry.pos,
                            state,
                            UPDATE_FLUID,
                        ) {
                            let [x, y, z] = entry.pos;
                            let at = BlockPos::new(x, y, z);
                            game.with_level(|_, _, ticks| {
                                ticks.fluids.clear_area(TickArea::new(at, at))
                            });
                            fluid.amount -= BUCKET;
                        }
                    }
                }
                for direction in Direction::ALL
                    .into_iter()
                    .filter(|direction| *direction != Direction::Up)
                {
                    let next = offset(entry.pos, direction.normal());
                    if !visited.contains(&next)
                        && distance_squared(root, next) <= RANGE_SQUARED
                        && space(game, next, &fluid) != Space::Blocked
                    {
                        queue.push(Entry {
                            pos: next,
                            distance: entry.distance + 1,
                        });
                    }
                }
                if here == Space::Empty {
                    break;
                }
            }
            queue.save(&mut entity, "HoseFillQueue");
            entity.nbt.insert(
                "HoseFillVisited".into(),
                Tag::IntArray(visited.into_iter().flatten().collect()),
            );
        }
        store(&mut entity, &fluid);
    }
    game.native_with_mod_block_entity(pos, |target| target.nbt = std::mem::take(&mut entity.nbt));
}

const COIL: &str = "create:block/hose_pulley/hose_coil";
const ROPE: &str = "create:block/hose_pulley/rope";
const HALF_ROPE: &str = "create:block/hose_pulley/rope_half";
const MAGNET: &str = "create:block/hose_pulley/pulley_magnet";
const HALF_MAGNET: &str = "create:block/hose_pulley/rope_half_magnet";

pub(super) fn models(models: &mut Vec<String>) {
    models.extend([COIL, ROPE, HALF_ROPE, MAGNET, HALF_MAGNET].map(String::from));
}

pub(super) fn update_tag(entity: &ModBlockEntity) -> Compound {
    let mut tag = Compound::new();
    for key in ["Offset", "Speed"] {
        if let Some(value) = entity.nbt.get(&key.into()) {
            tag.insert(key.into(), value.clone());
        }
    }
    tag
}

pub(super) fn render(
    game: &Game<'_>,
    state: horizon_world::registry::BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut super::native_block_entity_draw::BlockEntityDraw,
) {
    let Some(front) = facing(game, state) else {
        return;
    };
    draw.push();
    if matches!(front, Direction::West | Direction::East) {
        draw.rotate_about([0.0, 1.0, 0.0], 90.0, [0.5; 3]);
    }
    game.native_draw_model(draw, COIL, 0xFFFFFF);
    draw.pop();

    render_cable(
        game,
        draw,
        hose_length(entity).max(3.0 / 16.0),
        [ROPE, HALF_ROPE, MAGNET, HALF_MAGNET],
    );
}

pub(super) fn render_cable(
    game: &Game<'_>,
    draw: &mut super::native_block_entity_draw::BlockEntityDraw,
    length: f32,
    [rope, half_rope, magnet, half_magnet]: [&str; 4],
) {
    let mut draw_at = |height: f32, model: &str| {
        draw.push();
        draw.translate([0.0, -height, 0.0]);
        game.native_draw_model(draw, model, 0xFFFFFF);
        draw.pop();
    };
    draw_at(length, if length > 0.25 { magnet } else { half_magnet });
    let fraction = length.fract();
    if length > 0.75 && !(0.25..=0.75).contains(&fraction) {
        draw_at(
            if fraction > 0.75 {
                fraction - 1.0
            } else {
                fraction
            },
            half_rope,
        );
    }
    for segment in 0..(length - 1.25).ceil().max(0.0) as u32 {
        draw_at(length - segment as f32 - 1.0, rope);
    }
}

pub(super) fn place(
    level: &super::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    context: &horizon_world::level::PlacementContext,
) -> Option<horizon_world::registry::BlockStateId> {
    if level.registry.state(state)?.name != HOSE {
        return None;
    }
    let mut preferred: Option<Direction> = None;
    for direction in [
        Direction::North,
        Direction::East,
        Direction::South,
        Direction::West,
    ] {
        let n = direction.normal();
        let state = level
            .world
            .block(context.pos.x + n[0], context.pos.y, context.pos.z + n[2]);
        let Some(pipe) = level.registry.state(state) else {
            continue;
        };
        let axis = if n[0] == 0 { "z" } else { "x" };
        let connects = match pipe.name.as_str() {
            super::create_fluids::GLASS_PIPE => pipe
                .properties
                .get("axis")
                .is_some_and(|value| value == axis),
            super::create_encased_fluid_pipe::BLOCK => pipe
                .properties
                .get(super::create_fluids::name(direction.opposite()))
                .is_some_and(|value| value == "true"),
            super::create_fluids::PIPE
            | super::create_fluids::PUMP
            | super::create_fluids::SMART_PIPE => true,
            _ => false,
        };
        if connects {
            if preferred.is_some_and(|old| old.normal()[0].abs() != n[0].abs()) {
                preferred = None;
                break;
            }
            preferred = Some(direction);
        }
    }
    let default =
        ["north", "east", "south", "west"][(context.yaw / 90.0).round() as i32 as usize & 3];
    let front = match preferred {
        Some(Direction::East) => "south",
        Some(Direction::South) => "west",
        Some(Direction::West) => "north",
        Some(Direction::North) => "east",
        _ => default,
    };
    level.native_state_with_property(state, "facing", front)
}

pub(super) fn bounds(_pos: [i32; 3], entity: &ModBlockEntity, bounds: &mut [f32; 6]) {
    bounds[1] = bounds[1].min(-hose_length(entity));
}
