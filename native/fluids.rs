use std::collections::{BTreeSet, VecDeque};

use horizon_core::geometry::{Aabb, Direction, Vec3};
use horizon_world::level::flags;
use horizon_world::nbt::{Compound, Tag};

use crate::containers::ModBlockEntity;
use crate::items::ItemStack;

use super::Game;
use super::create_depot::compound;
use super::create_fan::facing;
use super::create_fluid_tank::{self, CREATIVE, TANK};
use super::create_hose::{self, HOSE};
use super::create_encased_fluid_pipe::{self, BLOCK as ENCASED_PIPE};
use super::create_machines::{float, int, mod_entity, offset, set_float};
use super::create_portable_interface::{self, FLUID as PORTABLE_INTERFACE};
use super::create_spout::{self, SPOUT};
use super::create_item_drain::{self, DRAIN};
use super::create_threshold_switch::delta;

use super::create_valve::{self, VALVE};

pub(super) const PUMP: &str = "create:mechanical_pump";
pub(super) const GLASS_PIPE: &str = "create:glass_fluid_pipe";
pub(super) const SMART_PIPE: &str = "create:smart_fluid_pipe";
pub(super) const PIPE: &str = "create:fluid_pipe";
pub(super) const BASIN: &str = "create:basin";
pub(super) const PUMP_MODEL: &str = "create:block/mechanical_pump/cog";
pub(super) const RANGE: i32 = 16;
pub(super) const BUCKET: i32 = 1000;
const WATER: &str = "minecraft:water";

#[derive(Clone)]
pub(super) struct Fluid {
    pub(super) id: String,
    pub(super) amount: i32,
    pub(super) components: Option<Compound>,
}

impl Fluid {
    pub(super) fn nbt(&self) -> Tag {
        let mut data = Compound::new();
        data.insert("id".into(), Tag::String(self.id.as_str().into()));
        data.insert("amount".into(), Tag::Int(self.amount));
        if let Some(components) = &self.components {
            data.insert("components".into(), Tag::Compound(components.clone()));
        }
        Tag::Compound(data)
    }

    pub(super) fn same_variant(&self, other: &Self) -> bool {
        self.id == other.id && self.components == other.components
    }
}

fn string(nbt: &Compound, key: &str) -> Option<String> {
    if let Tag::String(name) = nbt.get(&key.into())? {
        Some(name.to_string_lossy())
    } else {
        None
    }
}

pub(super) fn load_structure(nbt: &mut Compound) {
    if string(nbt, "id").as_deref() == Some(PUMP) {
        // A template's saved rotation belongs to its old network.
        set_float(nbt, "Speed", 0.0);
    }
}

pub(super) fn read_fluid(nbt: &Compound) -> Option<Fluid> {
    let id = string(nbt, "id")?;
    let amount = int(nbt, "amount").or_else(|| int(nbt, "Amount"))?;
    (amount > 0).then_some(Fluid {
        id,
        amount,
        components: compound(nbt, "components").cloned(),
    })
}

pub(super) fn name(face: Direction) -> &'static str {
    match face {
        Direction::Up => "up",
        Direction::Down => "down",
        Direction::North => "north",
        Direction::South => "south",
        Direction::West => "west",
        Direction::East => "east",
    }
}

fn adjacent(pos: [i32; 3], face: Direction) -> [i32; 3] {
    offset(pos, delta(face))
}

fn along(face: Direction) -> &'static str {
    match face {
        Direction::Up | Direction::Down => "y",
        Direction::East | Direction::West => "x",
        _ => "z",
    }
}

pub(super) fn open_to(game: &Game<'_>, pos: [i32; 3], face: Direction) -> bool {
    match game.native_block(pos).as_str() {
        SMART_PIPE => game
            .native_block_property(pos, "facing")
            .and_then(|facing| super::create_machines::facing_axis(&facing))
            .is_some_and(|axis| face.normal()[axis] != 0),
        VALVE => create_valve::pipe_axis(game, pos).is_some_and(|axis| face.normal()[axis] != 0),
        GLASS_PIPE => game.native_block_property(pos, "axis").as_deref() == Some(along(face)),
        PIPE | ENCASED_PIPE => game.native_block_property(pos, name(face)).as_deref() == Some("true"),
        PUMP => facing(game, game.world.block(pos[0], pos[1], pos[2]))
            .is_some_and(|towards| along(towards) == along(face)),
        _ => false,
    }
}

pub(super) fn fluid_block(game: &Game<'_>, pos: [i32; 3]) -> bool {
    matches!(
        game.native_block(pos).as_str(),
        GLASS_PIPE | PIPE | ENCASED_PIPE | PUMP | VALVE | SMART_PIPE
    )
}

pub(super) fn incoming_matches(
    game: &Game<'_>,
    pos: [i32; 3],
    mut matches: impl FnMut(&Fluid) -> bool,
) -> bool {
    let Some(entity) = mod_entity(game, pos) else {
        return false;
    };
    Direction::ALL.into_iter().any(|face| {
        let side = port(entity, face);
        let (inbound, _) = pressure(&side);
        inbound && flow(&side).is_some_and(|(fluid, progress)| progress >= 1.0 && matches(&fluid))
    })
}

fn open_space(game: &Game<'_>, pos: [i32; 3]) -> bool {
    let state = game.world.block(pos[0], pos[1], pos[2]);
    game.world.loaded(pos[0], pos[2]) && game.res.behaviours().is_replaceable(state)
}

pub(super) fn basin_tanks(entity: &ModBlockEntity, output: bool) -> [Option<Fluid>; 2] {
    let key = if output { "OutputTanks" } else { "InputTanks" };
    let Some(Tag::List(tanks)) = entity.nbt.get(&key.into()) else {
        return [None, None];
    };
    std::array::from_fn(|i| {
        let Tag::Compound(tank) = tanks.get(i)? else {
            return None;
        };
        read_fluid(compound(compound(tank, "TankContent")?, "Fluid")?)
    })
}

pub(super) fn basin_destination(tanks: &[Option<Fluid>; 2], fluid: &Fluid) -> Option<usize> {
    tanks
        .iter()
        .position(|slot| {
            slot.as_ref()
                .is_some_and(|stored| stored.same_variant(fluid))
        })
        .or_else(|| tanks.iter().position(Option::is_none))
}

pub(super) fn set_basin_fluid(
    entity: &mut ModBlockEntity,
    output: bool,
    slot: usize,
    fluid: Option<Fluid>,
) {
    let key = if output { "OutputTanks" } else { "InputTanks" };
    let tanks = entity.nbt.entry(key.into()).or_insert_with(|| {
        Tag::List(vec![
            Tag::Compound(Compound::new()),
            Tag::Compound(Compound::new()),
        ])
    });
    if let Tag::List(tanks) = tanks {
        tanks.resize_with(2, || Tag::Compound(Compound::new()));
        if let Some(Tag::Compound(tank)) = tanks.get_mut(slot) {
            let mut content = Compound::new();
            if let Some(fluid) = fluid.filter(|fluid| fluid.amount > 0) {
                content.insert("Fluid".into(), fluid.nbt());
            }
            tank.insert("TankContent".into(), Tag::Compound(content));
        }
    }
}

fn basin_source(
    basin: &ModBlockEntity,
    mut accepts: impl FnMut(&Fluid) -> bool,
) -> Option<(bool, usize, Fluid)> {
    for output in [true, false] {
        for (slot, fluid) in basin_tanks(basin, output).into_iter().enumerate() {
            if let Some(fluid) = fluid.filter(&mut accepts) {
                return Some((output, slot, fluid));
            }
        }
    }
    None
}

fn write_basin(game: &mut Game<'_>, pos: [i32; 3], output: bool, slot: usize, fluid: Fluid) {
    let time = game.world.game_time;
    game.native_with_mod_block_entity(pos, |entity| {
        if !output && fluid.amount >= BUCKET {
            entity.nbt.insert(
                format!("InputTank{slot}Refilled").as_str().into(),
                Tag::Long(time),
            );
        }
        set_basin_fluid(entity, output, slot, Some(fluid))
    });
}

pub(super) fn liquid_from_stack(stack: &ItemStack, amount: i32) -> Option<Fluid> {
    let item = stack.item.as_ref();
    if let Some(kind) = horizon_world::fluid::FluidKind::of_bucket(item) {
        return Some(Fluid { id: kind.name().into(), amount, components: None });
    }
    match item {
        "minecraft:milk_bucket" => Some(Fluid { id: "minecraft:milk".into(), amount, components: None }),
        "minecraft:water_bucket" => Some(Fluid {
            id: WATER.into(),
            amount,
            components: None,
        }),
        "minecraft:lava_bucket" => Some(Fluid {
            id: "minecraft:lava".into(),
            amount,
            components: None,
        }),
        "minecraft:potion" if stack.potion() == Some(WATER) => Some(Fluid {
            id: WATER.into(),
            amount,
            components: None,
        }),
        "minecraft:potion" | "minecraft:splash_potion" | "minecraft:lingering_potion" => {
            let data = stack.data()?;
            let mut contents: Compound = data
                .potion_extra
                .iter()
                .map(|(key, value)| (key.as_str().into(), value.clone()))
                .collect();
            if let Some(potion) = stack.potion() {
                contents.insert("potion".into(), Tag::String(potion.into()));
            }
            if contents.is_empty() {
                return None;
            }
            let contents = Tag::Compound(contents);
            let bottle = match item {
                "minecraft:splash_potion" => "splash",
                "minecraft:lingering_potion" => "lingering",
                _ => "regular",
            };
            Some(Fluid {
                id: "create:potion".into(),
                amount,
                components: Some(Compound::from([
                    ("minecraft:potion_contents".into(), contents),
                    (
                        "create:potion_fluid_bottle_type".into(),
                        Tag::String(bottle.into()),
                    ),
                ])),
            })
        }
        _ => None,
    }
}

fn filter_fluid(entity: &ModBlockEntity, fluid: &Fluid) -> bool {
    if entity.id != SMART_PIPE {
        return true;
    }
    let filter = compound(&entity.nbt, "Filter").and_then(ItemStack::from_nbt);
    filter.is_none_or(|sample| {
        liquid_from_stack(&sample, 1).is_some_and(|want| want.same_variant(fluid))
    })
}

pub(super) fn set_filter(game: &mut Game<'_>, pos: [i32; 3], stack: &ItemStack) -> bool {
    if game.native_block(pos) != SMART_PIPE || liquid_from_stack(stack, 1).is_none() {
        return false;
    }
    let mut sample = stack.clone();
    sample.count = 1;
    if game
        .native_with_mod_block_entity(pos, |pipe| {
            pipe.nbt
                .insert("Filter".into(), super::create_depot::encode(&sample));
        })
        .is_none()
    {
        return false;
    }
    game.native_block_entity_sync(pos);
    game.swing_arm();
    true
}

fn port(entity: &ModBlockEntity, direction: Direction) -> Compound {
    compound(&entity.nbt, name(direction))
        .cloned()
        .unwrap_or_default()
}

fn write_port(entity: &mut ModBlockEntity, direction: Direction, value: Compound) {
    entity
        .nbt
        .insert(name(direction).into(), Tag::Compound(value));
}

fn buffer(port: &Compound) -> Option<Fluid> {
    let endpoint = compound(port, "OpenEnd").or_else(|| compound(port, "RefreshingEnd"))?;
    read_fluid(compound(endpoint, "Fluid")?)
}

fn write_buffer(port: &mut Compound, fluid: Fluid, pull: bool) {
    let mut endpoint = compound(port, "OpenEnd").cloned().unwrap_or_default();
    endpoint.insert("Pulling".into(), Tag::Byte(i8::from(pull)));
    if fluid.amount == 0 {
        endpoint.remove(&"Fluid".into());
    } else {
        endpoint.insert("Fluid".into(), fluid.nbt());
    }
    port.insert("OpenEnd".into(), Tag::Compound(endpoint));
}

fn pressure(port: &Compound) -> (bool, f32) {
    if let Some(Tag::List(values)) = port.get(&"Pressure".into())
        && let [Tag::Float(inward), Tag::Float(outward)] = values.as_slice()
    {
        let inward = f32::from_bits(*inward);
        let outward = f32::from_bits(*outward);
        (inward > outward, inward.max(outward))
    } else {
        (false, 0.0)
    }
}

fn flow(port: &Compound) -> Option<(Fluid, f32)> {
    let flow = compound(port, "Flow")?;
    let fluid = read_fluid(compound(flow, "Fluid")?)?;
    let progress = compound(flow, "Progress")
        .and_then(|progress| float(progress, "Value"))
        .unwrap_or(1.0);
    Some((fluid, progress))
}

fn set_flow(port: &mut Compound, fluid: Option<Fluid>, inbound: bool, rpm: f32, now: i64) {
    let Some(mut fluid) = fluid else {
        port.remove(&"Flow".into());
        port.remove(&"FlowReached".into());
        return;
    };
    let previous = flow(port)
        .filter(|(last, _)| last.same_variant(&fluid))
        .map_or(0.0, |(_, progress)| progress);
    let progress = (previous + 1.0 / 32.0 + (rpm / 128.0).clamp(0.0, 1.0) * 31.0 / 32.0).min(1.0);
    if progress >= 1.0 && previous < 1.0 {
        port.insert("FlowReached".into(), Tag::Long(now));
    }
    fluid.amount = 1;
    let mut value = Compound::new();
    value.insert("Fluid".into(), fluid.nbt());
    value.insert("In".into(), Tag::Byte(i8::from(inbound)));
    if progress < 1.0 {
        let mut interpolation = Compound::new();
        set_float(&mut interpolation, "Value", progress);
        value.insert("Progress".into(), Tag::Compound(interpolation));
    }
    port.insert("Flow".into(), Tag::Compound(value));
}

fn complete(entity: &ModBlockEntity, direction: Direction) -> Option<Fluid> {
    let (fluid, value) = flow(&port(entity, direction))?;
    (value >= 1.0).then_some(fluid)
}

fn set_pressure(
    entity: &mut ModBlockEntity,
    direction: Direction,
    inbound: bool,
    rpm: f32,
    now: i64,
) {
    let mut side = port(entity, direction);
    if rpm == 0.0 {
        side.remove(&"Pressure".into());
        side.remove(&"Flow".into());
    } else {
        let vector = if inbound { [rpm, 0.0] } else { [0.0, rpm] };
        side.insert(
            "Pressure".into(),
            Tag::List(
                vector
                    .into_iter()
                    .map(|value| Tag::Float(value.to_bits()))
                    .collect(),
            ),
        );
        if compound(&side, "Flow").is_some_and(|flow| int(flow, "In") != Some(i32::from(inbound))) {
            side.remove(&"Flow".into());
        }
    }
    write_port(entity, direction, side);
    entity.nbt.insert("FlowReady".into(), Tag::Long(now + 2));
}

fn endpoint(game: &Game<'_>, pos: [i32; 3], face: Direction) -> bool {
    if game.native_block(pos) == HOSE {
        return create_hose::pipe_face(game, pos) == Some(face);
    }
    let block = game.native_block(pos);
    if block == DRAIN {
        return face != Direction::Up;
    }
    matches!(block.as_str(), BASIN | TANK | CREATIVE | SPOUT | PORTABLE_INTERFACE) || !fluid_block(game, pos) && open_space(game, pos)
}

struct PipeNode {
    pos: [i32; 3],
    from: Direction,
    depth: usize,
    outgoing: Vec<Direction>,
}

fn pressure_side(
    game: &mut Game<'_>,
    pos: [i32; 3],
    pump: Option<&mut ModBlockEntity>,
    face: Direction,
    inbound: bool,
    rpm: f32,
) {
    let next = adjacent(pos, face);
    let mut nodes = Vec::new();
    let mut visited = BTreeSet::from([pos]);
    let mut frontier = VecDeque::from([(next, face.opposite(), 1)]);
    while let Some((pos, from, depth)) = frontier.pop_front() {
        if depth >= RANGE as usize
            || game.native_block(pos) == PUMP
            || !open_to(game, pos, from)
            || !visited.insert(pos)
        {
            continue;
        }
        let outgoing: Vec<_> = Direction::ALL
            .into_iter()
            .filter(|&side| side != from && open_to(game, pos, side))
            .filter(|&side| !visited.contains(&adjacent(pos, side)))
            .collect();
        for &side in &outgoing {
            frontier.push_back((adjacent(pos, side), side.opposite(), depth + 1));
        }
        nodes.push(PipeNode {
            pos,
            from,
            depth,
            outgoing,
        });
    }
    let mut connected = BTreeSet::new();
    let mut counts = [0; RANGE as usize];
    for node in nodes.iter_mut().rev() {
        node.outgoing.retain(|&side| {
            let next = adjacent(node.pos, side);
            endpoint(game, next, side.opposite())
                || connected.contains(&(next, side.opposite() as u8))
        });
        if !node.outgoing.is_empty() {
            connected.insert((node.pos, node.from as u8));
            counts[node.depth] += node.outgoing.len() + 1;
        }
    }

    let pressure = rpm.abs();
    let now = game.world.game_time;
    if let Some(pump) = pump {
        let reachable =
            endpoint(game, next, face.opposite()) || connected.contains(&(next, face.opposite() as u8));
        set_pressure(
            pump,
            face,
            inbound,
            if reachable { pressure } else { 0.0 },
            now,
        );
    }
    for node in nodes {
        let local = pressure / counts[node.depth].saturating_sub(1_usize).max(1) as f32;
        let mut wanted = [0.0; 6];
        if !node.outgoing.is_empty() {
            wanted[node.from as usize] = local;
        }
        for side in node.outgoing {
            wanted[side as usize] = local;
        }
        game.native_with_mod_block_entity(node.pos, |entity| {
            for side in Direction::ALL {
                if open_to_pipe_port(entity, side) || wanted[side as usize] > 0.0 {
                    set_pressure(
                        entity,
                        side,
                        if side == node.from { !inbound } else { inbound },
                        wanted[side as usize],
                        now,
                    );
                }
            }
        });
    }
}

fn open_to_pipe_port(entity: &ModBlockEntity, direction: Direction) -> bool {
    entity.nbt.contains_key(&name(direction).into())
}

pub(super) fn pump(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
    rpm: f32,
    changed: bool,
) {
    let state = game.world.block(pos[0], pos[1], pos[2]);
    let Some(face) = facing(game, state) else {
        return;
    };
    let direct_tanks = [face, face.opposite()].iter().all(|side| {
        matches!(
            game.native_block(adjacent(pos, *side)).as_str(),
            TANK | CREATIVE
        )
    });
    let enclosed = [face, face.opposite()].iter().all(|side| {
        let neighbor = adjacent(pos, *side);
        fluid_block(game, neighbor)
            || matches!(
                game.native_block(neighbor).as_str(),
                BASIN | TANK | CREATIVE | SPOUT | PORTABLE_INTERFACE | DRAIN
            )
    });
    if rpm == 0.0
        && (changed
            || [face, face.opposite()]
                .into_iter()
                .any(|side| pressure(&port(entity, side)).1 != 0.0))
    {
        // A loaded pump can already read zero while its saved ports retain pressure.
        entity.nbt.remove(&"PressureSpeed".into());
        pressure_side(game, pos, Some(entity), face, false, 0.0);
        pressure_side(game, pos, Some(entity), face.opposite(), true, 0.0);
    }

    // The pump's transport behavior writes its own pressure before the
    // legacy facing flip. The connected pipes see the new facing in this tick.
    if int(&entity.nbt, "Reversed") == Some(1) {
        if direct_tanks && rpm != 0.0 {
            pressure_side(game, pos, Some(entity), face, false, rpm);
            pressure_side(game, pos, Some(entity), face.opposite(), true, rpm);
        }
        entity.nbt.remove(&"Reversed".into());
        game.native_set_block_property_with(
            pos,
            "facing",
            name(face.opposite()),
            flags::UPDATE_ALL,
        );
        if enclosed && !direct_tanks && rpm != 0.0 {
            pressure_side(game, pos, None, face.opposite(), false, rpm);
            pressure_side(game, pos, None, face, true, rpm);
        }
        return;
    }
    let ready = float(&entity.nbt, "PressureSpeed");
    let direction = string(&entity.nbt, "PressureFacing");
    if changed {
        entity.nbt.remove(&"PressureSpeed".into());
        // The train interface's pump propagates pressure in the scheduled
        // block phase after its kinetic speed changes.
        if !enclosed
            || rpm == 0.0
            || [face, face.opposite()].into_iter().any(|side| {
                super::create_train_portable_items::fluid_train_at(&game.world, adjacent(pos, side))
                    .is_some()
            })
        {
            return;
        }
    }
    if rpm != 0.0 && (ready != Some(rpm.abs()) || direction.as_deref() != Some(name(face))) {
        pressure_side(game, pos, Some(entity), face, false, rpm);
        pressure_side(game, pos, Some(entity), face.opposite(), true, rpm);
        set_float(&mut entity.nbt, "PressureSpeed", rpm.abs());
        entity
            .nbt
            .insert("PressureFacing".into(), Tag::String(name(face).into()));
    }
    tick(game, pos, entity);
}

fn source(game: &Game<'_>, next: [i32; 3], face: Direction, port: &Compound) -> Option<Fluid> {
    if let Some(reserve) = buffer(port) {
        return Some(reserve);
    }
    match game.native_block(next).as_str() {
        VALVE if !create_valve::enabled(game, next) => None,
        PUMP | PIPE | ENCASED_PIPE | GLASS_PIPE | VALVE | SMART_PIPE => {
            complete(mod_entity(game, next)?, face.opposite())
        }
        HOSE if create_hose::pipe_face(game, next) == Some(face.opposite()) => {
            create_hose::supply(game, next)
        }
        BASIN => basin_source(mod_entity(game, next)?, |_| true).map(|(_, _, fluid)| fluid),
        PORTABLE_INTERFACE => {
            create_portable_interface::tanks(game, next).find_map(|(_, _, fluid)| fluid)
        }
        SPOUT if face != Direction::Up => create_spout::contents(mod_entity(game, next)?),
        DRAIN if face != Direction::Down => create_item_drain::contents(mod_entity(game, next)?),
        TANK | CREATIVE => {
            let (root, _, fluid) = create_fluid_tank::storage(game, next)?;
            if super::create_steam::accepts_water(game, root) {
                None
            } else {
                fluid
            }
        }
        WATER | "minecraft:lava"
            if game.native_block_property(next, "level").as_deref() == Some("0") =>
        {
            Some(Fluid {
                id: game.native_block(next),
                amount: BUCKET,
                components: None,
            })
        }
        _ => None,
    }
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Reservoir {
    Basin([i32; 3], bool, usize),
    Spout([i32; 3]),
    Drain([i32; 3]),
    Tank([i32; 3]),
    MountedTank([i32; 3], usize),
    Hose([i32; 3]),
    Creative([i32; 3]),
    Boiler([i32; 3]),
    Open {
        pipe: [i32; 3],
        face: Direction,
        space: [i32; 3],
    },
}

struct Output {
    reservoir: Reservoir,
    reached: i64,
    fluid: Fluid,
    available: i32,
}

fn output(
    game: &Game<'_>,
    pipe: [i32; 3],
    face: Direction,
    at: [i32; 3],
    port: &Compound,
    wanted: &Fluid,
) -> Option<Output> {
    let (reservoir, capacity, stored) = match game.native_block(at).as_str() {
        BASIN => {
            let tanks = basin_tanks(mod_entity(game, at)?, false);
            let index = basin_destination(&tanks, wanted)?;
            (
                Reservoir::Basin(at, false, index),
                BUCKET,
                tanks[index].clone(),
            )
        }
        HOSE if create_hose::pipe_face(game, at) == Some(face.opposite())
            && matches!(wanted.id.as_str(), WATER | "minecraft:lava") =>
        {
            (
                Reservoir::Hose(at),
                create_hose::CAPACITY,
                create_hose::contents(mod_entity(game, at)?),
            )
        }
        SPOUT if face != Direction::Up => (
            Reservoir::Spout(at),
            BUCKET,
            create_spout::contents(mod_entity(game, at)?),
        ),
        TANK | CREATIVE => {
            let (root, capacity, stored) = create_fluid_tank::storage(game, at)?;
            if super::create_steam::accepts_water(game, root) {
                if wanted.id != WATER {
                    return None;
                }
                (Reservoir::Boiler(root), i32::MAX, None)
            } else if game.native_block(root) == CREATIVE {
                (Reservoir::Creative(root), i32::MAX, None)
            } else {
                (Reservoir::Tank(root), capacity, stored)
            }
        }
        PORTABLE_INTERFACE => {
            let (index, capacity, stored) =
                create_portable_interface::tanks(game, at).find(|(_, capacity, fluid)| {
                    fluid
                        .as_ref()
                        .is_none_or(|fluid| fluid.same_variant(wanted) && fluid.amount < *capacity)
                })?;
            (Reservoir::MountedTank(at, index), capacity, stored)
        }
        block if open_space(game, at) && !matches!(block, WATER | "minecraft:lava") => (
            Reservoir::Open {
                pipe,
                face,
                space: at,
            },
            BUCKET,
            buffer(port),
        ),
        _ => return None,
    };
    let fluid = stored.unwrap_or_else(|| Fluid {
        amount: 0,
        ..wanted.clone()
    });
    if !fluid.same_variant(wanted) {
        return None;
    }
    let available = if matches!(reservoir, Reservoir::Open { .. })
        && ((fluid.amount == 0 && matches!(wanted.id.as_str(), WATER | "minecraft:lava"))
            || matches!(wanted.id.as_str(), "minecraft:milk" | "create:potion"))
    {
        1
    } else {
        capacity - fluid.amount
    };
    let reached = match port.get(&"FlowReached".into()) {
        Some(Tag::Long(tick)) => *tick,
        _ => 0,
    };
    Some(Output {
        reservoir,
        reached,
        fluid,
        available: available.max(0),
    })
}

fn apply_outlet_effect(game: &mut Game<'_>, space: [i32; 3], face: Direction, fluid: &Fluid) {
    let [x, y, z] = space.map(f64::from);
    let area = Aabb::new(
        Vec3::new(x, y - if face == Direction::Down { 2.0 } else { 1.0 }, z),
        Vec3::new(x + 1.0, y + 1.0, z + 1.0),
    );
    let phase = game.world.game_time % 5;
    let potion_effects = if fluid.id == "create:potion" {
        create_spout::bottle(fluid)
            .map(|(_, stack)| horizon_client::brewing::contents_effects(&stack))
            .unwrap_or_default()
    } else {
        Vec::new()
    };
    let tags = &game.res.stations().enchantments.entity_tags;
    for mob in game
        .mobs
        .iter_mut()
        .filter(|mob| !mob.removed && mob.alive() && area.intersects(mob.bounds()))
    {
        match fluid.id.as_str() {
            WATER if phase == 0 => mob.extinguish_fire(),
            "minecraft:lava"
                if phase == 0 && !horizon_client::mobs::spawn_rules::fire_immune(mob.species()) =>
            {
                mob.ignite_for_ticks(60)
            }
            "minecraft:milk" if phase == 0 => {
                mob.extra.effects.clear();
                mob.needs_sync = true;
            }
            "create:potion" => {
                for &(effect, duration, amplifier) in &potion_effects {
                    if super::potions::mob_can_be_affected(tags, &mob.kind.id, effect)
                        && let Some(effect) = super::potions::mob_effect_id(effect)
                    {
                        mob.add_effect(effect, duration, amplifier);
                    }
                }
            }
            _ => {}
        }
    }
}

fn find_outputs(
    game: &Game<'_>,
    pos: [i32; 3],
    entity: &ModBlockEntity,
    fluid: &Fluid,
) -> Vec<Output> {
    let mut outputs: Vec<Output> = Vec::new();
    let mut visited = BTreeSet::from([pos]);
    let mut frontier = VecDeque::from([(pos, entity)]);
    while let Some((pos, entity)) = frontier.pop_front() {
        for face in Direction::ALL {
            let port = port(entity, face);
            let (inbound, rpm) = pressure(&port);
            if rpm == 0.0
                || inbound
                || !flow(&port).is_some_and(|(flow, t)| t >= 1.0 && flow.same_variant(fluid))
            {
                continue;
            }
            let target = adjacent(pos, face);
            if game.native_block(target) == VALVE && !create_valve::enabled(game, target) {
                continue;
            }
            if fluid_block(game, target) {
                if let Some(next) = mod_entity(game, target)
                    && complete(next, face.opposite())
                        .is_some_and(|found| found.same_variant(fluid))
                    && visited.insert(target)
                {
                    frontier.push_back((target, next));
                }
            } else if let Some(target) = output(game, pos, face, target, &port, fluid)
                && outputs.iter().all(|out| out.reservoir != target.reservoir)
            {
                outputs.push(target);
            }
        }
    }
    outputs.sort_by_key(|out| out.reached);
    outputs
}

fn allocate(targets: &[Output], mut remaining: i32, simulate: bool) -> Vec<i32> {
    let mut offered = vec![0; targets.len()];
    let mut active: Vec<_> = (0..targets.len()).collect();
    while !active.is_empty() && remaining > 0 {
        let count = active.len() as i32;
        let share = remaining / count;
        let remainder = remaining % count;
        let mut unfilled = Vec::with_capacity(active.len());
        for (order, index) in active.into_iter().enumerate() {
            if remaining == 0 {
                break;
            }
            let request = share + i32::from((order as i32) < remainder);
            let mut compared = request;
            if simulate {
                // In Java the simulated handler receives the cumulative offer.
                // The network compares its incremental acceptance to that offer.
                compared += offered[index];
            }
            let accepted = request.min(targets[index].available - offered[index]);
            offered[index] += accepted;
            remaining -= accepted;
            if accepted == compared {
                unfilled.push(index);
            }
        }
        active = unfilled;
    }
    offered
}

fn fluid_tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity, intake: Direction) {
    if create_encased_fluid_pipe::transfer_restarting(entity, game.world.game_time) {
        return;
    }
    let intake_pos = adjacent(pos, intake);
    if fluid_block(game, intake_pos) {
        return;
    }
    let Some(wanted) = complete(entity, intake) else {
        return;
    };
    let mut inlet = port(entity, intake);
    let basin = mod_entity(game, intake_pos)
        .filter(|entity| entity.id == BASIN)
        .and_then(|entity| basin_source(entity, |fluid| fluid.same_variant(&wanted)));
    let supplied = if game.native_block(intake_pos) == BASIN {
        basin.as_ref().map(|(_, _, fluid)| fluid.clone())
    } else {
        source(game, intake_pos, intake, &inlet)
    };
    let Some(mut from) = supplied else {
        return;
    };
    let (_, rpm) = pressure(&inlet);
    let now = game.world.game_time;
    let mut targets = find_outputs(game, pos, entity, &from);
    // Boiler fills start on the tick after the outlet reaches the tank.
    targets
        .retain(|target| !matches!(target.reservoir, Reservoir::Boiler(_)) || target.reached < now);
    if targets.is_empty() {
        return;
    }
    let intake_storage = match game.native_block(intake_pos).as_str() {
        BASIN => {
            let Some((output, slot, _)) = basin else {
                return;
            };
            Reservoir::Basin(intake_pos, output, slot)
        }
        SPOUT => Reservoir::Spout(intake_pos),
        DRAIN => Reservoir::Drain(intake_pos),
        PORTABLE_INTERFACE => {
            let Some((index, _, _)) =
                create_portable_interface::tanks(game, intake_pos).find(|(_, _, fluid)| {
                    fluid
                        .as_ref()
                        .is_some_and(|fluid| fluid.same_variant(&from))
                })
            else {
                return;
            };
            Reservoir::MountedTank(intake_pos, index)
        }
        HOSE => Reservoir::Hose(intake_pos),
        TANK | CREATIVE => {
            let Some((root, _, _)) = create_fluid_tank::storage(game, intake_pos) else {
                return;
            };
            if game.native_block(root) == CREATIVE {
                Reservoir::Creative(root)
            } else {
                Reservoir::Tank(root)
            }
        }
        _ => Reservoir::Open {
            pipe: pos,
            face: intake,
            space: intake_pos,
        },
    };
    targets.retain(|output| output.reservoir != intake_storage);
    // An open end fed by a tank starts draining after its connection reaches the outlet.
    if matches!(intake_storage, Reservoir::Tank(_) | Reservoir::Creative(_)) {
        targets.retain(|target| {
            !matches!(target.reservoir, Reservoir::Open { .. }) || target.reached < now
        });
    }
    let intake_open = matches!(intake_storage, Reservoir::Open { .. });

    if intake_open {
        let mut endpoint = compound(&inlet, "OpenEnd")
            .or_else(|| compound(&inlet, "RefreshingEnd"))
            .cloned()
            .unwrap_or_default();
        let open = game.native_block(intake_pos);
        let prior = string(&endpoint, "ObservedBlock");
        let wait = match endpoint.get(&"Resume".into()) {
            Some(Tag::Long(resume)) => *resume - now,
            _ => 0,
        };
        let blocked = wait > 0;
        endpoint.insert("ObservedBlock".into(), Tag::String(open.as_str().into()));
        if prior.is_some_and(|prior| prior != open) && buffer(&inlet).is_some() {
            endpoint.insert("Resume".into(), Tag::Long(now + 5));
        }
        // The scheduled neighbour update replaces the open flow source for
        // one tick. The buffer remains with the same pipe port.
        let (active, inactive) = if wait == 4 {
            ("RefreshingEnd", "OpenEnd")
        } else {
            ("OpenEnd", "RefreshingEnd")
        };
        inlet.remove(&inactive.into());
        inlet.insert(active.into(), Tag::Compound(endpoint));
        if blocked {
            write_port(entity, intake, inlet);
            return;
        }
    }

    let available = ((rpm / 2.0).max(1.0) as i32).min(from.amount);
    let simulated: i32 = allocate(&targets, available, true).into_iter().sum();
    let mut offered = allocate(&targets, simulated, false);
    let mut moved = offered.iter().sum::<i32>();
    if moved > 0
        && let Reservoir::Hose(at) = intake_storage
    {
        if !create_hose::drain_ready(game, at) {
            return;
        }
        let drained = create_hose::drain(game, at, &from, moved);
        if drained < moved {
            offered = allocate(&targets, drained, false);
            moved = offered.iter().sum();
        }
    }
    if moved == 0 {
        return;
    }
    if intake_open
        && buffer(&inlet).is_none()
        && let Some(state) = game.native_default_state(&from.id)
        && let Some(flowing) =
            game.with_level(|_, level, _| level.native_state_with_property(state, "level", "14"))
    {
        game.native_set_block(
            game.native_dimension(),
            intake_pos,
            flowing,
            flags::UPDATE_ALL,
        );
    }
    from.amount -= moved;
    match intake_storage {
        Reservoir::Basin(at, out, slot) => write_basin(game, at, out, slot, from),
        Reservoir::Spout(at) => create_spout::write(game, at, from),
        Reservoir::Drain(at) => create_item_drain::write(game, at, from),
        Reservoir::Tank(root) | Reservoir::Creative(root) => {
            if let Some((_, _, mut stored)) = create_fluid_tank::storage(game, root) {
                let creative = game.native_block(root) == CREATIVE;
                super::create_tank_storage::drain(&mut stored, creative, moved, Some(&from), true);
                if !creative {
                    let remaining = stored.unwrap_or(from);
                    create_fluid_tank::write(game, root, remaining);
                }
            }
        }
        Reservoir::MountedTank(at, index) => {
            create_portable_interface::write_tank(game, at, index, from)
        }
        Reservoir::Boiler(_) | Reservoir::Hose(_) => {}
        Reservoir::Open { .. } => {
            write_buffer(&mut inlet, from, true);
            write_port(entity, intake, inlet);
        }
    }
    for (mut target, amount) in targets.into_iter().zip(offered) {
        if amount == 0 {
            continue;
        }
        target.fluid.amount += amount;
        match target.reservoir {
            Reservoir::Basin(at, out, slot) => write_basin(game, at, out, slot, target.fluid),
            Reservoir::Spout(at) => create_spout::write(game, at, target.fluid),
            Reservoir::Tank(root) | Reservoir::Creative(root) => {
                if let Some((_, capacity, mut stored)) = create_fluid_tank::storage(game, root) {
                    let creative = game.native_block(root) == CREATIVE;
                    let mut incoming = target.fluid;
                    incoming.amount = amount;
                    super::create_tank_storage::fill(&mut stored, capacity, creative, &incoming, true);
                    if !creative && let Some(fluid) = stored {
                        create_fluid_tank::write(game, root, fluid);
                    }
                }
            }
            Reservoir::MountedTank(at, index) => {
                create_portable_interface::write_tank(game, at, index, target.fluid)
            }
            Reservoir::Hose(at) => create_hose::fill(game, at, target.fluid),
            Reservoir::Boiler(root) => { super::create_steam::boiler_fill(game, root, &target.fluid.id, amount, true); }
            Reservoir::Drain(_) => {}
            Reservoir::Open { pipe, face, space } => {
                apply_outlet_effect(game, space, face, &target.fluid);
                if matches!(target.fluid.id.as_str(), "minecraft:milk" | "create:potion") {
                    target.fluid.amount = 0;
                }
                if target.fluid.amount >= BUCKET
                    && let Some(state) = game.native_default_state(&target.fluid.id)
                {
                    game.native_set_block(game.native_dimension(), space, state, flags::UPDATE_ALL);
                    target.fluid.amount = 0;
                }
                let write = |entity: &mut ModBlockEntity| {
                    let mut outlet = port(entity, face);
                    write_buffer(&mut outlet, target.fluid, false);
                    write_port(entity, face, outlet);
                };
                if pipe == pos {
                    write(entity);
                } else {
                    game.native_with_mod_block_entity(pipe, write);
                }
            }
        }
    }
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    if matches!(entity.nbt.get(&"FlowReady".into()), Some(Tag::Long(ready)) if *ready > game.world.game_time)
    {
        return;
    }

    let mut ports = Direction::ALL.map(|face| (face, port(entity, face)));
    let internal = ports.iter().find_map(|(_, port)| {
        let (inward, rpm) = pressure(port);
        (inward && rpm > 0.0)
            .then(|| flow(port))
            .flatten()
            .filter(|(_, t)| *t >= 1.0)
            .map(|(fluid, _)| fluid)
    });
    let now = game.world.game_time;
    let mut sources = Vec::new();
    for (face, port) in &mut ports {
        let (inward, rpm) = pressure(port);
        if rpm == 0.0 {
            continue;
        }
        let fluid = if inward {
            sources.push(*face);
            let adjacent = adjacent(pos, *face);
            if game.native_block(adjacent) == BASIN && entity.id == SMART_PIPE {
                mod_entity(game, adjacent).and_then(|basin| {
                    basin_source(basin, |fluid| filter_fluid(entity, fluid))
                        .map(|(_, _, fluid)| fluid)
                })
            } else {
                source(game, adjacent, *face, port)
            }
        } else {
            internal.clone()
        };
        let fluid = fluid.filter(|fluid| filter_fluid(entity, fluid));
        set_flow(port, fluid, inward, rpm, now);
    }
    for (face, port) in ports {
        if !port.is_empty() {
            write_port(entity, face, port);
        }
    }
    for source in sources {
        fluid_tick(game, pos, entity, source);
    }
}
