use horizon_core::{geometry::Direction, position::BlockPos, random::RandomSource};
use horizon_world::{
    level::{LevelAccess, Ticks, flags},
    nbt::{Compound, Tag},
    registry::BlockStateId,
};

use crate::{
    containers::{BlockEntity, ModBlockEntity},
    items::ItemStack,
};

use super::{
    Game, GameLevel, create_package_style::STYLES, create_packager_inventory as inventory,
    create_packager_state as process,
};

pub(super) const PACKAGER: &str = "create:packager";
const REPACKAGER: &str = "create:repackager";

pub(super) fn is_packager(block: &str) -> bool {
    matches!(block, PACKAGER | REPACKAGER)
}

fn relative(pos: BlockPos, direction: Direction) -> BlockPos {
    let [x, y, z] = direction.normal();
    pos.offset(x, y, z)
}

fn key(pos: BlockPos) -> (i32, i32, i32) {
    (pos.x, pos.y, pos.z)
}

pub(super) fn attached_barrel(
    level: &GameLevel<'_>,
    pos: BlockPos,
    state: BlockStateId,
) -> Option<BlockPos> {
    let facing = level.registry.state(state)?.properties.get("facing")?;
    let direction = match facing.as_str() {
        "down" => Direction::Down,
        "up" => Direction::Up,
        "east" => Direction::East,
        "west" => Direction::West,
        "south" => Direction::South,
        "north" => Direction::North,
        _ => return None,
    };
    let target = relative(pos, direction.opposite());
    (level.native_state_block(level.block_state(target)) == Some("minecraft:barrel"))
        .then_some(target)
}

fn address(level: &GameLevel<'_>, pos: BlockPos) -> String {
    Direction::ALL
        .iter()
        .filter_map(|&direction| {
            let BlockEntity::Sign(sign) = level
                .world
                .block_entities
                .get(&key(relative(pos, direction)))?
            else {
                return None;
            };
            [&sign.front, &sign.back].iter().find_map(|side| {
                let address = side
                    .lines
                    .iter()
                    .map(|line| line.trim())
                    .filter(|line| !line.is_empty())
                    .collect::<Vec<_>>()
                    .join(" ");
                (!address.is_empty()).then_some(address)
            })
        })
        .last()
        .unwrap_or_default()
}

fn create_box(level: &mut GameLevel<'_>) -> ItemStack {
    let random = &mut level.world.random;
    let styles = if random.next_int_bound(7500) == Ok(0) {
        &STYLES[4..]
    } else {
        &STYLES[..4]
    };
    let index = random
        .next_int_bound(styles.len() as i32)
        .unwrap_or_default() as usize;
    ItemStack {
        item: format!("create:{}", styles[index].0).into(),
        count: 1,
        damage: 0,
        extra: None,
    }
}

pub(super) fn notify(level: &mut GameLevel<'_>, ticks: &mut Ticks, pos: BlockPos) {
    level.world.modified.insert((pos.x >> 4, pos.z >> 4));
    level
        .behaviours
        .update_neighbour_for_output_signal(level, ticks, pos);
}

pub(super) fn refresh_link(
    level: &mut GameLevel<'_>,
    ticks: &mut Ticks,
    pos: BlockPos,
) -> BlockStateId {
    let state = level.block_state(pos);
    if level.native_state_block(state) != Some(PACKAGER) {
        return state;
    }
    let linked = Direction::ALL.into_iter().any(|side| {
        let neighbor = level.block_state(relative(pos, side));
        super::create_stock_link::attachment(level, neighbor) == Some(side.opposite())
    });
    let property = if linked { "true" } else { "false" };
    if let Some(next) = level.native_state_with_property(state, "linked", property)
        && next != state
    {
        level
            .behaviours
            .set_block(level, ticks, pos, next, flags::UPDATE_CLIENTS);
        return next;
    }
    state
}

fn is_linked(level: &GameLevel<'_>, state: BlockStateId) -> bool {
    level
        .registry
        .state(state)
        .and_then(|info| info.properties.get("linked"))
        .is_some_and(|value| value == "true")
}

pub(super) fn neighbor(
    level: &mut GameLevel<'_>,
    ticks: &mut Ticks,
    pos: BlockPos,
    state: BlockStateId,
) {
    if level.client_side {
        return;
    }
    let Some(info) = level.registry.state(state) else {
        return;
    };
    let prior = info
        .properties
        .get("powered")
        .is_some_and(|value| value == "true");
    let powered = level.behaviours.has_neighbor_signal(level, ticks, pos);
    if prior == powered {
        return;
    }
    if let Some(next) =
        level.native_state_with_property(state, "powered", if powered { "true" } else { "false" })
    {
        level
            .behaviours
            .set_block(level, ticks, pos, next, flags::UPDATE_CLIENTS);
    }
    if !powered {
        return;
    }
    let Some(BlockEntity::Mod(entity)) = level.world.block_entities.get(&key(pos)) else {
        return;
    };
    let mut nbt = entity.nbt.clone();
    process::activate(&mut nbt);
    let state = refresh_link(level, ticks, pos);
    if !is_linked(level, state) {
        if process::may_send(&nbt) {
            send(level, ticks, pos, state, &mut nbt);
        }
        process::finish_activation(&mut nbt);
    }
    if let Some(BlockEntity::Mod(entity)) = level.world.block_entities.get_mut(&key(pos)) {
        entity.nbt = nbt;
    }
    if let Some(log) = level.world.block_log.as_mut() {
        log.push(key(pos));
    }
    notify(level, ticks, pos);
}

fn send(
    level: &mut GameLevel<'_>,
    ticks: &mut Ticks,
    pos: BlockPos,
    state: BlockStateId,
    nbt: &mut Compound,
) -> bool {
    if level.native_state_block(state) == Some(REPACKAGER) {
        return send_repackager(level, ticks, pos, state, nbt);
    }
    let address = address(level, pos);
    nbt.insert("SignAddress".into(), Tag::String(address.as_str().into()));
    let Some(target) = attached_barrel(level, pos, state) else {
        return false;
    };
    let Some(BlockEntity::Chest(slots)) = level.world.block_entities.get(&key(target)) else {
        return false;
    };
    let mut proposed = slots.clone();
    let payload = inventory::collect(&mut proposed, |stack| max_stack(level.items, stack));
    if payload.iter().all(Option::is_none) {
        return false;
    }

    let package = make_package(level, inventory::encode_contents(&payload), &address, None);
    if let Some(BlockEntity::Chest(slots)) = level.world.block_entities.get_mut(&key(target)) {
        *slots = proposed;
    }
    process::start_animation(nbt, &package, false);
    nbt.insert("AnimationStart".into(), Tag::Long(level.game_time()));
    notify(level, ticks, target);
    true
}

fn send_repackager(
    level: &mut GameLevel<'_>,
    ticks: &mut Ticks,
    pos: BlockPos,
    state: BlockStateId,
    nbt: &mut Compound,
) -> bool {
    use super::create_machines::{int, same_stack};
    use super::create_package_open::ORDER;
    let Some(target) = attached_barrel(level, pos, state) else {
        return false;
    };
    let Some(BlockEntity::Chest(slots)) = level.world.block_entities.get(&key(target)) else {
        return false;
    };
    if matches!(nbt.get(&QUEUE.into()), Some(Tag::List(queue)) if !queue.is_empty()) {
        return false;
    }
    let slots = slots.clone();
    let mut groups: Vec<(i32, Vec<(usize, ItemStack, Compound)>)> = Vec::new();
    let mut complete = None;
    for (slot, stack) in slots.iter().enumerate() {
        let Some(stack) = stack
            .as_ref()
            .filter(|s| super::create_package_style::dimensions(&s.item).is_some())
        else {
            continue;
        };
        let order = stack.data().and_then(|data| data.other(ORDER));
        let Some(Tag::Compound(metadata)) = order else {
            let mut package = stack.clone();
            package.count = 1;
            if let Some(BlockEntity::Chest(slots)) =
                level.world.block_entities.get_mut(&key(target))
            {
                if let Some(stack) = slots[slot].as_mut() {
                    stack.count -= 1;
                    if stack.count == 0 {
                        slots[slot] = None;
                    }
                }
            }
            let sign = address(level, pos);
            if !sign.is_empty() {
                package.data_mut().set_other(
                    "create:package_address",
                    Some(Tag::String(sign.as_str().into())),
                );
            }
            process::start_animation(nbt, &package, false);
            nbt.insert("AnimationStart".into(), Tag::Long(level.game_time()));
            notify(level, ticks, target);
            return true;
        };
        let Some(id) = int(metadata, "order_id").filter(|id| *id != -1) else {
            continue;
        };
        let index = groups
            .iter()
            .position(|(key, _)| *key == id)
            .unwrap_or_else(|| {
                groups.push((id, Vec::new()));
                groups.len() - 1
            });
        groups[index]
            .1
            .push((slot, stack.clone(), metadata.clone()));
        let entries = &groups[index].1;
        let mut link = 0;
        let mut fragment = 0;
        loop {
            let Some((_, _, part)) = entries.iter().find(|(_, _, part)| {
                int(part, "link_index") == Some(link)
                    && int(part, "fragment_index") == Some(fragment)
            }) else {
                break;
            };
            if int(part, "is_final").unwrap_or(0) != 0 {
                if int(part, "is_final_link").unwrap_or(0) != 0 {
                    complete = Some(index);
                    break;
                }
                link += 1;
                fragment = 0;
            } else {
                fragment += 1;
            }
        }
        if complete.is_some() {
            break;
        }
    }
    let Some(index) = complete else { return false };
    let (id, entries) = &groups[index];
    let mut summary: Vec<ItemStack> = Vec::new();
    let mut address_value = String::new();
    let mut context = None;
    for (_, package, metadata) in entries {
        address_value = match package
            .data()
            .and_then(|d| d.other("create:package_address"))
        {
            Some(Tag::String(s)) => s.to_string_lossy(),
            _ => String::new(),
        };
        if let Some(value) = metadata.get(&"order_context".into()) {
            context = Some(value.clone());
        }
        if let Some(Tag::List(contents)) = package
            .data()
            .and_then(|d| d.other("create:package_contents"))
        {
            for entry in contents {
                let Some(Tag::Compound(item)) = entry.get("item") else {
                    continue;
                };
                let Some(stack) = ItemStack::from_nbt(item) else {
                    continue;
                };
                if let Some(prior) = summary.iter_mut().find(|prior| same_stack(prior, &stack)) {
                    prior.count += stack.count;
                } else {
                    summary.push(stack);
                }
            }
        }
    }
    let mut output: Vec<ItemStack> = Vec::new();
    let mut ordered = context
        .as_ref()
        .map(super::create_stock_network::order_stacks)
        .unwrap_or_default();
    // Crafting contexts carry patterns whose slot layout must be preserved.
    if let Some(Tag::List(crafts)) = context.as_ref().and_then(|c| c.get("ordered_crafts")) {
        for craft in crafts {
            let Some(Tag::Compound(fields)) = Some(craft) else {
                continue;
            };
            let Some(pattern) = craft.get("pattern") else {
                continue;
            };
            let pattern_stacks: Vec<Option<ItemStack>> = match pattern.get("entries") {
                Some(Tag::List(entries)) => entries
                    .iter()
                    .map(|entry| {
                        let Some(Tag::Compound(stack)) = entry.get("item_stack") else {
                            return None;
                        };
                        ItemStack::from_nbt(stack)
                    })
                    .collect(),
                _ => Vec::new(),
            };
            let mut count = 0;
            for _ in 0..int(fields, "count").unwrap_or(0).max(0) {
                let mut proposed = summary.clone();
                let mut possible = true;
                for required in pattern_stacks.iter().flatten() {
                    let Some(found) = proposed
                        .iter_mut()
                        .find(|s| s.count > 0 && same_stack(s, required))
                    else {
                        possible = false;
                        break;
                    };
                    found.count -= 1;
                }
                if !possible {
                    break;
                }
                summary = proposed;
                count += 1;
            }
            for _ in 0..count {
                let mut payload = std::array::from_fn(|_| None);
                for (slot, stack) in pattern_stacks.iter().take(9).enumerate() {
                    if let Some(mut stack) = stack.clone() {
                        stack.count = 1;
                        payload[slot] = Some(stack);
                    }
                }
                let recipe_context = Tag::compound([
                    (
                        "ordered_stacks",
                        Tag::compound([("entries", Tag::List(Vec::new()))]),
                    ),
                    (
                        "ordered_crafts",
                        Tag::List(vec![Tag::compound([
                            ("pattern", pattern.clone()),
                            ("count", Tag::Int(1)),
                        ])]),
                    ),
                ]);
                let recipe_order = Tag::compound([
                    ("order_id", Tag::Int(level.world.random.next_int())),
                    ("link_index", Tag::Int(0)),
                    ("is_final_link", Tag::Byte(1)),
                    ("fragment_index", Tag::Int(0)),
                    ("is_final", Tag::Byte(1)),
                    ("order_context", recipe_context),
                ]);
                output.push(make_package(
                    level,
                    inventory::encode_contents(&payload),
                    &address_value,
                    Some(recipe_order),
                ));
            }
        }
        if !output.is_empty() {
            ordered.clear();
        }
    }
    let mut slots_out: Vec<ItemStack> = Vec::new();
    while summary.iter().any(|s| s.count > 0) {
        let target = if ordered.is_empty() {
            None
        } else {
            Some(ordered.remove(0))
        };
        for stack in &mut summary {
            if stack.count == 0 || target.as_ref().is_some_and(|item| !same_stack(item, stack)) {
                continue;
            }
            let mut amount = target
                .as_ref()
                .map_or(stack.count, |item| item.count)
                .min(stack.count);
            while amount > 0 {
                let count = amount.min(max_stack(level.items, stack));
                let mut part = stack.clone();
                part.count = count;
                slots_out.push(part);
                stack.count -= count;
                amount -= count;
            }
            break;
        }
    }
    for chunk in slots_out.chunks(9) {
        let mut payload = std::array::from_fn(|_| None);
        for (slot, stack) in chunk.iter().enumerate() {
            payload[slot] = Some(stack.clone());
        }
        output.push(make_package(
            level,
            inventory::encode_contents(&payload),
            &address_value,
            None,
        ));
    }
    let last = output.len().saturating_sub(1);
    for (index, package) in output.iter_mut().enumerate() {
        if package.data().and_then(|d| d.other(ORDER)).is_none() {
            let mut order = Compound::from([
                ("order_id".into(), Tag::Int(*id)),
                ("link_index".into(), Tag::Int(0)),
                ("is_final_link".into(), Tag::Byte(1)),
                ("fragment_index".into(), Tag::Int(0)),
                ("is_final".into(), Tag::Byte(1)),
            ]);
            if index == last
                && let Some(context) = &context
            {
                order.insert("order_context".into(), context.clone());
            }
            package
                .data_mut()
                .set_other(ORDER, Some(Tag::Compound(order)));
        }
    }
    if let Some(BlockEntity::Chest(slots)) = level.world.block_entities.get_mut(&key(target)) {
        for (slot, _, _) in entries {
            if let Some(stack) = slots[*slot].as_mut() {
                stack.count -= 1;
                if stack.count == 0 {
                    slots[*slot] = None;
                }
            }
        }
    }
    if !output.is_empty() {
        nbt.insert(
            QUEUE.into(),
            Tag::List(
                output
                    .iter()
                    .map(|item| {
                        Tag::compound([
                            ("item_stack", super::create_depot::encode(item)),
                            ("count", Tag::Int(1)),
                        ])
                    })
                    .collect(),
            ),
        );
    }
    notify(level, ticks, target);
    true
}

pub(super) fn make_package(
    level: &mut GameLevel<'_>,
    contents: Tag,
    address: &str,
    order: Option<Tag>,
) -> ItemStack {
    let mut package = create_box(level);
    let data = package.data_mut();
    data.set_other("create:package_contents", Some(contents));
    if !address.is_empty() {
        data.set_other("create:package_address", Some(Tag::String(address.into())));
    }
    data.set_other(super::create_package_open::ORDER, order);
    package
}

const QUEUE: &str = "QueuedExitingPackages";

pub(super) fn queued(level: &GameLevel<'_>, pos: BlockPos) -> usize {
    let Some(BlockEntity::Mod(entity)) = level.world.block_entities.get(&key(pos)) else {
        return 0;
    };
    match entity.nbt.get(&QUEUE.into()) {
        Some(Tag::List(queue)) => queue.len(),
        _ => 0,
    }
}

pub(super) fn dispatch(
    level: &mut GameLevel<'_>,
    ticks: &mut Ticks,
    pos: BlockPos,
    package: &ItemStack,
) {
    let now = level.game_time();
    let Some(BlockEntity::Mod(entity)) = level.world.block_entities.get_mut(&key(pos)) else {
        return;
    };
    let nbt = &mut entity.nbt;
    if process::animation(nbt) == 0 && process::held(nbt).is_none() {
        process::start_animation(nbt, package, false);
        nbt.insert("AnimationStart".into(), Tag::Long(now));
    } else {
        let entry = Tag::compound([
            ("item_stack", super::create_depot::encode(package)),
            ("count", Tag::Int(1)),
        ]);
        match nbt.get_mut(&QUEUE.into()) {
            Some(Tag::List(queue)) => queue.push(entry),
            _ => {
                nbt.insert(QUEUE.into(), Tag::List(vec![entry]));
            }
        }
    }
    if let Some(log) = level.world.block_log.as_mut() {
        log.push(key(pos));
    }
    notify(level, ticks, pos);
}

fn pop_package(nbt: &mut Compound) -> Option<ItemStack> {
    let Tag::List(queue) = nbt.get_mut(&QUEUE.into())? else {
        return None;
    };
    if queue.is_empty() {
        return None;
    }
    let entry = queue.remove(0);
    let Some(Tag::Compound(stack)) = entry.get("item_stack") else {
        return None;
    };
    ItemStack::from_nbt(stack)
}

pub(super) fn output(level: &GameLevel<'_>, pos: BlockPos, state: BlockStateId, value: &mut i32) {
    if level.native_state_block(state).is_some_and(is_packager)
        && let Some(BlockEntity::Mod(entity)) = level.world.block_entities.get(&key(pos))
    {
        *value = process::comparator(&entity.nbt);
    }
}

pub(super) fn tick(game: &mut Game<'_>, coords: [i32; 3], entity: &mut ModBlockEntity) {
    use super::create_machines::int;

    let powered = game.native_block_property(coords, "powered").as_deref() == Some("true");
    let phase_before_tick = int(&entity.nbt, "LazyPhase");
    let mut phase = phase_before_tick.unwrap_or(process::LAZY_TICK_RATE);
    let lazy = phase <= 0;
    let retry = process::lazy_update(&mut entity.nbt, &mut phase, powered);
    entity.nbt.insert("LazyPhase".into(), Tag::Int(phase));
    if lazy || phase_before_tick.is_none() {
        let pos = BlockPos::new(coords[0], coords[1], coords[2]);
        let sent = game.with_level(|_, level, ticks| {
            let state = refresh_link(level, ticks, pos);
            retry && !is_linked(level, state) && send(level, ticks, pos, state, &mut entity.nbt)
        });
        if sent {
            game.native_block_entity_sync(coords);
        }
    }
    let animation = process::animation(&entity.nbt);
    let inward = int(&entity.nbt, "AnimationInward").unwrap_or(1) != 0;
    let at = coords.map(|coordinate| f64::from(coordinate) + 0.5);
    if animation == if inward { 15 } else { 19 } {
        game.native_play_sound_in_place("create:packager", at, 4, 1.0, 1.0);
    }
    if animation == if inward { 1 } else { 5 } {
        game.native_play_sound_in_place("minecraft:block.iron_trapdoor.close", at, 4, 0.25, 0.75);
    }
    process::tick_animation(&mut entity.nbt);
    if animation == 0
        && process::held(&entity.nbt).is_none()
        && let Some(package) = pop_package(&mut entity.nbt)
    {
        process::start_animation(&mut entity.nbt, &package, false);
        entity
            .nbt
            .insert("AnimationStart".into(), Tag::Long(game.world.game_time));
        game.native_update_output_neighbors(game.native_dimension(), coords);
    }
    if animation == 1 && process::held(&entity.nbt).is_none() {
        // The ticker has temporarily taken this entity out of the world.
        // Asking now queues the comparator's read of the newly empty output.
        game.native_update_output_neighbors(game.native_dimension(), coords);
    }
}

pub(super) fn click(game: &mut Game<'_>, coords: [i32; 3], canceled: &mut bool) {
    use super::{create_machines::mod_entity, create_package_open};

    if *canceled || !is_packager(&game.native_block(coords)) {
        return;
    }
    let held = game.held().cloned();
    if held.as_ref().is_some_and(|stack| {
        matches!(
            stack.item.as_ref(),
            "create:wrench"
                | "create:factory_gauge"
                | "create:stock_link"
                | "create:package_frogport"
        )
    }) {
        return;
    }
    *canceled = true;
    if game.hand != horizon_client::first_person::Hand::Main
        || (!game.native_authoritative() && game.lan_acting.is_none())
    {
        return;
    }
    let Some(entity) = mod_entity(game, coords) else {
        return;
    };
    if process::animation(&entity.nbt) != 0 {
        return;
    }
    let pos = BlockPos::new(coords[0], coords[1], coords[2]);
    if let Some(box_stack) = process::held(&entity.nbt) {
        game.native_with_mod_block_entity(coords, |entity| {
            entity.nbt.remove(&"HeldBox".into());
        });
        if let Some(left) = game.give(box_stack) {
            game.with_level(|_, level, _| level.drop_lost_contents(pos, vec![Some(left)]));
        }
        game.native_block_entity_sync(coords);
        game.with_level(|_, level, ticks| notify(level, ticks, pos));
        return;
    }

    let Some(mut package) =
        held.filter(|stack| super::create_package_style::dimensions(&stack.item).is_some())
    else {
        return;
    };
    let repackager = game.native_block(coords) == REPACKAGER;
    let payload = create_package_open::contents(game, &package);
    package.count = 1;
    let has_cargo = payload.iter().any(Option::is_some);
    let accepted = (!repackager && !has_cargo)
        || game.with_level(|_, level, ticks| {
            let Some(target) = attached_barrel(level, pos, level.block_state(pos)) else {
                return false;
            };
            let items = level.items;
            let Some(BlockEntity::Chest(slots)) = level.world.block_entities.get_mut(&key(target))
            else {
                return false;
            };
            let accepted = if repackager {
                super::create_machines::insert(slots, &package, max_stack(items, &package)) == 0
            } else {
                inventory::deposit(slots, &payload, |stack| max_stack(items, stack))
            };
            if !accepted {
                return false;
            }
            notify(level, ticks, target);
            true
        });
    if !accepted {
        return;
    }
    if let Some(stack) = game.held_mut().as_mut() {
        stack.count -= 1;
        if stack.count == 0 {
            *game.held_mut() = None;
        }
    }
    if has_cargo || repackager {
        let now = game.world.game_time;
        game.native_with_mod_block_entity(coords, |entity| {
            process::start_animation(&mut entity.nbt, &package, true);
            entity.nbt.insert("AnimationStart".into(), Tag::Long(now));
        });
        game.native_block_entity_sync(coords);
        game.with_level(|_, level, ticks| notify(level, ticks, pos));
    }
    game.native_play_sound_in_place(
        "create:depot_plop",
        coords.map(|coordinate| f64::from(coordinate) + 0.5),
        4,
        0.25,
        1.25,
    );
}

pub(super) fn max_stack(items: &crate::items::Items, stack: &ItemStack) -> u32 {
    if let Some(Tag::Int(limit)) = stack
        .data()
        .and_then(|data| data.other("minecraft:max_stack_size"))
    {
        return (*limit).clamp(1, 99) as u32;
    }
    items
        .get(&stack.item)
        .map_or(64, |item| item.max_stack)
        .max(1)
}
