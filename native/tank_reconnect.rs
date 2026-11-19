use std::collections::{BTreeMap, BTreeSet, VecDeque};

use horizon_world::nbt::{Compound, Tag};
use crate::containers::{BlockEntity, ModBlockEntity};
use super::Game;
use super::create_depot::compound;
use super::create_fluids::{Fluid, read_fluid};

use super::create_tank_connectivity::{self, Part, Pos};

const PENDING: &str = "CreateTankPendingSplit";
const MOVED_AT: &str = "CreateTankMovedAt";

fn moved_this_tick(game: &Game<'_>, entity: &ModBlockEntity) -> bool {
    matches!(entity.runtime.get(&MOVED_AT.into()), Some(Tag::Long(tick)) if *tick == game.world.game_time)
}

impl create_tank_connectivity::Fluid for Fluid {
    fn amount(&self) -> i32 { self.amount }
    fn set_amount(&mut self, amount: i32) { self.amount = amount; }
    fn same_variant(&self, other: &Self) -> bool { Fluid::same_variant(self, other) }
}

type TankPart = Part<Fluid>;

// Existing connected tanks participate with their current controller and
// contents. They are not themselves queued for connectivity work.
fn collect_neighbors(game: &Game<'_>, parts: &mut BTreeMap<Pos, TankPart>, kind: &str) {
    let mut frontier: VecDeque<_> = parts.keys().copied().collect();
    while let Some(pos) = frontier.pop_front() {
        for direction in super::create_machines::DIRECTIONS {
            let next = super::create_machines::offset(pos, direction);
            if parts.contains_key(&next) || game.native_block(next) != kind {
                continue;
            }
            let Some((width, group)) = super::create_fluid_tank::parts(game, next) else { continue };
            let Some(&controller) = group.first() else { continue };
            let entity = super::create_machines::mod_entity(game, next);
            if entity.is_some_and(|entity| moved_this_tick(game, entity)) { continue; }
            let fluid = entity.and_then(|entity|
                compound(&entity.nbt, "TankContent").and_then(|tank| read_fluid(compound(tank, "Fluid")?)));
            let dirty = entity.is_some_and(|entity| entity.nbt.contains_key(&PENDING.into()));
            let height = group.len() / (width * width);
            parts.insert(next, Part { controller, width: width as i32, height: height as i32,
                fluid, dirty, touched: false });
            frontier.push_back(next);
        }
    }
}

pub(super) fn finish(game: &mut Game<'_>) {
    finish_kind(game, super::create_fluid_tank::TANK, false);
    finish_kind(game, super::create_fluid_tank::CREATIVE, false);
}

// A moved Java tank reconnects at the start of its next own tick, before
// its boiler ticks. Other split work keeps the existing block-entity phase.
pub(super) fn finish_moved(game: &mut Game<'_>) {
    finish_kind(game, super::create_fluid_tank::TANK, true);
    finish_kind(game, super::create_fluid_tank::CREATIVE, true);
}

fn finish_kind(game: &mut Game<'_>, kind: &str, moved_only: bool) {
    let mut parts = BTreeMap::new();
    for (&(x, y, z), entity) in game.world.block_entities.iter() {
        let BlockEntity::Mod(entity) = entity else { continue };
        if entity.id != kind || !entity.nbt.contains_key(&PENDING.into()) { continue; }
        if moved_this_tick(game, entity) || (moved_only && !entity.runtime.contains_key(&MOVED_AT.into())) { continue; }
        let pos = [x, y, z];
        let fluid = compound(&entity.nbt, "TankContent").and_then(|tank| read_fluid(compound(tank, "Fluid")?));
        parts.insert(pos, Part { controller: pos, width: 1, height: 1, fluid, dirty: true, touched: true });
    }
    if parts.is_empty() { return; }

    collect_neighbors(game, &mut parts, kind);
    let ticking = game.block_ticking_area();
    let tickers = game.world.block_entity_tickers();
    let mut active = BTreeSet::new();
    for slot in tickers.iter().copied() {
        let (x, y, z) = slot.0;
        let pos = [x, y, z];
        if !parts.get(&pos).is_some_and(|part| part.dirty) || !ticking(x, z) || !game.world.block_entities.is_live(slot)
            || game.world.block_entities.is_asleep(&(x, y, z))
            || !game.border.contains(f64::from(x), f64::from(z))
        {
            continue;
        }
        let mut frontier = VecDeque::from([pos]);
        while let Some(current) = frontier.pop_front() {
            if !active.insert(current) { continue; }
            for direction in super::create_machines::DIRECTIONS {
                let next = super::create_machines::offset(current, direction);
                if parts.contains_key(&next) && !active.contains(&next) { frontier.push_back(next); }
            }
        }
        create_tank_connectivity::reconnect(&mut parts, pos, kind == super::create_fluid_tank::CREATIVE);
    }
    commit(game, parts, &active);
}

fn commit(game: &mut Game<'_>, parts: BTreeMap<Pos, TankPart>, active: &BTreeSet<Pos>) {
    let mut roots = BTreeSet::new();
    for (pos, part) in parts {
        if !active.contains(&pos) || !part.touched { continue; }
        roots.insert(part.controller);
        let key = (pos[0], pos[1], pos[2]);
        if let Some(BlockEntity::Mod(entity)) = game.world.block_entities.get_mut(&key) {
            if part.controller == pos && part.dirty {
                entity.nbt.insert(PENDING.into(), Tag::Byte(1));
            } else {
                entity.nbt.remove(&PENDING.into());
            }
            entity.runtime.remove(&MOVED_AT.into());
            entity.nbt.remove(&"Controller".into());
            entity.nbt.insert("CreateTankController".into(), Tag::IntArray(part.controller.to_vec()));
            let mut tank = Compound::new();
            if part.controller == pos {
                let old_width = super::create_machines::int(&entity.nbt, "Size").unwrap_or(1);
                let old_height = super::create_machines::int(&entity.nbt, "Height").unwrap_or(1);
                if old_width != part.width || old_height != part.height {
                    entity.runtime.remove(&"CreateTankCapacity".into());
                }
                if let Some(fluid) = part.fluid { tank.insert("Fluid".into(), fluid.nbt()); }
                entity.nbt.insert("Size".into(), Tag::Int(part.width));
                entity.nbt.insert("Height".into(), Tag::Int(part.height));
            } else {
                entity.runtime.remove(&"CreateTankCapacity".into());
                entity.nbt.remove(&"Size".into());
                entity.nbt.remove(&"Height".into());
            }
            entity.nbt.insert("TankContent".into(), Tag::Compound(tank));
        }
    }
    for root in roots {
        let Some((width, group)) = super::create_fluid_tank::parts(game, root) else { continue };
        let Some(entity) = super::create_machines::mod_entity(game, root) else { continue };
        let enabled = super::create_tank_windows::window_enabled(entity);
        let entity = entity.clone();
        super::create_tank_windows::sync(game, root, width, &group, enabled);
        super::create_tank_lighting::sync(game, root, width, &group, &entity);
    }
}

// A copied member can still name the source controller. On its first tick,
// Java drops that identity and schedules connectivity for the next tick.
pub(super) fn tick_identity(game: &mut Game<'_>, pos: Pos, entity: &mut ModBlockEntity) -> bool {
    let native_owner = match entity.nbt.get(&"CreateTankController".into()) {
        Some(Tag::IntArray(owner)) => <Pos>::try_from(owner.as_slice()).ok(),
        _ => None,
    };
    let java_owner = compound(&entity.nbt, "Controller").and_then(|owner| Some([
        super::create_machines::int(owner, "X")?,
        super::create_machines::int(owner, "Y")?,
        super::create_machines::int(owner, "Z")?,
    ]));
    let owner = native_owner.or(java_owner);
    let previous = match entity.nbt.get(&"LastKnownPos".into()) {
        Some(Tag::IntArray(previous)) => <Pos>::try_from(previous.as_slice()).ok(),
        Some(Tag::Compound(previous)) => Some([
            super::create_machines::int(previous, "X").unwrap_or(pos[0]),
            super::create_machines::int(previous, "Y").unwrap_or(pos[1]),
            super::create_machines::int(previous, "Z").unwrap_or(pos[2]),
        ]),
        _ => None,
    };
    let moved_root = previous.is_some_and(|previous| previous != pos)
        && (owner.is_none() || owner == previous || owner == Some(pos));
    if moved_root {
        // Java removes the controller but keeps the inventory's existing
        // capacity until an actual resize, even for a now-singleton root.
        let width = super::create_machines::int(&entity.nbt, "Size").unwrap_or(1);
        let height = super::create_machines::int(&entity.nbt, "Height").unwrap_or(1);
        let moved_at = game.world.game_time;
        game.native_with_mod_block_entity(pos, |live| {
            live.runtime.insert(MOVED_AT.into(), Tag::Long(moved_at));
            live.runtime.insert("CreateTankCapacity".into(), Tag::Int(8000 * width * width * height));
        });
        entity.nbt.remove(&"Controller".into());
        entity.nbt.insert("CreateTankController".into(), Tag::IntArray(pos.to_vec()));
        entity.nbt.insert("LastKnownPos".into(), Tag::IntArray(pos.to_vec()));
        entity.nbt.insert("Size".into(), Tag::Int(1));
        entity.nbt.insert("Height".into(), Tag::Int(1));
        entity.nbt.insert(PENDING.into(), Tag::Byte(1));
        entity.nbt.remove(&"Boiler".into());
        for key in ["BoilerIntake", "BoilerWindow", "BoilerSample", "BoilerIndex"] {
            entity.nbt.remove(&key.into());
        }
        return true;
    }
    let stale_member = owner.filter(|&root| root != pos).is_some_and(|root| {
        if previous.is_some_and(|previous| previous != pos) { return true; }
        let Some(controller) = super::create_machines::mod_entity(game, root) else { return false };
        let width = super::create_machines::int(&controller.nbt, "Size").unwrap_or(1);
        let height = super::create_machines::int(&controller.nbt, "Height").unwrap_or(1);
        pos[0] < root[0] || pos[0] >= root[0] + width || pos[1] < root[1]
            || pos[1] >= root[1] + height || pos[2] < root[2] || pos[2] >= root[2] + width
    });
    if owner.is_some_and(|root| root != pos) {
        entity.nbt.insert("LastKnownPos".into(), Tag::IntArray(pos.to_vec()));
    }
    if !stale_member { return false; }
    let moved_at = game.world.game_time;
    game.native_with_mod_block_entity(pos, |live| {
        live.runtime.insert(MOVED_AT.into(), Tag::Long(moved_at));
    });
    entity.nbt.remove(&"Controller".into());
    entity.nbt.insert("CreateTankController".into(), Tag::IntArray(pos.to_vec()));
    entity.nbt.insert("Size".into(), Tag::Int(1));
    entity.nbt.insert("Height".into(), Tag::Int(1));
    entity.nbt.insert(PENDING.into(), Tag::Byte(1));
    true
}

// A newly placed tank begins as a singleton; Java invokes connectivity from
// that position and discovers existing controllers through negative neighbors.
pub(super) fn place(game: &mut Game<'_>, pos: Pos) {
    let kind = game.native_block(pos);
    let Some(entity) = super::create_machines::mod_entity(game, pos) else { return };
    if entity.nbt.contains_key(&"CreateTankController".into()) { return; }
    let fluid = compound(&entity.nbt, "TankContent")
        .and_then(|tank| read_fluid(compound(tank, "Fluid")?));
    // Exclude the just-placed seed while legacy neighbors reconstruct their
    // pre-placement group; the queue commits its final identity below.
    game.native_with_mod_block_entity(pos, |entity| {
        entity.nbt.insert(PENDING.into(), Tag::Byte(1));
    });
    let mut parts = BTreeMap::from([(pos, Part {
        controller: pos, width: 1, height: 1, fluid, dirty: true, touched: true,
    })]);
    collect_neighbors(game, &mut parts, &kind);
    create_tank_connectivity::reconnect(&mut parts, pos, kind == super::create_fluid_tank::CREATIVE);
    let active = parts.keys().copied().collect();
    commit(game, parts, &active);
}
