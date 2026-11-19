use horizon_core::geometry::{Direction, Vec3};
use horizon_world::level::flags;
use horizon_world::nbt::{Compound, Tag};

use super::Game;
use super::create_bearing::{
    attached_glue, capture_from, cargo_items, display, move_glue, relative, restore,
};
use super::create_depot::compound;
use super::create_fan::facing;
use super::create_machines::mod_entity;
use super::create_machines::{int, offset, string};
use super::create_portable_interface::ITEM as PORT;
use super::minecarts::CartKind;
use crate::items::ItemStack;

pub(super) const ASSEMBLER: &str = "create:cart_assembler";
const ANCHOR: &str = "create:minecart_anchor";
const PAYLOAD: &str = "CreateCartPayload";
const RAIL_SPEED: f64 = 0.4_f32 as f64;

const RAIL_TYPES: [(&str, &str); 5] = [
    ("regular", "minecraft:rail"),
    ("powered_rail", "minecraft:powered_rail"),
    ("detector_rail", "minecraft:detector_rail"),
    ("activator_rail", "minecraft:activator_rail"),
    ("controller_rail", super::create_controller_rail::RAIL),
];

pub(super) fn use_rail(game: &mut Game<'_>, pos: [i32; 3], held: &ItemStack) -> bool {
    let block = game.native_block(pos);
    if block == ASSEMBLER {
        return exchange_rail(game, pos, held);
    }
    if held.item.as_ref() != ASSEMBLER {
        return false;
    }
    let Some(kind) = RAIL_TYPES
        .iter()
        .find_map(|(kind, rail)| (*rail == block).then_some(*kind))
    else {
        return false;
    };
    let Some(shape) = game.native_block_property(pos, "shape") else {
        return false;
    };
    if !matches!(shape.as_str(), "north_south" | "east_west") {
        return false;
    }
    let backwards = if kind == "controller_rail" {
        game.native_block_property(pos, "backwards").as_deref() == Some("true")
    } else {
        let direction = ((f64::from(game.yaw) / 90.0 + 0.5).floor() as i32).rem_euclid(4);
        matches!(direction, 0 | 3)
    };
    let Some(state) = game.with_level(|_, level, _| {
        let state = level.registry.default_state(ASSEMBLER)?;
        let state = level.native_state_with_property(state, "rail_type", kind)?;
        let state = level.native_state_with_property(state, "shape", &shape)?;
        level.native_state_with_property(
            state,
            "backwards",
            if backwards { "true" } else { "false" },
        )
    }) else {
        return false;
    };
    if !game.native_set_block(game.native_dimension(), pos, state, flags::UPDATE_ALL) {
        return false;
    }
    game.consume_held();
    game.native_play_sound_in_place(
        "minecraft:block.stone.place",
        pos.map(|coordinate| f64::from(coordinate) + 0.5),
        4,
        1.0,
        1.0,
    );
    true
}

fn exchange_rail(game: &mut Game<'_>, pos: [i32; 3], held: &ItemStack) -> bool {
    let Some(old) = game.native_block_property(pos, "rail_type") else {
        return false;
    };
    let Some(new) = RAIL_TYPES
        .iter()
        .find_map(|(kind, item)| (*item == held.item.as_ref()).then_some(*kind))
    else {
        return false;
    };
    if new == old || !game.native_set_block_property_with(pos, "rail_type", new, flags::UPDATE_ALL)
    {
        return false;
    }
    if !game.creative {
        game.consume_held();
        if let Some(returned) = RAIL_TYPES
            .iter()
            .find_map(|(kind, item)| (*kind == old).then_some(*item))
        {
            game.give_or_drop(ItemStack::new(returned, 1));
        }
    }
    game.native_play_sound_in_place(
        "minecraft:entity.item.pickup",
        pos.map(|coordinate| f64::from(coordinate) + 0.5),
        4,
        1.0,
        1.0,
    );
    true
}

pub(super) fn payload_ref<'a>(game: &'a Game<'_>, cart: u32) -> Option<(u32, &'a Compound)> {
    let uuid = game.persist.uuid_of(cart)?;
    game.others.iter().find_map(|marker| {
        if marker.kind != "minecraft:marker" {
            return None;
        }
        let Tag::Compound(tag) = game.persist.raw.get(&marker.id)? else {
            return None;
        };
        let data = compound(tag, PAYLOAD)?;
        let Tag::IntArray(saved) = data.get(&"Cart".into())? else {
            return None;
        };
        (saved == &uuid).then_some((marker.id, data))
    })
}

pub(super) fn has_payload(game: &Game<'_>, cart: u32) -> bool {
    payload_ref(game, cart).is_some()
}

pub(super) fn save(game: &mut Game<'_>, marker: u32, mut data: Compound, blocks: Vec<Compound>) {
    data.insert(
        "Blocks".into(),
        Tag::List(blocks.into_iter().map(Tag::Compound).collect()),
    );
    if let Some(Tag::Compound(tag)) = game.persist.raw.get_mut(&marker) {
        tag.insert(PAYLOAD.into(), Tag::Compound(data));
    }
}

fn point(pos: Vec3) -> [f64; 3] {
    [pos.x, pos.y, pos.z]
}

pub(super) fn cell(pos: Vec3) -> [i32; 3] {
    point(pos).map(|coord| coord.floor() as i32)
}

fn assemble(game: &mut Game<'_>, id: u32, rail: [i32; 3], location: [f64; 3]) -> bool {
    if game.riding == Some(id)
        || game.guest_vehicles().contains(&id)
        || game.mobs.iter().any(|mob| mob.extra.mount == Some(id))
    {
        return false;
    }
    let mut blocks = capture_from(game, rail, rail, [offset(rail, [0, 1, 0])]);
    if blocks.is_empty() {
        return false;
    }
    let locations: Vec<_> = blocks
        .iter()
        .map(|block| offset(rail, relative(block)))
        .collect();
    let glue = attached_glue(game, &locations, rail);
    let uuid = game.uuid_for(id);
    let dimension = game.native_dimension();
    let Some(air) = game.native_default_state("minecraft:air") else {
        return false;
    };
    let Some(marker) = game.native_summon(
        dimension,
        "minecraft:marker",
        location,
        Compound::from([(
            "Tags".into(),
            Tag::List(vec![Tag::String("create_cart_payload".into())]),
        )]),
    ) else {
        return false;
    };
    for pos in locations {
        game.native_set_block(
            dimension,
            pos,
            air,
            flags::UPDATE_ALL | flags::UPDATE_SKIP_BLOCK_ENTITY_SIDEEFFECTS,
        );
    }
    // Java replaces the assembler cell with a visual anchor inside the contraption.
    // The actual assembler stays in the world and the anchor is never restored.
    let axis = if game.native_block_property(rail, "shape").as_deref() == Some("east_west") {
        "x"
    } else {
        "z"
    };
    let backwards = game.native_block_property(rail, "backwards").as_deref() == Some("true");
    let initial_orientation = match (axis, backwards) {
        ("x", false) => "WEST",
        ("x", true) => "EAST",
        (_, false) => "NORTH",
        (_, true) => "SOUTH",
    };
    blocks.push(Compound::from([
        ("Pos".into(), Tag::IntArray(vec![0, 0, 0])),
        (
            "BlockState".into(),
            Tag::Compound(Compound::from([
                ("Name".into(), Tag::String(ANCHOR.into())),
                (
                    "Properties".into(),
                    Tag::Compound(Compound::from([("axis".into(), Tag::String(axis.into()))])),
                ),
            ])),
        ),
    ]));
    let display_origin = rail.map(f64::from);
    for block in &mut blocks {
        display(game, rail, block, 1, 0.0);
        if let Some(id) = int(block, "Display") {
            game.native_move_entity(dimension, id as u32, display_origin, 0.0, 0.0);
        }
    }
    save(
        game,
        marker,
        Compound::from([
            ("Cart".into(), Tag::IntArray(uuid.to_vec())),
            ("Anchor".into(), Tag::IntArray(rail.to_vec())),
            (
                "InitialOrientation".into(),
                Tag::String(initial_orientation.into()),
            ),
            ("Glue".into(), Tag::List(glue)),
        ]),
        blocks,
    );
    true
}

fn refuel(blocks: &mut [Compound], fuel: &mut i32) {
    if *fuel >= 5 {
        return;
    }
    for block in blocks {
        let Some(state) = compound(block, "BlockState") else {
            continue;
        };
        if string(state, "Name").as_deref() == Some("create:item_vault") {
            continue;
        }
        let Some((items, _)) = cargo_items(block) else {
            continue;
        };
        for tag in items.iter_mut() {
            let Tag::Compound(item) = tag else {
                continue;
            };
            if !matches!(
                string(item, "id").as_deref(),
                Some("minecraft:coal" | "minecraft:charcoal")
            ) {
                continue;
            }
            let Some(stack) = ItemStack::from_nbt(item) else {
                continue;
            };
            let count = stack.count as i32;
            item.insert("count".into(), Tag::Int(count - 1));
            if count == 1 {
                items.retain(
                    |entry| !matches!(entry, Tag::Compound(item) if int(item, "count") == Some(0)),
                );
            }
            *fuel += 3600;
            return;
        }
    }
}

fn touch_interfaces(game: &mut Game<'_>, blocks: &[Compound], anchor: [f64; 3], cart: [i32; 4]) {
    let now = game.world.game_time;
    let dim = game.native_dimension();
    for block in blocks {
        let Some(state) = block
            .get(&"BlockState".into())
            .and_then(|tag| game.state_from_nbt(tag))
        else {
            continue;
        };
        if game.res.facts().get(state).name.as_ref() != PORT {
            continue;
        }
        let Some(side) = facing(game, state) else {
            continue;
        };
        let delta = side.normal();
        let local = relative(block);
        let point: [f64; 3] = std::array::from_fn(|i| {
            anchor[i] + f64::from(local[i]) + 0.5 + f64::from(delta[i]) * f64::from(1.85_f32)
        });
        let at = point.map(|value| value.floor() as i32);
        let Some(station) = [at, offset(at, delta)].into_iter().find(|&pos| {
            game.native_block(pos) == PORT
                && facing(game, game.world.block(pos[0], pos[1], pos[2])) == Some(side.opposite())
                && game.native_neighbor_signal(dim, pos) == 0
        }) else {
            continue;
        };
        game.native_with_mod_block_entity(station, |entity| {
            let same = matches!(entity.nbt.get(&"CartDock".into()), Some(Tag::IntArray(previous)) if previous == &cart);
            let present = matches!(entity.nbt.get(&"CartContact".into()), Some(Tag::Long(last)) if (0..=1).contains(&(now - last)));
            if !same || !present {
                entity.nbt.insert("CartDock".into(), Tag::IntArray(cart.to_vec()));
                entity.nbt.insert("CartUntil".into(), Tag::Long(now + 14));
            }
            entity.nbt.insert("CartContact".into(), Tag::Long(now));
        });
    }
}

pub(super) fn extract_docked(
    game: &mut Game<'_>,
    station: [i32; 3],
    funnel: &crate::containers::ModBlockEntity,
    limit: u32,
    exact: bool,
) -> Option<ItemStack> {
    let now = game.world.game_time;
    let data = &mod_entity(game, station)
        .filter(|entity| entity.id == PORT)?
        .nbt;
    let (Some(Tag::IntArray(uuid)), Some(Tag::Long(contact)), Some(Tag::Long(until))) = (
        data.get(&"CartDock".into()),
        data.get(&"CartContact".into()),
        data.get(&"CartUntil".into()),
    ) else {
        return None;
    };
    if !(0..=1).contains(&(now - contact)) || until - now <= 4 {
        return None;
    }
    let id = game.vehicle_by_uuid(uuid.as_slice().try_into().ok()?)?;
    let cart = game
        .carts
        .iter()
        .find(|cart| cart.id == id && cart.kind == CartKind::Chest)?;
    let mut output = cart
        .items
        .iter()
        .flatten()
        .find(|stack| {
            super::create_item_filters::accepts(game.items(), &funnel.nbt, stack)
                && (!exact
                    || cart
                        .items
                        .iter()
                        .flatten()
                        .filter(|item| item.same_item_same_components(stack))
                        .map(|item| item.count)
                        .sum::<u32>()
                        >= limit)
        })?
        .clone();
    let limit = limit.min(game.native_max_stack_size(&output.item).unwrap_or(64));
    output.count = 0;
    let cart = game.carts.iter_mut().find(|cart| cart.id == id)?;
    for slot in &mut cart.items {
        let Some(item) = slot
            .as_mut()
            .filter(|item| item.same_item_same_components(&output))
        else {
            continue;
        };
        let quantity = item.count.min(limit - output.count);
        output.count += quantity;
        item.count -= quantity;
        if item.count == 0 {
            *slot = None;
        }
        if output.count == limit {
            break;
        }
    }
    game.native_with_mod_block_entity(station, |entity| {
        entity.nbt.insert("CartUntil".into(), Tag::Long(now + 63));
    });
    (output.count != 0).then_some(output)
}

fn move_payload(
    game: &mut Game<'_>,
    marker: u32,
    mut data: Compound,
    pos: Vec3,
    rail: [i32; 3],
    release: bool,
    furnace_fuel: Option<&mut i32>,
    previous: Vec3,
    cart_items: &mut [Option<ItemStack>],
) -> bool {
    let Some(Tag::List(saved)) = data.remove(&"Blocks".into()) else {
        return false;
    };
    let mut blocks: Vec<_> = saved
        .into_iter()
        .filter_map(|entry| match entry {
            Tag::Compound(block) => Some(block),
            _ => None,
        })
        .collect();
    let dimension = game.native_dimension();
    let is_anchor = |block: &Compound| {
        compound(block, "BlockState")
            .and_then(|state| string(state, "Name"))
            .as_deref()
            == Some(ANCHOR)
    };
    let restored: Vec<_> = blocks
        .iter()
        .filter(|block| !is_anchor(block))
        .cloned()
        .collect();
    if release && restore(game, rail, &restored, 1, 0.0) {
        for block in blocks.iter().filter(|block| is_anchor(block)) {
            if let Some(id) = int(block, "Display") {
                game.native_remove_entity(dimension, id as u32);
            }
        }
        if let Some(Tag::List(glue)) = data.remove(&"Glue".into()) {
            move_glue(game, &glue, rail.map(f64::from));
        }
        game.native_remove_entity(dimension, marker);
        return true;
    }
    if let Some(fuel) = furnace_fuel {
        refuel(&mut blocks, fuel);
    }
    let anchor = |p: Vec3| [p.x - 0.5, p.y, p.z - 0.5];
    let prior = match data.get(&"PreviousActorAnchor".into()) {
        Some(Tag::List(prior)) if prior.len() == 3 => std::array::from_fn(|i| match prior[i] {
            Tag::Double(bits) => f64::from_bits(bits),
            _ => 0.0,
        }),
        _ => anchor(previous),
    };
    let current = anchor(previous);
    super::create_harvester::translate(game, &mut blocks, prior, current, cart_items);
    if let Some(Tag::IntArray(uuid)) = data.get(&"Cart".into())
        && let Ok(uuid) = uuid.as_slice().try_into()
    {
        touch_interfaces(game, &blocks, current, uuid);
    }
    data.insert(
        "PreviousActorAnchor".into(),
        Tag::List(
            current
                .into_iter()
                .map(|v| Tag::Double(v.to_bits()))
                .collect(),
        ),
    );

    let location = [pos.x, pos.y - 0.0025, pos.z];
    let display_origin = [location[0] - 0.5, location[1], location[2] - 0.5];
    game.native_move_entity(dimension, marker, location, 0.0, 0.0);
    for block in &mut blocks {
        display(game, rail, block, 1, 0.0);
        if let Some(id) = int(block, "Display") {
            game.native_move_entity(dimension, id as u32, display_origin, 0.0, 0.0);
        }
    }
    save(game, marker, data, blocks);
    false
}

fn pass(game: &mut Game<'_>, rail: [i32; 3]) -> Option<(String, bool)> {
    if game.native_block(rail) != ASSEMBLER {
        return None;
    }
    let power = game.native_neighbor_signal(game.native_dimension(), rail) != 0;
    game.native_set_block_property_with(
        rail,
        "powered",
        if power { "true" } else { "false" },
        flags::UPDATE_CLIENTS,
    );
    let kind = game.native_block_property(rail, "rail_type")?;
    let tick = game.world.game_time;
    let mut ready = false;
    game.native_with_mod_block_entity(rail, |assembler| {
        let last = match assembler.nbt.get(&"LastCartPass".into()) {
            Some(Tag::Long(last)) => *last,
            _ => tick - 8,
        };
        ready = tick - last >= 8;
        if ready {
            assembler.nbt.insert("LastCartPass".into(), Tag::Long(tick));
        }
    });
    ready.then_some((kind, power))
}

pub(super) fn tick(game: &mut Game<'_>, id: u32) {
    let Some(cart) = game.carts.iter().find(|cart| cart.id == id) else {
        return;
    };
    let pos = cart.position;
    let previous = cart.previous;
    let mut items = (cart.kind == CartKind::Chest)
        .then(|| cart.items.clone())
        .unwrap_or_default();
    let (kind, mut fuel, mut motion) = (cart.kind, cart.fuel, cart.velocity);
    // The cart reports the rail it moves from. A cart arriving in the
    // assembler's cell runs it when its next rail tick begins.
    let raw = cell(previous);
    let below = offset(raw, [0, -1, 0]);
    let rail = if game.rail(below[0], below[1], below[2]).is_some() {
        below
    } else {
        raw
    };
    let mounted = payload_ref(game, id).map(|(id, data)| (id, data.clone()));
    let action = pass(game, rail);
    let load = matches!(
        action.as_ref().map(|(kind, on)| (kind.as_str(), *on)),
        Some(("regular" | "powered_rail" | "controller_rail", true))
    ) || matches!(
        action.as_ref().map(|(kind, _)| kind.as_str()),
        Some("detector_rail")
    ) && mounted.is_none();
    let release = matches!(
        action.as_ref().map(|(kind, on)| (kind.as_str(), *on)),
        Some(
            ("regular" | "powered_rail" | "controller_rail", false)
                | ("activator_rail", true)
                | ("detector_rail", _)
        )
    );
    let mut assembled = false;
    let mut released = false;
    if let Some((marker, data)) = mounted {
        if kind == CartKind::Furnace && fuel > 1 && game.rail(rail[0], rail[1], rail[2]).is_some() {
            motion = motion.normalize();
        }
        released = move_payload(
            game,
            marker,
            data,
            pos,
            rail,
            release,
            (kind == CartKind::Furnace).then_some(&mut fuel),
            previous,
            &mut items,
        );
    } else if load {
        assembled = assemble(
            game,
            id,
            rail,
            [
                f64::from(rail[0]) + 0.5,
                f64::from(rail[1]),
                f64::from(rail[2]) + 0.5,
            ],
        );
    }
    if let Some((kind, power)) = action {
        if !power && matches!(kind.as_str(), "powered_rail" | "controller_rail") {
            motion = Vec3::new(
                (f64::from(rail[0]) + 0.5 - pos.x) / 16.0,
                0.0,
                (f64::from(rail[2]) + 0.5 - pos.z) / 16.0,
            );
        }
        if power && kind == "controller_rail" {
            let backwards =
                game.native_block_property(rail, "backwards").as_deref() == Some("true");
            let along_x = game.native_block_property(rail, "shape").as_deref() == Some("east_west");
            let [x, _, z] = super::create_controller_rail::direction(along_x, backwards);
            motion = Vec3::new(f64::from(x) * RAIL_SPEED, 0.0, f64::from(z) * RAIL_SPEED);
        }
        if load
            && matches!(kind.as_str(), "powered_rail" | "detector_rail")
            && motion.length() > 1.0 / 128.0
        {
            let faces = match game.native_block_property(rail, "shape").as_deref() {
                Some("east_west") => [Direction::West, Direction::East],
                _ => [Direction::North, Direction::South],
            };
            motion = motion.normalize().scale(RAIL_SPEED);
            for face in faces {
                let [x, y, z] = offset(rail, face.normal());
                let state = game.world.block(x, y, z);
                if game.res.behaviours().facts(state).flags
                    & horizon_world::level::data::state_flags::CONDUCTOR
                    != 0
                {
                    let [vx, vy, vz] = face.opposite().normal();
                    motion = Vec3::new(
                        f64::from(vx) * RAIL_SPEED,
                        f64::from(vy) * RAIL_SPEED,
                        f64::from(vz) * RAIL_SPEED,
                    );
                }
            }
        }
    }
    if let Some(cart) = game.carts.iter_mut().find(|cart| cart.id == id) {
        cart.velocity = motion;
        cart.fuel = fuel;
        if kind == CartKind::Chest {
            cart.items = items;
        }
        if assembled && kind == CartKind::Furnace {
            cart.push = Vec3::ZERO;
        }
        if released && kind == CartKind::Furnace {
            cart.push = Vec3::new(motion.z, 0.0, motion.x);
        }
    }
}
