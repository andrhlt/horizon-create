use std::sync::atomic::{AtomicI64, Ordering};

use horizon_core::geometry::{Aabb, Direction, Vec3};
use horizon_world::nbt::{Compound, Tag};

use crate::containers::ModBlockEntity;
use crate::items::ItemStack;

use super::Game;
use super::create_chain_conveyor::{
    Span, advance_loop, crosses_loop_angle, loop_position, reverse_progress,
};
use super::create_chain_conveyor_connect::links;
use super::create_depot::{compound, encode};
use super::create_machines::{
    CONVEYOR, FROGPORT, float, int, mod_entity, offset, saved_speed, set_float, string,
};
use super::create_package_address;

pub(super) const PACKAGES: &str = "Packages";
const VISUAL_ID: &str = "VisualId";
const PICKUP_CHANNEL: &str = "create:chain_pickup";
pub(super) const CARGO_VISUALS: &str = "CargoVisuals";
pub(super) const CARGO_SAMPLE_TIME: &str = "CargoSampleTime";
static NEXT_VISUAL_ID: AtomicI64 = AtomicI64::new(1);

fn next_visual_id() -> i64 {
    NEXT_VISUAL_ID.fetch_add(1, Ordering::Relaxed)
}

fn visual_id(nbt: &Compound) -> i64 {
    match nbt.get(&VISUAL_ID.into()) {
        Some(Tag::Long(id)) => *id,
        _ => 0,
    }
}

pub(super) struct VisualCargo {
    pub id: i64,
    pub item: String,
    pub position: f32,
    pub edge: Option<[i32; 3]>,
}

pub(super) fn visual_cargo(nbt: &Compound) -> impl Iterator<Item = VisualCargo> + '_ {
    let remote = nbt.contains_key(&CARGO_VISUALS.into());
    entries(nbt, if remote { CARGO_VISUALS } else { PACKAGES })
        .iter()
        .filter_map(move |tag| {
            let Tag::Compound(nbt) = tag else { return None };
            let item = if remote {
                string(nbt, "Item")?
            } else {
                string(compound(nbt, "Item")?, "id")?
            };
            let id = visual_id(nbt);
            (id != 0).then_some(VisualCargo {
                id,
                item,
                position: float(nbt, "Position")?,
                edge: coords(nbt, "Connection"),
            })
        })
}

pub(super) fn cargo_update(nbt: &Compound) -> Tag {
    Tag::List(
        visual_cargo(nbt)
            .map(|cargo| {
                let mut record = Compound::from([
                    (VISUAL_ID.into(), Tag::Long(cargo.id)),
                    ("Item".into(), Tag::String(cargo.item.as_str().into())),
                ]);
                set_float(&mut record, "Position", cargo.position);
                if let Some(edge) = cargo.edge {
                    record.insert("Connection".into(), Tag::IntArray(edge.to_vec()));
                }
                Tag::Compound(record)
            })
            .collect(),
    )
}
const ROUTES: &str = "RoutingEntries";
const CATCH: &str = "ReceivingPackage";
const SEND: &str = "SendingPackage";
const DEPOSITING: &str = "CurrentlyDepositing";
const STARTED: &str = "AnimationStartedAt";
const PORT_LAZY_RATE: i32 = 10;
pub(super) const BLOCKED_EXPORT: &str = "FailedLastExport";
const CAPACITY: usize = 20;
pub(super) const PORT_SLOTS: usize = 18;
pub(super) const ANTICIPATE: &str = "FrogportAnticipate";

fn entries<'a>(tag: &'a Compound, field: &str) -> &'a [Tag] {
    match tag.get(&field.into()) {
        Some(Tag::List(list)) => list.as_slice(),
        _ => &[],
    }
}

fn coords(nbt: &Compound, field: &str) -> Option<[i32; 3]> {
    let Tag::IntArray(values) = nbt.get(&field.into())? else {
        return None;
    };
    values.as_slice().try_into().ok()
}

fn reverse(edge: [i32; 3]) -> [i32; 3] {
    edge.map(|value| -value)
}

fn save(nbt: &mut Compound, field: &str, values: Vec<Tag>) {
    if values.is_empty() {
        nbt.remove(&field.into());
    } else {
        nbt.insert(field.into(), Tag::List(values));
    }
}

pub(super) fn package(game: &Game<'_>, stack: &ItemStack) -> bool {
    game.items()
        .item_tags
        .get("create:packages")
        .is_some_and(|items| items.contains(stack.item.as_ref()))
}

fn address(game: &Game<'_>, stack: &ItemStack) -> String {
    match game.native_component(stack, "create:package_address") {
        Ok(Some(Tag::String(value))) => value.to_string_lossy(),
        _ => String::new(),
    }
}

#[derive(Clone)]
struct Route {
    address: String,
    next: [i32; 3],
    distance: i32,
    ttl: i32,
    local: bool,
}

impl Route {
    fn read(nbt: &Compound) -> Vec<Self> {
        entries(nbt, ROUTES)
            .iter()
            .filter_map(|tag| {
                let Tag::Compound(record) = tag else {
                    return None;
                };
                Some(Self {
                    address: string(record, "Address")?,
                    next: coords(record, "Next")?,
                    distance: int(record, "Distance")?,
                    ttl: int(record, "TTL")?,
                    local: int(record, "Local") == Some(1),
                })
            })
            .collect()
    }

    fn write(nbt: &mut Compound, routes: Vec<Self>) {
        save(
            nbt,
            ROUTES,
            routes
                .into_iter()
                .map(|route| {
                    Tag::Compound(Compound::from([
                        ("Address".into(), Tag::String(route.address.as_str().into())),
                        ("Next".into(), Tag::IntArray(route.next.to_vec())),
                        ("Distance".into(), Tag::Int(route.distance)),
                        ("TTL".into(), Tag::Int(route.ttl)),
                        ("Local".into(), Tag::Byte(i8::from(route.local))),
                    ]))
                })
                .collect(),
        );
    }
}

fn receive_route(routes: &mut Vec<Route>, entry: Route) -> bool {
    let index = routes.partition_point(|candidate| candidate.distance <= entry.distance);
    if let Some(prior) = routes[..index]
        .iter_mut()
        .find(|prior| prior.address == entry.address)
    {
        if prior.distance == entry.distance && prior.next == entry.next {
            prior.ttl = 100;
        }
        return false;
    }
    routes.insert(index, entry);
    true
}

struct Port {
    at: [i32; 3],
    edge: Option<[i32; 3]>,
    position: f32,
    filter: String,
}

fn ports(game: &Game<'_>, origin: [i32; 3], nbt: &Compound) -> Vec<Port> {
    entries(nbt, "PackagePorts")
        .iter()
        .filter_map(|tag| {
            let Tag::Compound(binding) = tag else {
                return None;
            };
            let at = offset(origin, coords(binding, "Port")?);
            let port = mod_entity(game, at).filter(|entity| entity.id == FROGPORT)?;
            if int(&port.nbt, "AcceptsPackages") == Some(0) {
                return None;
            }
            let filter = string(&port.nbt, "AddressFilter").unwrap_or_default();
            Some(Port {
                at,
                edge: coords(binding, "Connection"),
                position: float(binding, "ChainPosition")?,
                filter,
            })
        })
        .collect()
}

fn reciprocal(game: &Game<'_>, origin: [i32; 3], edge: [i32; 3]) -> bool {
    mod_entity(game, offset(origin, edge)).is_some_and(|entity| {
        entity.id == CONVEYOR && links(&entity.nbt).any(|candidate| candidate == reverse(edge))
    })
}

fn route_tick(
    game: &mut Game<'_>,
    at: [i32; 3],
    nbt: &mut Compound,
    ports: &[Port],
    edges: &[[i32; 3]],
) -> Vec<Route> {
    let mut routes = Route::read(nbt);
    let mut changed = int(nbt, "RoutingChanged") == Some(1);
    for port in ports {
        if port.edge.is_none_or(|edge| edges.contains(&edge)) {
            changed |= receive_route(
                &mut routes,
                Route {
                    address: port.filter.clone(),
                    next: port.edge.unwrap_or_default(),
                    distance: if port.filter == "*" { 1000 } else { 0 },
                    ttl: 20,
                    local: true,
                },
            );
        }
    }
    for route in &mut routes {
        route.ttl -= 1;
    }
    let count = routes.len();
    routes.retain(|route| route.ttl > 0);
    changed |= routes.len() != count;
    let age = int(nbt, "RoutingAge").unwrap_or(0) + 1;
    let age = if changed || (!routes.is_empty() && age > 80) {
        for &edge in edges {
            if !reciprocal(game, at, edge) {
                continue;
            }
            let back = reverse(edge);
            game.native_with_mod_block_entity(offset(at, edge), |target| {
                let mut remote = Route::read(&target.nbt);
                let mut changed = int(&target.nbt, "RoutingChanged") == Some(1);
                for route in routes
                    .iter()
                    .filter(|route| route.local || route.next != edge)
                {
                    changed |= receive_route(
                        &mut remote,
                        Route {
                            address: route.address.clone(),
                            next: back,
                            distance: route.distance + 1,
                            ttl: 100,
                            local: false,
                        },
                    );
                }
                remote.retain(|route| route.local || route.next != back || route.ttl == 100);
                Route::write(&mut target.nbt, remote);
                if changed {
                    target.nbt.insert("RoutingChanged".into(), Tag::Byte(1));
                }
            });
        }
        0
    } else if routes.is_empty() {
        0
    } else {
        age
    };
    nbt.remove(&"RoutingChanged".into());
    nbt.insert("RoutingAge".into(), Tag::Int(age));
    Route::write(nbt, routes.clone());
    routes
}

struct Carried {
    id: i64,
    stack: ItemStack,
    position: f32,
    edge: Option<[i32; 3]>,
    flipped: bool,
}

impl Carried {
    fn read(tag: Tag) -> Option<Self> {
        let Tag::Compound(nbt) = tag else { return None };
        Some(Self {
            id: visual_id(&nbt),
            stack: ItemStack::from_nbt(compound(&nbt, "Item")?)?,
            position: float(&nbt, "Position")?,
            edge: coords(&nbt, "Connection"),
            flipped: int(&nbt, "JustFlipped") == Some(1),
        })
    }

    fn write(&self) -> Tag {
        let mut nbt = Compound::from([
            ("Item".into(), encode(&self.stack)),
            (VISUAL_ID.into(), Tag::Long(self.id)),
        ]);
        set_float(&mut nbt, "Position", self.position);
        if let Some(edge) = self.edge {
            nbt.insert("Connection".into(), Tag::IntArray(edge.to_vec()));
        }
        if self.flipped {
            nbt.insert("JustFlipped".into(), Tag::Byte(1));
        }
        Tag::Compound(nbt)
    }
}

fn transfer(game: &mut Game<'_>, at: [i32; 3], carried: &Carried) -> bool {
    let now = game.world.game_time;
    let moved = game.native_with_mod_block_entity(at, |target| {
        if target.id != CONVEYOR {
            return false;
        }
        let mut packages = entries(&target.nbt, PACKAGES).to_vec();
        packages.push(carried.write());
        save(&mut target.nbt, PACKAGES, packages);
        target.nbt.insert(CARGO_SAMPLE_TIME.into(), Tag::Long(now));
        true
    }) == Some(true);
    if moved {
        game.native_block_entity_sync(at);
    }
    moved
}

fn pickup_target(
    game: &Game<'_>,
    key: &str,
    wanted: Option<i64>,
) -> Option<([i32; 3], usize, i64)> {
    let (eye, direction) = game.aim()?;
    let from = Vec3::new(eye[0], eye[1], eye[2]);
    let reach = game.reach() + 1.0;
    let to = from.add_vector(Vec3::new(direction[0], direction[1], direction[2]).scale(reach));
    let mut closest = None;
    let mut best = reach * reach;
    for &(x, y, z) in game.world.block_entities.keys() {
        let at = [x, y, z];
        let Some(wheel) = mod_entity(game, at).filter(|entity| entity.id == CONVEYOR) else {
            continue;
        };
        let reversed = int(&wheel.nbt, "Reversed") == Some(1);
        for (index, tag) in entries(&wheel.nbt, key).iter().enumerate() {
            let Tag::Compound(record) = tag else { continue };
            let id = visual_id(record);
            if wanted.is_some_and(|wanted| wanted != id) || (key == CARGO_VISUALS && id == 0) {
                continue;
            }
            let Some(progress) = float(record, "Position") else {
                continue;
            };
            let [x, y, z] = coords(record, "Connection").map_or_else(
                || loop_position(at, progress),
                |edge| Span::new(at, edge, reversed).position(progress),
            );
            // Java tests the package's unswung target, nine pixels below the
            // chain, with a 0.5-block vertical extension and 0.45 inflation.
            let bounds = Aabb::new(
                Vec3::new(x - 0.45, y - 9.0 / 16.0 - 0.25 - 0.45, z - 0.45),
                Vec3::new(x + 0.45, y - 9.0 / 16.0 + 0.25 + 0.45, z + 0.45),
            );
            if let Some(hit) = bounds.clip(from, to) {
                let distance = hit.subtract(from).length_squared();
                if distance < best {
                    best = distance;
                    closest = Some((at, index, id));
                }
            }
        }
    }
    closest
}

pub(super) fn retrieve(game: &mut Game<'_>) -> bool {
    pickup_target(game, PACKAGES, None).is_some_and(|(at, index, _)| retrieve_from(game, at, index))
}

pub(super) fn send_air_pickup(game: &mut Game<'_>) -> bool {
    if !game.may_build()
        || game.stack_in(game.selected).is_some()
        || game.pick().is_some()
        || game.pick_entity_hit().is_some()
        || (game.native_sneaking()
            && game
                .offhand
                .as_ref()
                .is_some_and(|stack| stack.item.as_ref() == "create:wrench"))
    {
        return false;
    }
    let Some((_, _, id)) = pickup_target(game, CARGO_VISUALS, None) else {
        return false;
    };
    let mut data = [0; 16];
    data[..8].copy_from_slice(&id.to_le_bytes());
    data[8..12].copy_from_slice(&game.yaw.to_le_bytes());
    data[12..].copy_from_slice(&game.pitch.to_le_bytes());
    game.native_net_send_to_server(PICKUP_CHANNEL, &data)
        .is_ok()
}

pub(super) fn receive_air_pickup(game: &mut Game<'_>, player: u128, channel: &str, data: &[u8]) {
    if channel != PICKUP_CHANNEL {
        return;
    }
    let Some((id, data)) = data.split_first_chunk::<8>() else {
        return;
    };
    let Some((yaw, pitch)) = data.split_first_chunk::<4>() else {
        return;
    };
    let Ok(pitch) = pitch.try_into() else { return };
    let (id, yaw, pitch) = (
        i64::from_le_bytes(*id),
        f32::from_le_bytes(*yaw),
        f32::from_le_bytes(pitch),
    );
    if id <= 0 || !yaw.is_finite() || !(-90.0..=90.0).contains(&pitch) {
        return;
    }
    game.native_as_player(player, |game| {
        if !game.may_build() || game.stack_in(game.selected).is_some() {
            return;
        }
        // The click carries its rotation because movement and native messages
        // can arrive on different ticks. The server supplies the eye position.
        let previous = (game.yaw, game.pitch);
        (game.yaw, game.pitch) = (yaw, pitch);
        let target = pickup_target(game, PACKAGES, Some(id));
        (game.yaw, game.pitch) = previous;
        if let Some((at, index, _)) = target {
            retrieve_from(game, at, index);
        }
    });
}

fn retrieve_from(game: &mut Game<'_>, at: [i32; 3], index: usize) -> bool {
    let stack = game.native_with_mod_block_entity(at, |wheel| {
        let mut tags = entries(&wheel.nbt, PACKAGES).to_vec();
        let stack = Carried::read(tags.remove(index))?.stack;
        save(&mut wheel.nbt, PACKAGES, tags);
        Some(stack)
    });
    let Some(Some(stack)) = stack else {
        return false;
    };
    if game.stack_in(game.selected).is_none() {
        *game.stack_in_mut(game.selected) = Some(stack);
    } else {
        game.give_or_drop(stack);
    }
    game.native_block_entity_sync(at);
    true
}

pub(super) fn drop_span(game: &mut Game<'_>, origin: [i32; 3], edge: [i32; 3]) {
    let dropped = game
        .native_with_mod_block_entity(origin, |entity| {
            let reversed = int(&entity.nbt, "Reversed") == Some(1);
            let span = Span::new(origin, edge, reversed);
            let mut dropped = Vec::new();
            let mut remaining = Vec::new();
            if let Some(Tag::List(packages)) = entity.nbt.remove(&PACKAGES.into()) {
                for tag in packages {
                    if matches!(&tag, Tag::Compound(nbt) if coords(nbt, "Connection") == Some(edge))
                    {
                        if let Some(package) = Carried::read(tag) {
                            let [x, y, z] = span.position(package.position);
                            dropped.push((package.stack, [x, y - 0.5, z]));
                        }
                    } else {
                        remaining.push(tag);
                    }
                }
            }
            save(&mut entity.nbt, PACKAGES, remaining);
            dropped
        })
        .unwrap_or_default();
    for (stack, point) in dropped {
        super::create_package_world::spawn(game, &stack, point, [0.0; 3], None);
    }
}

fn has_capacity(game: &Game<'_>, capacity_at: [i32; 3]) -> bool {
    let Some(entity) = mod_entity(game, capacity_at).filter(|entity| entity.id == CONVEYOR) else {
        return false;
    };
    let mut spans = std::collections::HashSet::new();
    let loops = entries(&entity.nbt, PACKAGES)
        .iter()
        .filter(|tag| {
            let Tag::Compound(package) = tag else {
                return false;
            };
            match coords(package, "Connection") {
                Some(edge) => {
                    spans.insert(edge);
                    false
                }
                None => true,
            }
        })
        .count();
    loops + spans.len() < CAPACITY
}

pub(super) fn insert_player_package(
    game: &mut Game<'_>,
    at: [i32; 3],
    position: f32,
    edge: Option<[i32; 3]>,
    mut stack: ItemStack,
) -> bool {
    if !has_capacity(game, edge.map_or(at, |edge| offset(at, edge))) {
        return false;
    }
    stack.count = 1;
    transfer(
        game,
        at,
        &Carried {
            id: next_visual_id(),
            stack,
            position,
            edge,
            flipped: false,
        },
    )
}

pub(super) fn attach_port(
    game: &mut Game<'_>,
    conveyor: [i32; 3],
    port: [i32; 3],
    position: f32,
    edge: Option<[i32; 3]>,
) {
    game.native_with_mod_block_entity(conveyor, |entity| {
        let mut ports = entries(&entity.nbt, "PackagePorts").to_vec();
        ports.retain(|entry| !matches!(entry, Tag::Compound(binding) if coords(binding, "Port") == Some(port)));
        let mut binding = Compound::from([
            ("Port".into(), Tag::IntArray(port.to_vec())),
            ("ChainPosition".into(), Tag::Float(position.to_bits())),
        ]);
        if let Some(edge) = edge {
            binding.insert("Connection".into(), Tag::IntArray(edge.to_vec()));
        }
        ports.push(Tag::Compound(binding));
        save(&mut entity.nbt, "PackagePorts", ports);
    });
    game.native_block_entity_sync(conveyor);
}

fn anticipate(game: &mut Game<'_>, port: &Port) {
    let now = game.world.game_time;
    if game.native_with_mod_block_entity(port.at, |entity| {
        if entity.id != FROGPORT
            || entity.nbt.contains_key(&STARTED.into())
            || (0..PORT_SLOTS).all(|slot| entity.items.get(slot).is_some_and(Option::is_some))
        {
            return false;
        }
        entity.set_client_update_fields(Compound::from([(ANTICIPATE.into(), Tag::Long(now))]));
        true
    }) == Some(true)
    {
        game.native_block_entity_sync(port.at);
        if std::env::var_os("CREATE_FROGPORT_ANTICIPATION").is_some() {
            println!("CREATE_FROGPORT_ANTICIPATE_REQUEST {:?},{now}", port.at);
        }
    }
}

fn catch(game: &mut Game<'_>, port: &Port, stack: &ItemStack) -> bool {
    let now = game.world.game_time;
    let started = game.native_with_mod_block_entity(port.at, |entity| {
        if entity.id != FROGPORT
            || entity.nbt.contains_key(&STARTED.into())
            || entity.nbt.contains_key(&CATCH.into())
            || (0..PORT_SLOTS).all(|slot| entity.items.get(slot).is_some_and(Option::is_some))
        {
            return false;
        }
        entity.nbt.insert(CATCH.into(), encode(stack));
        entity.nbt.remove(&DEPOSITING.into());
        entity.nbt.insert(STARTED.into(), Tag::Long(now));
        set_float(&mut entity.nbt, "AnimationProgress", 0.0);
        true
    }) == Some(true);
    if started {
        game.native_block_entity_sync(port.at);
    }
    started
}

fn port_target(nbt: &Compound, at: [i32; 3]) -> Option<([i32; 3], f32, Option<[i32; 3]>)> {
    let target = compound(nbt, "Target")?;
    Some((
        offset(at, coords(target, "RelativePos")?),
        float(target, "ChainPosition")?,
        coords(target, "Connection"),
    ))
}

fn send_to_inventory_below(
    game: &mut Game<'_>,
    at: [i32; 3],
    entity: &mut ModBlockEntity,
    filter: Option<&str>,
) -> bool {
    let Some(filter) = filter else { return false };
    let below = offset(at, [0, -1, 0]);
    if game.native_block(below) == FROGPORT
        || game
            .native_container_slots(game.native_dimension(), below, Direction::Up)
            .is_none()
    {
        return false;
    }
    let mut blocked = false;
    for slot in &mut entity.items {
        let Some(item) = slot.as_mut().filter(|item| {
            package(game, item) && create_package_address::matches(&address(game, item), filter)
        }) else {
            continue;
        };
        let mut stack = item.clone();
        stack.count = 1;
        if game
            .native_insert_item(below, Direction::Up, stack)
            .is_some()
        {
            blocked = true;
            continue;
        }
        item.count -= 1;
        if item.count == 0 {
            *slot = None;
        }
    }
    blocked
}

fn outbound_stack(
    game: &mut Game<'_>,
    below: [i32; 3],
    entity: &mut ModBlockEntity,
    filter: Option<&str>,
) -> Option<ItemStack> {
    let outbound = |game: &Game<'_>, item: &ItemStack| {
        package(game, item)
            && filter
                .is_none_or(|filter| !create_package_address::matches(&address(game, item), filter))
    };
    if let Some(slot) = entity
        .items
        .iter_mut()
        .find(|slot| slot.as_ref().is_some_and(|item| outbound(game, item)))
    {
        let item = slot.as_mut().unwrap();
        let mut stack = item.clone();
        stack.count = 1;
        item.count -= 1;
        if item.count == 0 {
            *slot = None;
        }
        return Some(stack);
    }

    if game.native_block(below) == FROGPORT {
        return None;
    }
    let packager = super::create_packager::is_packager(&game.native_block(below));
    let dimension = game.native_dimension().to_owned();
    let slot = game
        .native_container_slots(&dimension, below, Direction::Up)?
        .into_iter()
        .find(|slot| {
            slot.can_take
                && slot.stack.as_ref().is_some_and(|item| {
                    if packager {
                        package(game, item)
                    } else {
                        outbound(game, item)
                    }
                })
        })?;
    game.native_extract_item(&dimension, below, Direction::Up, slot.slot, 1)
}

fn try_start_outbound(
    game: &mut Game<'_>,
    at: [i32; 3],
    entity: &mut ModBlockEntity,
    filter: Option<&str>,
) -> bool {
    let Some((conveyor, _, edge)) = port_target(&entity.nbt, at) else {
        return false;
    };
    if !mod_entity(game, conveyor).is_some_and(|wheel| {
        wheel.id == CONVEYOR
            && saved_speed(&wheel.nbt) != 0.0
            && edge.is_none_or(|edge| {
                links(&wheel.nbt).any(|link| link == edge) && reciprocal(game, conveyor, edge)
            })
    }) || !has_capacity(game, edge.map_or(conveyor, |edge| offset(conveyor, edge)))
    {
        return false;
    }
    let Some(stack) = outbound_stack(game, offset(at, [0, -1, 0]), entity, filter) else {
        return false;
    };
    entity.nbt.insert(SEND.into(), encode(&stack));
    entity.nbt.insert(DEPOSITING.into(), Tag::Byte(1));
    entity
        .nbt
        .insert(STARTED.into(), Tag::Long(game.world.game_time));
    set_float(&mut entity.nbt, "AnimationProgress", 0.0);
    true
}

fn drop_port_package(game: &mut Game<'_>, at: [i32; 3], stack: &ItemStack) {
    super::create_package_world::spawn(
        game,
        stack,
        at.map(|axis| f64::from(axis) + 0.5),
        [0.0; 3],
        None,
    );
}

pub(super) fn restore_chunk(game: &mut Game<'_>, chunk: [i32; 2]) {
    let [x, z] = chunk.map(|coord| f64::from(coord) * 16.0 + 8.0);
    let machines: Vec<_> = game
        .world
        .block_entities
        .mods_near(x, z, 0.0)
        .copied()
        .filter(|&(x, y, z)| {
            mod_entity(game, [x, y, z]).is_some_and(|entity| {
                entity.id == CONVEYOR
                    || entity.id == FROGPORT && entity.nbt.contains_key(&STARTED.into())
            })
        })
        .collect();
    for (x, y, z) in machines {
        game.native_with_mod_block_entity([x, y, z], |entity| {
            if entity.id == CONVEYOR {
                // Java initializes direction from loaded RPM and reloads
                // packages without the transient reversal marker.
                let reversed = saved_speed(&entity.nbt) < 0.0;
                entity
                    .nbt
                    .insert("Reversed".into(), Tag::Byte(i8::from(reversed)));
                if let Some(Tag::List(packages)) = entity.nbt.get_mut(&PACKAGES.into()) {
                    for tag in packages {
                        if let Tag::Compound(package) = tag {
                            package.remove(&"JustFlipped".into());
                            package.insert(VISUAL_ID.into(), Tag::Long(next_visual_id()));
                        }
                    }
                }
                return;
            }
            // Java deserializes the in-flight package and starts its animation
            // on the first tick. It does not save the animation's phase.
            entity.nbt.remove(&STARTED.into());
            set_float(&mut entity.nbt, "AnimationProgress", 0.0);
        });
    }
}

pub(super) fn open_port(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    let block = game.native_block(pos);
    if game.hand != super::Hand::Main
        || game.native_sneaking()
        || (block != FROGPORT && !super::create_postbox::block(&block))
    {
        return false;
    }
    if game
        .held()
        .is_some_and(|stack| stack.item.as_ref() == super::create_clipboard::ITEM)
    {
        let address = mod_entity(game, pos)
            .and_then(|entity| string(&entity.nbt, "AddressFilter"))
            .unwrap_or_default();
        super::create_clipboard::copy_address(game, &address);
        return true;
    }
    if block == FROGPORT
        && game.held().is_some_and(|stack| stack.item.as_ref() == "create:goggles")
        && game.native_with_mod_block_entity(pos, |entity| {
            if int(&entity.nbt, "Goggles") == Some(1) {
                return false;
            }
            entity.nbt.insert("Goggles".into(), Tag::Byte(1));
            true
        }) == Some(true)
    {
        game.native_block_entity_sync(pos);
        let center = pos.map(|axis| f64::from(axis) + 0.5);
        game.native_play_sound_in_place("minecraft:item.armor.equip_gold", center, 4, 0.5, 1.0);
        return true;
    }
    game.open_menu(pos);
    true
}

pub(super) fn port_layout() -> crate::mod_api::NativeScreen {
    crate::mod_api::NativeScreen {
        width: 220.0,
        height: 190.0,
        slots: (0..PORT_SLOTS)
            .map(|slot| {
                Some([
                    27.0 + (slot % 9) as f32 * 18.0,
                    9.0 + (slot / 9) as f32 * 18.0,
                ])
            })
            .collect(),
        inventory_x: 38.0,
        inventory_y: 108.0,
        own_labels: true,
        own_background: true,
    }
}

pub(super) fn draw_port_screen(
    game: &Game<'_>,
    batch: &mut horizon_client::hud::HudBatch,
    [x, y]: [f32; 2],
) {
    let frogport = "create:gui/frogport_and_mailbox";
    game.native_sprite(
        batch,
        frogport,
        [0.0, 0.0, 214.0, 17.0],
        [x, y - 17.0, 214.0, 17.0],
    );
    game.native_sprite(
        batch,
        frogport,
        [0.0, 47.0, 220.0, 82.0],
        [x, y, 220.0, 82.0],
    );
    game.native_sprite(
        batch,
        "create:gui/player_inventory",
        [0.0, 0.0, 176.0, 108.0],
        [x + 30.0, y + 90.0, 176.0, 108.0],
    );
    super::create_frogport_screen::draw(game, batch, [x, y]);
}

pub(super) fn tick_port(game: &mut Game<'_>, at: [i32; 3], entity: &mut ModBlockEntity) {
    if !entity.nbt.contains_key(&STARTED.into())
        && [CATCH, SEND]
            .iter()
            .any(|&key| entity.nbt.contains_key(&key.into()))
    {
        entity
            .nbt
            .insert(STARTED.into(), Tag::Long(game.world.game_time));
        game.native_block_entity_sync(at);
    }
    // SmartBlockEntity initializes with one lazy tick, then counts ten
    // intervening ticks before polling inventory again.
    let lazy = entity.data.first().is_none_or(|remaining| *remaining <= 0);
    if lazy {
        if entity.data.is_empty() {
            entity.data.push(PORT_LAZY_RATE - 1);
        } else {
            entity.data[0] = PORT_LAZY_RATE;
        }
        if !entity.nbt.contains_key(&STARTED.into()) {
            let filter = (int(&entity.nbt, "AcceptsPackages") != Some(0))
                .then(|| string(&entity.nbt, "AddressFilter").unwrap_or_default());
            let was_blocked = int(&entity.nbt, BLOCKED_EXPORT) == Some(1);
            let blocked = send_to_inventory_below(game, at, entity, filter.as_deref());
            if blocked {
                entity.nbt.insert(BLOCKED_EXPORT.into(), Tag::Byte(1));
            } else {
                entity.nbt.remove(&BLOCKED_EXPORT.into());
            }
            if try_start_outbound(game, at, entity, filter.as_deref()) || blocked != was_blocked {
                game.native_block_entity_sync(at);
            }
        }
    } else {
        entity.data[0] -= 1;
    }

    if !entity.nbt.contains_key(&STARTED.into()) {
        return;
    }
    let progress = float(&entity.nbt, "AnimationProgress").unwrap_or(0.0) + 0.1;
    let depositing = int(&entity.nbt, DEPOSITING) == Some(1);
    if depositing
        && progress > 0.5
        && let Some(Tag::Compound(nbt)) = entity.nbt.remove(&SEND.into())
        && let Some(stack) = ItemStack::from_nbt(&nbt)
    {
        let delivered = port_target(&entity.nbt, at).is_some_and(|(conveyor, position, edge)| {
            if let Some(edge) = edge
                && !mod_entity(game, conveyor)
                    .is_some_and(|wheel| links(&wheel.nbt).any(|link| link == edge))
            {
                return false;
            }
            transfer(
                game,
                conveyor,
                &Carried {
                    id: next_visual_id(),
                    stack: stack.clone(),
                    position,
                    edge,
                    flipped: false,
                },
            )
        });
        if !delivered {
            drop_port_package(game, at, &stack);
        }
        game.native_block_entity_sync(at);
    }
    if progress < 1.0 {
        set_float(&mut entity.nbt, "AnimationProgress", progress);
        return;
    }
    if let Some(Tag::Compound(nbt)) = entity.nbt.remove(&CATCH.into())
        && let Some(stack) = ItemStack::from_nbt(&nbt)
    {
        if let Some(slot) = entity
            .items
            .iter_mut()
            .take(PORT_SLOTS)
            .find(|slot| slot.is_none())
        {
            *slot = Some(stack);
        } else {
            drop_port_package(game, at, &stack);
        }
    }
    set_float(&mut entity.nbt, "AnimationProgress", 0.0);
    entity.nbt.remove(&STARTED.into());
    game.native_block_entity_sync(at);
}

pub(super) fn tick(game: &mut Game<'_>, at: [i32; 3], nbt: &mut Compound, rpm: f32) {
    let edges: Vec<_> = links(nbt).collect();
    let ports = ports(game, at, nbt);
    let routes = route_tick(game, at, nbt, &ports, &edges);
    if let Some(Tag::List(packages)) = nbt.get_mut(&PACKAGES.into()) {
        for tag in packages {
            if let Tag::Compound(package) = tag
                && visual_id(package) == 0
            {
                package.insert(VISUAL_ID.into(), Tag::Long(next_visual_id()));
            }
        }
        nbt.insert(CARGO_SAMPLE_TIME.into(), Tag::Long(game.world.game_time));
        game.native_block_entity_sync(at);
    }
    if rpm == 0.0 {
        return;
    }

    let reversed = rpm < 0.0;
    let direction_changed = reversed != (int(nbt, "Reversed") == Some(1));
    nbt.insert("Reversed".into(), Tag::Byte(i8::from(reversed)));
    let Some(Tag::List(old)) = nbt.remove(&PACKAGES.into()) else {
        return;
    };
    let mut retained = Vec::with_capacity(old.len());

    // Java advances span packages before deciding which loops depart this tick.
    let mut packages: Vec<_> = old.into_iter().filter_map(Carried::read).collect();
    packages.sort_by_key(|carried| carried.edge.is_none());
    for mut carried in packages {
        let address = address(game, &carried.stack);
        if let Some(edge) = carried.edge {
            if !edges.contains(&edge) || !reciprocal(game, at, edge) {
                retained.push(carried.write());
                continue;
            }
            let target = offset(at, edge);
            if direction_changed && !carried.flipped {
                carried.position = reverse_progress(edge, carried.position);
                carried.edge = Some(reverse(edge));
                carried.flipped = true;
                if transfer(game, target, &carried) {
                    continue;
                }
                carried.position = reverse_progress(edge, carried.position);
                carried.edge = Some(edge);
            }
            let prior = carried.position;
            carried.flipped = false;
            let span = Span::new(at, edge, reversed);
            carried.position = span.advance(prior, rpm);
            let ahead = span.advance(carried.position, rpm * 4.0);
            if ports.iter().any(|port| {
                if port.edge != Some(edge)
                    || prior > port.position
                    || ahead < port.position
                    || !create_package_address::matches(&address, &port.filter)
                {
                    return false;
                }
                if carried.position < port.position {
                    anticipate(game, port);
                    false
                } else {
                    catch(game, port, &carried.stack)
                }
            }) {
                continue;
            }
            if carried.position >= span.length {
                carried.position = span.arrival;
                carried.edge = None;
                if transfer(game, target, &carried) {
                    continue;
                }
                carried.position = span.length;
                carried.edge = Some(edge);
            }
        } else {
            carried.flipped = false;
            let prior = carried.position;
            carried.position = advance_loop(prior, rpm);
            let ahead = advance_loop(carried.position, rpm * 4.0);
            if ports.iter().any(|port| {
                if port.edge.is_some() {
                    return false;
                }
                let reached = crosses_loop_angle(prior, carried.position, port.position, reversed);
                if !(reached || crosses_loop_angle(prior, ahead, port.position, reversed))
                    || !create_package_address::matches(&address, &port.filter)
                {
                    return false;
                }
                if reached {
                    catch(game, port, &carried.stack)
                } else {
                    anticipate(game, port);
                    false
                }
            }) {
                continue;
            }
            if let Some(route) = routes
                .iter()
                .find(|route| create_package_address::matches(&address, &route.address))
                && edges.contains(&route.next)
                && reciprocal(game, at, route.next)
            {
                let span = Span::new(at, route.next, reversed);
                if crosses_loop_angle(prior, carried.position, span.departure, reversed)
                    && mod_entity(game, offset(at, route.next)).is_some_and(|other| {
                        entries(&other.nbt, PACKAGES).iter().filter(|tag| {
                            matches!(tag, Tag::Compound(nbt) if coords(nbt, "Connection").is_none())
                        }).count() < CAPACITY
                    })
                {
                    carried.position = 0.0;
                    carried.edge = Some(route.next);
                }
            }
        }
        retained.push(carried.write());
    }
    save(nbt, PACKAGES, retained);
}
