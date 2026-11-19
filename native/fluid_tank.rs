use std::collections::{BTreeMap, BTreeSet, VecDeque};

use horizon_world::nbt::{Compound, Tag};

use crate::containers::ModBlockEntity;
use crate::items::ItemStack;

use super::Game;
use super::create_depot::compound;
use super::create_fluids::{Fluid, read_fluid};
use super::create_machines::mod_entity;

pub(super) const TANK: &str = "create:fluid_tank";
pub(super) const CREATIVE: &str = "create:creative_fluid_tank";
const PER_PART: i32 = 8000;

pub(super) fn parts(game: &Game<'_>, pos: [i32; 3]) -> Option<(usize, Vec<[i32; 3]>)> {
    let tank = game.native_block(pos);
    if !matches!(tank.as_str(), TANK | CREATIVE) {
        return None;
    }
    let pending = |at| mod_entity(game, at).is_some_and(|entity|
        entity.nbt.contains_key(&"CreateTankPendingSplit".into()));
    if pending(pos) {
        return Some((1, vec![pos]));
    }
    // New native groups retain their controller identity. Legacy/imported
    // block entities without this field use the existing reconstruction path.
    if let Some(Tag::IntArray(owner)) = mod_entity(game, pos)
        .and_then(|entity| entity.nbt.get(&"CreateTankController".into()))
    {
        if let Ok(saved_root) = <[i32; 3]>::try_from(owner.as_slice()) {
            // A native root stores its own position; Java represents the same
            // identity by omitting Controller, including after a copy.
            let root = if mod_entity(game, pos).is_some_and(|entity| matches!(
                entity.nbt.get(&"LastKnownPos".into()),
                Some(Tag::IntArray(previous)) if previous.as_slice() == saved_root
            )) { pos } else { saved_root };
            if let Some(controller) = mod_entity(game, root) {
                let width = super::create_machines::int(&controller.nbt, "Size").unwrap_or(1);
                let height = super::create_machines::int(&controller.nbt, "Height").unwrap_or(1);
                if width > 0 && height > 0 {
                    let mut group = Vec::new();
                    for y in 0..height {
                        for x in 0..width {
                            for z in 0..width {
                                group.push([root[0] + x, root[1] + y, root[2] + z]);
                            }
                        }
                    }
                    if root == pos || group.iter().all(|&at| {
                        game.native_block(at) == tank && !pending(at)
                            && mod_entity(game, at).is_some_and(|entity| {
                                matches!(entity.nbt.get(&"CreateTankController".into()),
                                    Some(Tag::IntArray(owner)) if owner.as_slice() == root)
                            })
                    }) {
                        return Some((width as usize, group));
                    }
                }
            }
        }
    }
    // Java saves a controller's dimensions on the root and a compound
    // Controller position on each member. Preserve those identities when
    // importing a world instead of joining adjacent saved groups by shape.
    let java_owner = |at| {
        let entity = mod_entity(game, at)?;
        let owner = compound(&entity.nbt, "Controller")?;
        Some([
            super::create_machines::int(owner, "X")?,
            super::create_machines::int(owner, "Y")?,
            super::create_machines::int(owner, "Z")?,
        ])
    };
    let root = java_owner(pos).unwrap_or(pos);
    if let Some(controller) = mod_entity(game, root) {
        let width = super::create_machines::int(&controller.nbt, "Size").unwrap_or(0);
        let height = super::create_machines::int(&controller.nbt, "Height").unwrap_or(0);
        if width > 0 && height > 0 && java_owner(root).is_none() {
            let mut group = Vec::new();
            for y in 0..height {
                for x in 0..width {
                    for z in 0..width {
                        group.push([root[0] + x, root[1] + y, root[2] + z]);
                    }
                }
            }
            let java_singleton = matches!(controller.nbt.get(&"LastKnownPos".into()), Some(Tag::Compound(_)));
            if (group.len() > 1 || java_singleton) && group.contains(&pos)
                && group.iter().all(|&at| game.native_block(at) == tank && !pending(at)
                    && (at == root || java_owner(at) == Some(root)))
            {
                return Some((width as usize, group));
            }
        }
    }
    // In a vertically stacked tank, incompatible filled layers remain
    // separate. Empty layers between them join the upper group.
    let mut connected = BTreeSet::from([pos]);
    let mut frontier = VecDeque::from([pos]);
    while let Some(part) = frontier.pop_front() {
        for direction in super::create_machines::DIRECTIONS {
            let next = super::create_machines::offset(part, direction);
            if game.native_block(next) == tank && !pending(next) && connected.insert(next) {
                frontier.push_back(next);
            }
        }
    }
    let mut layers = BTreeMap::<i32, Fluid>::new();
    let mut conflicting_layer = false;
    for &part in &connected {
        let fluid = mod_entity(game, part).and_then(|entity| {
            compound(&entity.nbt, "TankContent")
                .and_then(|content| read_fluid(compound(content, "Fluid")?))
        });
        if let Some(fluid) = fluid {
            if let Some(existing) = layers.get(&part[1]) {
                conflicting_layer |= !existing.same_variant(&fluid);
            } else {
                layers.insert(part[1], fluid);
            }
        }
    }
    let mut min_y = i32::MIN;
    let mut max_y = i32::MAX;
    if !conflicting_layer {
        let mut previous: Option<(i32, &Fluid)> = None;
        for (&y, fluid) in &layers {
            if let Some((previous_y, previous_fluid)) = previous {
                if !previous_fluid.same_variant(fluid) {
                    let boundary = previous_y + 1;
                    if pos[1] < boundary {
                        max_y = max_y.min(boundary - 1);
                    } else {
                        min_y = min_y.max(boundary);
                    }
                }
            }
            previous = Some((y, fluid));
        }
    }
    let axis_at = |at| {
        (game.native_block(at) == tank && !pending(at) && (min_y..=max_y).contains(&at[1]))
            .then_some('y')
    };
    if conflicting_layer {
        super::create_multiblock::parts_matching(pos, axis_at, |_| 32, |candidate| {
            let anchor = candidate.first().and_then(|&part| mod_entity(game, part)).and_then(|entity| {
                compound(&entity.nbt, "TankContent")
                    .and_then(|content| read_fluid(compound(content, "Fluid")?))
            });
            for &part in candidate {
                let fluid = mod_entity(game, part).and_then(|entity| {
                    compound(&entity.nbt, "TankContent")
                        .and_then(|content| read_fluid(compound(content, "Fluid")?))
                });
                if anchor.as_ref().zip(fluid.as_ref()).is_some_and(|(a, b)| !a.same_variant(b)) {
                    return false;
                }
            }
            true
        })
    } else {
        super::create_multiblock::parts(pos, axis_at, |_| 32)
    }
}

pub(super) fn stored_controller(entity: &ModBlockEntity, pos: [i32; 3]) -> Option<[i32; 3]> {
    if let Some(Tag::IntArray(owner)) = entity.nbt.get(&"CreateTankController".into()) {
        if let Ok(root) = <[i32; 3]>::try_from(owner.as_slice()) {
            return Some(if matches!(entity.nbt.get(&"LastKnownPos".into()),
                Some(Tag::IntArray(previous)) if previous.as_slice() == root) { pos } else { root });
        }
    }
    compound(&entity.nbt, "Controller").and_then(|owner| Some([
        super::create_machines::int(owner, "X")?,
        super::create_machines::int(owner, "Y")?,
        super::create_machines::int(owner, "Z")?,
    ]))
}

pub(super) fn retained_capacity(entity: &ModBlockEntity, fallback: i32) -> i32 {
    match entity.runtime.get(&"CreateTankCapacity".into()) {
        Some(Tag::Int(capacity)) => *capacity,
        _ => fallback,
    }
}

pub(super) fn controller(game: &Game<'_>, pos: [i32; 3]) -> Option<[i32; 3]> {
    stored_controller(mod_entity(game, pos)?, pos).or_else(|| parts(game, pos)?.1.first().copied())
}

pub(super) fn storage(game: &Game<'_>, pos: [i32; 3]) -> Option<([i32; 3], i32, Option<Fluid>)> {
    if let Some(Tag::IntArray(owner)) = mod_entity(game, pos)
        .and_then(|entity| entity.runtime.get(&"CreateTankCapability".into()))
    {
        if let Ok(root) = <[i32; 3]>::try_from(owner.as_slice()) {
            let entity = mod_entity(game, root)?;
            let width = super::create_machines::int(&entity.nbt, "Size").unwrap_or(1);
            let height = super::create_machines::int(&entity.nbt, "Height").unwrap_or(1);
            let fluid = compound(&entity.nbt, "TankContent")
                .and_then(|tank| read_fluid(compound(tank, "Fluid")?));
            return Some((root, PER_PART * width * width * height, fluid));
        }
    }
    let (_, parts) = parts(game, pos)?;
    let root = *parts.first()?;
    let entity = mod_entity(game, root)?;
    let contained =
        compound(&entity.nbt, "TankContent").and_then(|tank| read_fluid(compound(tank, "Fluid")?));
    let capacity = retained_capacity(entity, PER_PART * parts.len() as i32);
    Some((root, capacity, contained))
}

pub(super) fn write(game: &mut Game<'_>, root: [i32; 3], fluid: Fluid) {
    game.native_with_mod_block_entity(root, |entity| {
        let mut tank = Compound::new();
        if fluid.amount > 0 {
            tank.insert("Fluid".into(), fluid.nbt());
        }
        entity.nbt.insert("TankContent".into(), Tag::Compound(tank));
    });
    if let Some((width, parts)) = parts(game, root) {
        if let Some(entity) = mod_entity(game, root).cloned() {
            super::create_tank_lighting::sync(game, root, width, &parts, &entity);
        }
        for pos in parts { game.native_update_output_neighbors(game.native_dimension(), pos); }
    }
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    game.native_with_mod_block_entity(pos, |live| { live.runtime.remove(&"CreateTankCapability".into()); });
    if super::create_tank_reconnect::tick_identity(game, pos, entity) { return; }
    let Some((width, parts)) = parts(game, pos) else {
        return;
    };
    let Some(root) = parts.first() else { return };
    let height = parts.len() / (width * width);
    let top = if pos[1] == root[1] + height as i32 - 1 {
        "true"
    } else {
        "false"
    };
    let bottom = if pos[1] == root[1] { "true" } else { "false" };
    let relight = game.native_block_property(pos, "top").as_deref() != Some(top)
        || game.native_block_property(pos, "bottom").as_deref() != Some(bottom);
    game.native_set_block_property_with(pos, "top", top, 2);
    game.native_set_block_property_with(pos, "bottom", bottom, 2);
    if *root == pos {
        if game.native_block(pos) == TANK {
            merge_contents(game, entity, &parts);
        }
        entity.nbt.insert("Size".into(), Tag::Int(width as i32));
        entity.nbt.insert("Height".into(), Tag::Int(height as i32));
        super::create_steam::boiler(game, pos, entity, width, &parts);
        super::create_tank_windows::tick(game, pos, entity, width, &parts);
        super::create_tank_lighting::sync(game, pos, width, &parts, entity);
    } else if relight && let Some(controller) = mod_entity(game, *root).cloned() {
        // Updating a member's top/bottom state clears its dynamic emission.
        super::create_tank_lighting::sync(game, *root, width, &parts, &controller);
    }
}

// Bucket interaction follows the tank's own capability; survival players can
// configure creative tanks without consuming the held bucket.
pub(super) fn use_bucket(game: &mut Game<'_>, pos: [i32; 3], stack: &ItemStack) -> bool {
    let block = game.native_block(pos);
    if !matches!(block.as_str(), TANK | CREATIVE) || (block == TANK && !game.creative) {
        return false;
    }
    let Some((root, capacity, mut contained)) = storage(game, pos) else { return true };
    let creative = block == CREATIVE;
    let boiler = super::create_steam::accepts_water(game, root);
    let previous = contained.clone();
    if let Some((incoming, _)) = super::create_item_drain::operation(game, stack) {
        let accepted = if boiler {
            super::create_steam::boiler_fill(game, root, &incoming.id, incoming.amount, false)
        } else {
            super::create_tank_storage::fill(&mut contained, capacity, creative, &incoming, false)
        };
        if accepted == incoming.amount && accepted > 0 {
            if boiler {
                super::create_steam::boiler_fill(game, root, &incoming.id, incoming.amount, true);
            } else if creative {
                super::create_tank_storage::configure(&mut contained, capacity, Some(incoming));
                write(game, root, contained.unwrap());
            } else {
                super::create_tank_storage::fill(&mut contained, capacity, false, &incoming, true);
                if let Some(fluid) = contained { write(game, root, fluid); }
            }
            // CreativeSmartFluidTank replaces its stack after the block has
            // obtained this reference; Java uses that previous stack here.
            let current = if boiler { None } else if creative { previous.clone() }
                else { storage(game, pos).and_then(|(_, _, fluid)| fluid) };
            super::create_tank_feedback::exchange(game, pos, true, current.as_ref(),
                current.as_ref().map_or(0, |fluid| fluid.amount));
        }
        return true;
    }
    let result = if stack.item.as_ref() == "minecraft:glass_bottle" {
        contained.as_ref().and_then(super::create_spout::bottle)
    } else if stack.item.as_ref() == "minecraft:bucket" {
        contained.as_ref().and_then(|fluid| {
            let item = match fluid.id.as_str() {
                "minecraft:water" => Some("minecraft:water_bucket"),
                "minecraft:lava" => Some("minecraft:lava_bucket"),
                "minecraft:milk" => Some("minecraft:milk_bucket"),
                id => horizon_world::fluid::FluidKind::from_name(id).and_then(|kind| kind.info().bucket),
            }?;
            Some((1000, ItemStack::new(item, 1)))
        })
    } else { return false };
    if boiler { return true; }
    if let Some((amount, output)) = result {
        if contained.as_ref().is_some_and(|fluid| fluid.amount >= amount) {
            if !game.creative { game.give_or_drop(output); }
            if creative {
                contained = None;
            } else {
                super::create_tank_storage::drain(&mut contained, false, amount, None, true);
            }
            write(game, root, contained.unwrap_or(Fluid { id: "minecraft:empty".into(), amount: 0, components: None }));
            let current = if creative { previous.clone() }
                else { storage(game, pos).and_then(|(_, _, fluid)| fluid) };
            super::create_tank_feedback::exchange(game, pos, false, previous.as_ref(),
                current.as_ref().map_or(0, |fluid| fluid.amount));
        }
    }
    true
}

// Preserve the surviving parts' shares when a tank is broken.
// The old controller still exists here, even when the removed block is the controller.
pub(super) fn split_pair(level: &mut super::GameLevel<'_>, ticks: &mut horizon_world::level::Ticks, pos: [i32; 3]) {
    use crate::containers::BlockEntity;
    if !level.native_authoritative { return; }
    let key = |p: [i32; 3]| (p[0], p[1], p[2]);
    let kind = match level.world.block_entities.get(&key(pos)) {
        Some(BlockEntity::Mod(entity)) if matches!(entity.id.as_str(), TANK | CREATIVE) => entity.id.clone(),
        _ => return,
    };
    let creative = kind == CREATIVE;
    // Removing any member splits its group into singletons before
    // connectivity is reconsidered on their block-entity ticks.
    let root = match level.world.block_entities.get(&key(pos)) {
        Some(BlockEntity::Mod(entity)) => match entity.nbt.get(&"CreateTankController".into()) {
            Some(Tag::IntArray(owner)) => <[i32; 3]>::try_from(owner.as_slice()).unwrap_or(pos),
            _ => pos,
        },
        _ => pos,
    };
    let dimensions = match level.world.block_entities.get(&key(root)) {
        Some(BlockEntity::Mod(entity)) if entity.id == kind => {
            let width = super::create_machines::int(&entity.nbt, "Size").unwrap_or(1);
            let height = super::create_machines::int(&entity.nbt, "Height").unwrap_or(1);
            let inside = pos[0] >= root[0] && pos[0] < root[0] + width
                && pos[1] >= root[1] && pos[1] < root[1] + height
                && pos[2] >= root[2] && pos[2] < root[2] + width;
            (width >= 1 && height > 0 && (width > 1 || height > 1) && inside).then_some((width, height))
        }
        _ => None,
    };
    if let Some((width, height)) = dimensions {
        let content = match level.world.block_entities.get(&key(root)) {
            Some(BlockEntity::Mod(entity)) => compound(&entity.nbt, "TankContent")
                .and_then(|tank| read_fluid(compound(tank, "Fluid")?)),
            _ => None,
        };
        let mut present = BTreeSet::new();
        for y in 0..height {
            for x in 0..width {
                for z in 0..width {
                    let at = [root[0] + x, root[1] + y, root[2] + z];
                    if matches!(level.world.block_entities.get(&key(at)), Some(BlockEntity::Mod(entity)) if entity.id == kind) {
                        present.insert(at);
                    }
                }
            }
        }
        let parts = super::create_tank_connectivity::split_removed(root, width, height, pos, content, &present, creative);
        for (at, part) in parts {
            if let Some(BlockEntity::Mod(entity)) = level.world.block_entities.get_mut(&key(at)) {
                let mut tank = Compound::new();
                if let Some(fluid) = part.fluid { tank.insert("Fluid".into(), fluid.nbt()); }
                entity.nbt.insert("TankContent".into(), Tag::Compound(tank));
                entity.nbt.insert("CreateTankController".into(), Tag::IntArray(at.to_vec()));
                entity.nbt.insert("Size".into(), Tag::Int(1));
                entity.nbt.insert("Height".into(), Tag::Int(1));
                entity.nbt.insert("CreateTankPendingSplit".into(), Tag::Byte(1));
            }
            super::create_tank_windows::split_singleton(level, ticks, at);
            super::create_tank_lighting::sync_singleton_level(level, at);
        }
        return;
    }
    let lower = [pos[0], pos[1] - 1, pos[2]];
    let root = [pos, lower].into_iter().find(|at| {
        matches!(level.world.block_entities.get(&key(*at)), Some(BlockEntity::Mod(entity))
            if entity.id == kind
                && super::create_machines::int(&entity.nbt, "Size") == Some(1)
                && super::create_machines::int(&entity.nbt, "Height") == Some(2))
    });
    let Some(root) = root else { return };
    let upper = [root[0], root[1] + 1, root[2]];
    let survivor = if pos == root { upper } else { root };
    if pos != root && pos != upper { return; }
    if !matches!(level.world.block_entities.get(&key(survivor)), Some(BlockEntity::Mod(entity)) if entity.id == kind) {
        return;
    }
    let content = match level.world.block_entities.get(&key(root)) {
        Some(BlockEntity::Mod(entity)) => compound(&entity.nbt, "TankContent")
            .and_then(|tank| read_fluid(compound(tank, "Fluid")?)),
        _ => None,
    };
    if let Some(BlockEntity::Mod(entity)) = level.world.block_entities.get_mut(&key(root)) {
        entity.nbt.insert("Height".into(), Tag::Int(1));
    }
    if let Some(BlockEntity::Mod(entity)) = level.world.block_entities.get_mut(&key(survivor)) {
        let mut tank = Compound::new();
        if let Some(mut fluid) = content {
            fluid.amount = fluid.amount.min(PER_PART);
            if fluid.amount > 0 { tank.insert("Fluid".into(), fluid.nbt()); }
        }
        entity.nbt.insert("TankContent".into(), Tag::Compound(tank));
        entity.nbt.insert("CreateTankController".into(), Tag::IntArray(survivor.to_vec()));
        entity.nbt.insert("Size".into(), Tag::Int(1));
        entity.nbt.insert("Height".into(), Tag::Int(1));
    }
    super::create_tank_windows::split_singleton(level, ticks, survivor);
}

// Newly connected tank controllers transfer what fits, then Java drains each
// source tank, including any rejected or excess fluid.
fn merge_contents(game: &mut Game<'_>, entity: &mut ModBlockEntity, parts: &[[i32; 3]]) {
    let mut contents = compound(&entity.nbt, "TankContent")
        .and_then(|tank| read_fluid(compound(tank, "Fluid")?));
    let capacity = PER_PART * parts.len() as i32;
    let mut changed = false;
    for &part in &parts[1..] {
        let Some(other) = mod_entity(game, part).and_then(|other| {
            compound(&other.nbt, "TankContent")
                .and_then(|tank| read_fluid(compound(tank, "Fluid")?))
        }) else { continue };
        let compatible = contents.as_ref().is_none_or(|current| current.same_variant(&other));
        let amount = if compatible {
            (capacity - contents.as_ref().map_or(0, |fluid| fluid.amount)).max(0).min(other.amount)
        } else {
            0
        };
        if amount > 0 {
            if let Some(current) = contents.as_mut() {
                current.amount += amount;
            } else {
                let mut first = other.clone();
                first.amount = amount;
                contents = Some(first);
            }
            changed = true;
        }
        // Java drains each source tank after its attempted transfer, including
        // fluid that the controller rejected or could not fit.
        let mut drained = other;
        drained.amount = 0;
        write(game, part, drained);
    }
    if changed {
        let mut tank = Compound::new();
        if let Some(fluid) = contents { tank.insert("Fluid".into(), fluid.nbt()); }
        entity.nbt.insert("TankContent".into(), Tag::Compound(tank));
    }
}

// A newly placed tank can change its controller before the next tick.
pub(super) fn placed(game: &mut Game<'_>, pos: [i32; 3]) {
    if !game.native_authoritative() || !matches!(game.native_block(pos).as_str(), TANK | CREATIVE) {
        return;
    }
    super::create_tank_reconnect::place(game, pos);
}

// Optional fixture observation after a command or the block-entity phase.
pub(super) fn trace_storage(game: &Game<'_>, phase: &str) {
    use std::io::Write;
    use std::sync::OnceLock;

    static TRACE: OnceLock<Option<std::path::PathBuf>> = OnceLock::new();
    if !game.native_authoritative() {
        return;
    }
    let Some(path) = TRACE.get_or_init(|| std::env::var_os("CREATE_TRACE_TANK_STORAGE").map(Into::into)) else {
        return;
    };
    let Ok(mut file) = std::fs::OpenOptions::new().create(true).append(true).open(path) else {
        return;
    };
    let _ = writeln!(file, "snapshot,{phase},{}", game.world.game_time);
    for &(x, y, z) in game.world.block_entities.keys() {
        let pos = [x, y, z];
        if !matches!(game.native_block(pos).as_str(), TANK | CREATIVE) {
            continue;
        }
        if let Some((root, capacity, fluid)) = storage(game, pos) {
            let (id, amount) = fluid.as_ref().map_or(("minecraft:empty", 0), |fluid| (fluid.id.as_str(), fluid.amount));
            let _ = writeln!(file, "{},{},{},{},{},{},{},{},{},{}", game.world.game_time,
                x, y, z, root[0], root[1], root[2], capacity, id, amount);
        }
    }
}

// Java rebuilds split groups in block-entity ticker order.
pub(super) fn finish_splits(game: &mut Game<'_>) {
    super::create_tank_reconnect::finish(game);
}
