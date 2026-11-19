use std::{cell::RefCell, collections::HashMap, path::Path};

use horizon_client::{lan::menu::Slots, mod_api::NativeServerPlayer, text::Text};
use horizon_world::nbt::Tag;
use serde::{Deserialize, Serialize};

use crate::containers::ModBlockEntity;
use crate::items::{ItemStack, Items};

use super::{
    Game,
    create_machines::{insert, mod_entity},
    create_packager::max_stack,
    create_toolbox::{self, COMPARTMENTS, SLOTS, STACKS_PER_COMPARTMENT},
    native_inventories::NativeInventoryKind,
};

pub(super) const CHANNEL: &str = "create:toolbox_links";
pub(super) const RANGE_SQUARED: f64 = 100.0;
const HOTBAR: usize = 9;

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Eq, Serialize)]
pub(super) struct Link {
    pub pos: [i32; 3],
    pub compartment: usize,
}

pub(super) type Hotbar = [Option<Link>; HOTBAR];

thread_local! {
    static LINKS: RefCell<HashMap<u128, Hotbar>> = RefCell::new(HashMap::new());
}

#[derive(Serialize, Deserialize)]
pub(super) enum Request {
    Browse,
    Equip { link: Link, slot: usize },
    Unequip { slot: usize },
    Deposit { positions: Vec<[i32; 3]> },
}

#[derive(Serialize, Deserialize)]
pub(super) struct ToolboxChoice {
    pub pos: [i32; 3],
    pub item: String,
    pub title: String,
    pub compartments: [Option<(String, u32)>; COMPARTMENTS],
}

#[derive(Serialize, Deserialize)]
pub(super) struct Reply {
    pub selected: usize,
    pub links: Hotbar,
    pub link: Option<Link>,
    pub boxes: Vec<ToolboxChoice>,
    pub browse: bool,
}

fn hotbar(player: u128) -> Hotbar {
    LINKS.with_borrow(|links| links.get(&player).copied().unwrap_or_default())
}

fn set_link(player: u128, slot: usize, value: Option<Link>) {
    LINKS.with_borrow_mut(|links| {
        links.entry(player).or_default()[slot] = value;
    });
}

fn file(directory: &Path, player: u128) -> std::path::PathBuf {
    let id = format!("{player:032x}");
    let name = format!(
        "{}-{}-{}-{}-{}.create-toolbox.json",
        &id[..8],
        &id[8..12],
        &id[12..16],
        &id[16..20],
        &id[20..]
    );
    directory.join(name)
}

pub(super) fn load(player: u128, directory: &Path) {
    let mut saved = std::fs::read(file(directory, player))
        .ok()
        .and_then(|contents| serde_json::from_slice::<Hotbar>(&contents).ok())
        .unwrap_or_default();
    for link in &mut saved {
        if link.is_some_and(|link| link.compartment >= COMPARTMENTS) {
            *link = None;
        }
    }
    LINKS.with_borrow_mut(|links| {
        links.insert(player, saved);
    });
}

pub(super) fn save(player: u128, directory: &Path) {
    let slots = hotbar(player);
    let path = file(directory, player);
    if slots.iter().all(Option::is_none) {
        let _ = std::fs::remove_file(path);
    } else if let Ok(contents) = serde_json::to_vec(&slots) {
        let temporary = path.with_extension("json.tmp");
        if std::fs::write(&temporary, contents).is_ok() {
            let _ = std::fs::rename(temporary, path);
        }
    }
}

pub(super) fn clear() {
    LINKS.with_borrow_mut(HashMap::clear);
}

pub(super) fn distance(position: [f64; 3], pos: [i32; 3]) -> f64 {
    [0.5, 0.0, 0.5]
        .into_iter()
        .enumerate()
        .map(|(axis, center)| (position[axis] - f64::from(pos[axis]) - center).powi(2))
        .sum()
}

fn group(slots: &mut [Option<ItemStack>], compartment: usize) -> &mut [Option<ItemStack>] {
    let first = compartment * STACKS_PER_COMPARTMENT;
    &mut slots[first..first + STACKS_PER_COMPARTMENT]
}

fn add(items: &Items, slots: &mut [Option<ItemStack>], stack: &mut ItemStack) {
    let limit = max_stack(items, stack);
    for index in (0..slots.len()).rev() {
        if stack.count == 0 {
            return;
        }
        let inserted = match &mut slots[index] {
            Some(existing) if existing.same_item_same_components(stack) => {
                let count = stack.count.min(limit.saturating_sub(existing.count));
                existing.count += count;
                count
            }
            Some(_) => 0,
            slot @ None => {
                let count = stack.count.min(limit);
                *slot = Some(ItemStack {
                    count,
                    ..stack.clone()
                });
                count
            }
        };
        stack.count -= inserted;
        if inserted > 0 {
            create_toolbox::settle(items, slots);
        }
    }
}

fn take(slots: &mut [Option<ItemStack>], amount: u32) -> Option<ItemStack> {
    let mut left = amount;
    let mut sample = None;
    for slot in slots.iter_mut().rev() {
        if left == 0 {
            break;
        }
        if let Some(stack) = slot {
            let count = left.min(stack.count);
            stack.count -= count;
            left -= count;
            sample = Some(stack.clone());
            if stack.count == 0 {
                *slot = None;
            }
        }
    }
    sample.map(|stack| ItemStack {
        count: amount - left,
        ..stack
    })
}

fn inventory(game: &Game<'_>, player: u128, slot: usize) -> Option<ItemStack> {
    if game.lan_acting_uuid == Some(player) {
        return game.inventory.get(slot)?.clone();
    }
    game.native_attack_stack(player, slot)
        .or_else(|| game.native_player_stacks(player)?.get(slot)?.clone())
}

fn set_inventory(
    game: &mut Game<'_>,
    player: u128,
    slot: usize,
    previous: Option<&ItemStack>,
    new: Option<ItemStack>,
) -> bool {
    if game.lan_acting_uuid == Some(player) {
        let Some(current) = game.inventory.get_mut(slot) else {
            return false;
        };
        if current.as_ref() != previous {
            return false;
        }
        *current = new;
        game.guest_inventory_resend = true;
        return true;
    }
    if game
        .native_attack_players()
        .iter()
        .any(|actor| actor.uuid == player)
    {
        return game.native_attack_set_stack(player, slot, previous, new);
    }
    game.native_set_inventory_slot_typed(player, NativeInventoryKind::Player, slot, previous, new)
        .is_ok()
}

fn disassemble_link(game: &mut Game<'_>, actor: &NativeServerPlayer, slot: usize, keep: bool) {
    let link = hotbar(actor.uuid)[slot];
    set_link(actor.uuid, slot, None);
    let Some(link) =
        link.filter(|link| !keep && distance(actor.position, link.pos) < RANGE_SQUARED)
    else {
        return;
    };
    let Some(entity) =
        mod_entity(game, link.pos).filter(|entity| entity.id == create_toolbox::ENTITY)
    else {
        return;
    };
    let (Some(filter), Some(current)) = (
        create_toolbox::saved_filter(&entity.nbt, link.compartment),
        inventory(game, actor.uuid, slot),
    ) else {
        return;
    };
    if !create_toolbox::compatible(game.items(), &filter, &current) {
        return;
    }
    let mut slots = entity.items.clone();
    slots.resize(SLOTS, None);
    let mut remainder = current.clone();
    if remainder.item.as_ref() == "create:belt_connector" {
        remainder
            .data_mut()
            .set_other("create:belt_first_shaft", None);
    }
    add(
        game.items(),
        group(&mut slots, link.compartment),
        &mut remainder,
    );
    if remainder.count != current.count
        && set_inventory(
            game,
            actor.uuid,
            slot,
            Some(&current),
            (remainder.count > 0).then_some(remainder),
        )
    {
        game.native_with_mod_block_entity(link.pos, |entity| entity.items = slots);
        game.native_block_entity_sync(link.pos);
        game.native_update_output_neighbors(game.native_dimension(), link.pos);
    }
}

fn relocate(game: &mut Game<'_>, actor: &NativeServerPlayer, link: Link, slot: usize) {
    let Some(entity) = mod_entity(game, link.pos) else {
        return;
    };
    let Ok(inventory) = game.native_inventory_typed(actor.uuid, NativeInventoryKind::Player) else {
        return;
    };
    if !inventory.online {
        return;
    }
    let mut player_items = inventory.slots;
    let Some(mut current) = player_items[slot].clone() else {
        return;
    };
    if create_toolbox::saved_filter(&entity.nbt, link.compartment)
        .is_some_and(|filter| create_toolbox::compatible(game.items(), &filter, &current))
    {
        return;
    }
    let mut proposed = entity.clone();
    proposed.items.resize(SLOTS, None);
    super::create_toolbox_menu::deposit(game.items(), &mut proposed, &mut current);
    current.count = insert(
        &mut player_items[9..36],
        &current,
        max_stack(game.items(), &current),
    );
    player_items[slot] = (current.count > 0).then_some(current);
    if game
        .native_set_inventory_typed(actor.uuid, NativeInventoryKind::Player, player_items, None)
        .is_ok()
    {
        game.native_with_mod_block_entity(link.pos, |entity| {
            entity.items = std::mem::take(&mut proposed.items)
        });
        game.native_block_entity_sync(link.pos);
    }
}

fn deposit_to(game: &mut Game<'_>, actor: &NativeServerPlayer, pos: [i32; 3]) {
    if distance(actor.position, pos) > RANGE_SQUARED {
        return;
    }
    let Some(entity) = mod_entity(game, pos).filter(|entity| entity.id == create_toolbox::ENTITY)
    else {
        return;
    };
    let mut proposal = entity.clone();
    proposal.items.resize(SLOTS, None);
    let Ok(inventory) = game.native_inventory_typed(actor.uuid, NativeInventoryKind::Player) else {
        return;
    };
    if !inventory.online {
        return;
    }
    for (slot, link) in hotbar(actor.uuid).into_iter().enumerate() {
        if link.is_some_and(|link| link.pos == pos) {
            set_link(actor.uuid, slot, None);
        }
    }
    let mut player_items = inventory.slots;
    for slot in player_items.iter_mut().take(36) {
        if let Some(stack) = slot.as_mut() {
            super::create_toolbox_menu::deposit(game.items(), &mut proposal, stack);
            if stack.count == 0 {
                *slot = None;
            }
        }
    }
    if game
        .native_set_inventory_typed(actor.uuid, NativeInventoryKind::Player, player_items, None)
        .is_ok()
    {
        game.native_with_mod_block_entity(pos, |entity| {
            entity.items = std::mem::take(&mut proposal.items)
        });
        game.native_block_entity_sync(pos);
        game.native_update_output_neighbors(game.native_dimension(), pos);
    }
}

fn is_open(game: &Game<'_>, player: u128, pos: [i32; 3]) -> bool {
    game.lan
        .as_ref()
        .and_then(|host| host.hub.guests.iter().find(|guest| guest.uuid == player))
        .and_then(|guest| guest.menu.as_ref())
        .is_some_and(|menu| matches!(menu.slots, Slots::Block((x,y,z)) if pos == [x,y,z]))
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    let linked = LINKS.with_borrow(|links| {
        links
            .iter()
            .filter_map(|(&player, hotbar)| {
                let slots = hotbar
                    .iter()
                    .enumerate()
                    .filter_map(|(slot, link)| {
                        link.filter(|link| link.pos == pos)
                            .map(|link| (slot, link.compartment))
                    })
                    .collect::<Vec<_>>();
                (!slots.is_empty()).then_some((player, slots))
            })
            .collect::<HashMap<_, _>>()
    });
    if linked.is_empty() {
        return;
    }
    let dimension = game.native_dimension();
    for actor in game
        .native_server_players()
        .into_iter()
        .filter(|p| p.dimension == dimension)
    {
        let Some(bound) = linked.get(&actor.uuid) else {
            continue;
        };
        let mut links_changed = false;
        for &(slot, compartment) in bound {
            let Some(filter) = create_toolbox::saved_filter(&entity.nbt, compartment) else {
                set_link(actor.uuid, slot, None);
                links_changed = true;
                continue;
            };
            if distance(actor.position, pos) >= RANGE_SQUARED {
                continue;
            }
            let previous = inventory(game, actor.uuid, slot);
            if previous
                .as_ref()
                .is_some_and(|item| !create_toolbox::compatible(game.items(), &filter, item))
            {
                set_link(actor.uuid, slot, None);
                links_changed = true;
                continue;
            }
            let count = previous.as_ref().map_or(0, |s| s.count);
            let target = max_stack(game.items(), &filter).div_ceil(2);
            if count == target {
                continue;
            }
            let mut slots = entity.items.clone();
            slots.resize(SLOTS, None);
            let selected = group(&mut slots, compartment);
            let player_new = if count < target {
                let Some(pulled) = take(selected, target - count) else {
                    continue;
                };
                let count = count + pulled.count;
                Some(ItemStack {
                    count,
                    ..previous.clone().unwrap_or(pulled)
                })
            } else {
                let mut surplus = previous.clone().expect("a nonempty hotbar stack");
                surplus.count = count - target;
                let requested = surplus.count;
                add(game.items(), selected, &mut surplus);
                if surplus.count == requested {
                    continue;
                }
                Some(ItemStack {
                    count: target + surplus.count,
                    ..surplus
                })
            };
            if is_open(game, actor.uuid, pos) {
                set_link(actor.uuid, slot, None);
                links_changed = true;
                if count < target
                    && let Some(mut remainder) = previous.clone()
                {
                    slots.clone_from(&entity.items);
                    slots.resize(SLOTS, None);
                    add(game.items(), group(&mut slots, compartment), &mut remainder);
                    if remainder.count != count
                        && set_inventory(
                            game,
                            actor.uuid,
                            slot,
                            previous.as_ref(),
                            (remainder.count > 0).then_some(remainder),
                        )
                    {
                        entity.items = slots;
                    }
                }
                continue;
            }
            create_toolbox::settle(game.items(), selected);
            if set_inventory(game, actor.uuid, slot, previous.as_ref(), player_new) {
                entity.items = slots;
            }
        }
        if links_changed {
            send_links(game, &actor, false);
        }
    }
}

fn nearby(game: &Game<'_>, actor: &NativeServerPlayer) -> Vec<ToolboxChoice> {
    let mut choices = game
        .world
        .block_entities
        .iter()
        .filter_map(|(&(x, y, z), entity)| {
            let crate::containers::BlockEntity::Mod(entity) = entity else {
                return None;
            };
            let pos = [x, y, z];
            let away = distance(actor.position, pos);
            if entity.id != create_toolbox::ENTITY || away >= RANGE_SQUARED {
                return None;
            }
            let Some(Tag::IntArray(uuid)) = entity.nbt.get(&"UniqueId".into()) else {
                return None;
            };
            let item = game.native_block(pos);
            let title = entity
                .nbt
                .get(&"CustomName".into())
                .map(horizon_client::component::name_text)
                .unwrap_or_else(|| {
                    Text::translate(&format!("block.{}", item.replace(':', ".")), &[])
                })
                .plain();
            let compartments = std::array::from_fn(|compartment| {
                let filter = create_toolbox::saved_filter(&entity.nbt, compartment)?;
                let count = entity
                    .items
                    .iter()
                    .skip(compartment * STACKS_PER_COMPARTMENT)
                    .take(STACKS_PER_COMPARTMENT)
                    .flatten()
                    .map(|stack| stack.count)
                    .sum();
                Some((filter.item.to_string(), count))
            });
            Some((
                away,
                uuid.clone(),
                ToolboxChoice {
                    pos,
                    item,
                    title,
                    compartments,
                },
            ))
        })
        .collect::<Vec<_>>();
    choices.sort_by(|left, right| left.0.total_cmp(&right.0));
    choices.truncate(8);
    choices.sort_by(|left, right| left.1.cmp(&right.1));
    choices.into_iter().map(|(_, _, choice)| choice).collect()
}

fn send_links(game: &mut Game<'_>, actor: &NativeServerPlayer, browse: bool) {
    let selected = usize::from(actor.selected_slot);
    let links = hotbar(actor.uuid);
    let reply = Reply {
        selected,
        links,
        link: links.get(selected).copied().flatten(),
        boxes: if browse {
            nearby(game, actor)
        } else {
            Vec::new()
        },
        browse,
    };
    if let Ok(data) = serde_json::to_vec(&reply) {
        let _ = game.native_net_send_to_player(actor.uuid, CHANNEL, &data);
    }
}

pub(super) fn login(game: &mut Game<'_>, player: u128) {
    if let Some(actor) = game
        .native_server_players()
        .into_iter()
        .find(|actor| actor.uuid == player)
    {
        send_links(game, &actor, false);
    }
}

pub(super) fn before_pickup(game: &mut Game<'_>, pos: [i32; 3]) {
    let mut actors = game.native_attack_players();
    if let Some(actor) = game.native_acting_player() {
        actors.push(actor);
    }
    for actor in actors {
        if actor.dimension != game.native_dimension() {
            continue;
        }
        let mut changed = false;
        for (slot, link) in hotbar(actor.uuid).into_iter().enumerate() {
            if link.is_some_and(|link| link.pos == pos) {
                disassemble_link(game, &actor, slot, false);
                changed = true;
            }
        }
        if changed {
            send_links(game, &actor, false);
        }
    }
}

pub(super) fn before_deposit(game: &mut Game<'_>, pos: [i32; 3]) {
    let Some(actor) = game.native_acting_player() else {
        return;
    };
    let mut changed = false;
    for (slot, link) in hotbar(actor.uuid).into_iter().enumerate() {
        if link.is_some_and(|link| link.pos == pos) {
            set_link(actor.uuid, slot, None);
            changed = true;
        }
    }
    if changed {
        send_links(game, &actor, false);
    }
}

pub(super) fn receive(game: &mut Game<'_>, player: u128, channel: &str, data: &[u8]) {
    if channel != CHANNEL {
        return;
    }
    let Ok(request) = serde_json::from_slice::<Request>(data) else {
        return;
    };
    let Some(actor) = game.native_server_players().into_iter().find(|actor| {
        actor.uuid == player && actor.dimension == game.native_dimension() && actor.game_mode != 3
    }) else {
        return;
    };
    match request {
        Request::Browse => {}
        Request::Deposit { ref positions } if positions.len() <= 8 => {
            for &pos in positions {
                deposit_to(game, &actor, pos);
            }
        }
        Request::Unequip { slot } if slot < HOTBAR => disassemble_link(game, &actor, slot, false),
        Request::Equip { slot, link }
            if slot < HOTBAR
                && link.compartment < COMPARTMENTS
                && distance(actor.position, link.pos) <= RANGE_SQUARED
                && mod_entity(game, link.pos)
                    .is_some_and(|entity| entity.id == create_toolbox::ENTITY) =>
        {
            disassemble_link(game, &actor, slot, false);
            relocate(game, &actor, link, slot);
            for (other, previous) in hotbar(player).into_iter().enumerate() {
                if previous == Some(link) {
                    disassemble_link(game, &actor, other, false);
                }
            }
            set_link(player, slot, Some(link));
        }
        _ => return,
    }
    send_links(game, &actor, matches!(request, Request::Browse));
}
