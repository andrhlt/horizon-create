use super::Game;
use crate::items::ItemStack;
use horizon_client::{first_person::Hand, text::Text};
use horizon_world::nbt::{Compound, Tag};

const ITEM: &str = "create:shopping_list";
const LIST: &str = "create:shopping_list";
const ADDRESS: &str = "create:shopping_list_address";

fn tag<'a>(value: &'a Tag, key: &str) -> Option<&'a Tag> {
    value.get(key)
}

fn int(value: Option<&Tag>) -> Option<i32> {
    match value? {
        Tag::Int(value) => Some(*value),
        _ => None,
    }
}

fn stack(value: &Tag) -> Option<ItemStack> {
    let Tag::Compound(value) = value else {
        return None;
    };
    ItemStack::from_nbt(value)
}

fn purchases(value: Option<&Tag>) -> Vec<Tag> {
    match value {
        Some(Tag::List(items)) => items.clone(),
        _ => Vec::new(),
    }
}

fn request_entries(entity: &horizon_client::containers::ModBlockEntity) -> Vec<(ItemStack, i32)> {
    let Some(request) = entity.nbt.get(&"RequestData".into()) else {
        return Vec::new();
    };
    let Some(ordered) =
        tag(request, "encoded_request").and_then(|value| tag(value, "ordered_stacks"))
    else {
        return Vec::new();
    };
    let Some(Tag::List(entries)) = tag(ordered, "entries") else {
        return Vec::new();
    };
    entries
        .iter()
        .filter_map(|entry| {
            // PackageOrderWithCrafts uses `item_stack`; older captures used
            // `stack`, so accept both encodings while the native bridge is
            // migrated.
            let item = stack(tag(entry, "item_stack").or_else(|| tag(entry, "stack"))?)?;
            let count = int(tag(entry, "count"))?.max(0);
            (count > 0).then_some((item, count))
        })
        .collect()
}

fn request_data(nbt: &Compound) -> Option<&Tag> {
    nbt.get(&"RequestData".into())
}

fn offset(data: &Tag) -> Option<[i32; 3]> {
    match tag(data, "target_offset")? {
        Tag::IntArray(at) if at.len() == 3 => Some([at[0], at[1], at[2]]),
        Tag::List(at) if at.len() == 3 => {
            Some([int(at.first())?, int(at.get(1))?, int(at.get(2))?])
        }
        _ => None,
    }
}

fn add_total(totals: &mut Vec<(ItemStack, i32)>, item: &ItemStack, count: i32) {
    if count <= 0 {
        return;
    }
    if let Some((_, amount)) = totals
        .iter_mut()
        .find(|(previous, _)| super::create_machines::same_stack(previous, item))
    {
        *amount = amount.saturating_add(count);
    } else {
        totals.push((item.clone(), count));
    }
}

fn held_list(game: &Game<'_>, held: Option<&ItemStack>) -> Option<Compound> {
    let value = held?.data()?.other(LIST)?.clone();
    match value {
        Tag::Compound(list) => Some(list),
        _ => None,
    }
}

fn cloth_at(game: &Game<'_>, at: [i32; 3]) -> Option<Compound> {
    super::create_machines::mod_entity(game, at)
        .filter(|entity| entity.id == "create:table_cloth")
        .map(|entity| entity.nbt.clone())
}

fn purchase_rows(list: &Compound) -> Vec<([i32; 3], i32)> {
    purchases(list.get(&"purchases".into()))
        .into_iter()
        .filter_map(|entry| {
            let Tag::IntArray(at) = entry.get("second")? else {
                return None;
            };
            let [x, y, z] = <[i32; 3]>::try_from(at.as_slice()).ok()?;
            let count = int(entry.get("first"))?.max(0);
            (count > 0).then_some(([x, y, z], count))
        })
        .collect()
}

fn price(nbt: &Compound) -> Option<(ItemStack, i32)> {
    let Tag::Compound(filter) = nbt.get(&"Filter".into())? else {
        return None;
    };
    let item = ItemStack::from_nbt(filter)?;
    let amount = int(nbt.get(&"FilterAmount".into())).unwrap_or(1).max(1);
    Some((item, amount))
}

fn shop_order(game: &Game<'_>, list: &Compound) -> Option<(Vec<ItemStack>, Vec<(ItemStack, i32)>)> {
    let mut order = Vec::<ItemStack>::new();
    let mut cost = Vec::<(ItemStack, i32)>::new();
    for (at, count) in purchase_rows(list) {
        let nbt = cloth_at(game, at)?;
        let Some(Tag::IntArray(owner)) = nbt.get(&"OwnerUUID".into()) else {
            return None;
        };
        if !matches!(list.get(&"shop_owner".into()), Some(Tag::IntArray(saved)) if saved == owner) {
            return None;
        }
        let request_data = request_data(&nbt)?;
        let offset = offset(request_data)?;
        let ticker_pos = [at[0] + offset[0], at[1] + offset[1], at[2] + offset[2]];
        let ticker = super::create_machines::mod_entity(game, ticker_pos)
            .filter(|entity| entity.id == super::create_stock_ticker::TICKER)?;
        if !matches!(ticker.nbt.get(&"Freq".into()), Some(Tag::IntArray(network))
            if matches!(list.get(&"shop_network".into()), Some(Tag::IntArray(saved)) if saved == network))
        {
            return None;
        }
        let request = super::create_machines::mod_entity(game, at)
            .filter(|entity| entity.id == "create:table_cloth")
            .map(request_entries)?;
        let (money, money_count) = price(&nbt)?;
        add_total(&mut cost, &money, money_count.saturating_mul(count));
        for (item, amount) in request {
            let total = amount.saturating_mul(count);
            if let Some(existing) = order
                .iter_mut()
                .find(|existing| super::create_machines::same_stack(existing, &item))
            {
                existing.count = existing.count.saturating_add(total as u32);
            } else {
                order.push(ItemStack {
                    count: total as u32,
                    ..item
                });
            }
        }
    }
    (!order.is_empty()).then_some((order, cost))
}

fn registered_payments(nbt: &Compound) -> [Option<ItemStack>; 27] {
    let mut slots: [Option<ItemStack>; 27] = std::array::from_fn(|_| None);
    let Some(Tag::Compound(inventory)) = nbt.get(&"ReceivedPayments".into()) else {
        return slots;
    };
    let Some(Tag::List(items)) = inventory.get(&"Items".into()) else {
        return slots;
    };
    for entry in items {
        let Some(item) = ItemStack::from_nbt(match entry {
            Tag::Compound(item) => item,
            _ => continue,
        }) else {
            continue;
        };
        let slot = match entry.get("Slot") {
            Some(Tag::Byte(slot)) => usize::try_from(*slot).ok(),
            Some(Tag::Int(slot)) => usize::try_from(*slot).ok(),
            _ => None,
        };
        if let Some(slot) = slot.filter(|slot| *slot < slots.len()) {
            slots[slot] = Some(item);
        }
    }
    slots
}

fn encode_payments(slots: &[Option<ItemStack>; 27]) -> Tag {
    let items = slots
        .iter()
        .enumerate()
        .filter_map(|(slot, item)| {
            let mut item = crate::save::item_to_nbt(item.as_ref()?);
            let Tag::Compound(fields) = &mut item else {
                return None;
            };
            fields.insert("Slot".into(), Tag::Byte(slot as i8));
            Some(item)
        })
        .collect();
    Tag::Compound(Compound::from([("Items".into(), Tag::List(items))]))
}

/// Submit a completed list at its linked Stock Ticker. Payment and stock are
/// preflighted before the shared order dispatcher mutates either inventory.
pub(super) fn ticker_click(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if !game.native_authoritative()
        || game.hand != Hand::Main
        || game.native_block(pos) != super::create_stock_ticker::TICKER
    {
        return false;
    }
    let Some(held) = game
        .held()
        .cloned()
        .filter(|stack| stack.item.as_ref() == ITEM)
    else {
        return false;
    };
    let Some(list) = held_list(game, Some(&held)) else {
        return true;
    };
    let Some(Tag::IntArray(network)) = super::create_machines::mod_entity(game, pos)
        .and_then(|ticker| ticker.nbt.get(&"Freq".into()))
    else {
        return true;
    };
    let Ok(network): Result<[i32; 4], _> = network.as_slice().try_into() else {
        return true;
    };
    if !matches!(list.get(&"shop_network".into()), Some(Tag::IntArray(saved)) if saved.as_slice() == network)
    {
        return true;
    }
    let Some((order, cost)) = shop_order(game, &list) else {
        return true;
    };

    super::create_stock_network::clear_summaries();
    let stock = super::create_stock_network::summary(game, network, true);
    if order.iter().any(|requested| {
        stock
            .items
            .iter()
            .find(|item| super::create_machines::same_stack(item, requested))
            .is_none_or(|item| item.count < requested.count)
    }) {
        return true;
    }

    let Some(ticker) = super::create_machines::mod_entity(game, pos) else {
        return true;
    };
    let mut payments = registered_payments(&ticker.nbt);
    for (item, count) in &cost {
        let mut remaining = (*count).max(0) as u32;
        let max_stack = super::create_packager::max_stack(game.items(), item);
        for slot in payments.iter_mut().filter_map(Option::as_mut) {
            if super::create_machines::same_stack(slot, item) {
                let room = max_stack.saturating_sub(slot.count);
                let amount = room.min(remaining);
                slot.count += amount;
                remaining -= amount;
            }
        }
        for slot in payments.iter_mut().filter(|slot| slot.is_none()) {
            if remaining == 0 {
                break;
            }
            let amount = remaining.min(max_stack);
            *slot = Some(ItemStack {
                count: amount,
                ..item.clone()
            });
            remaining -= amount;
        }
        if remaining > 0 {
            return true;
        }
    }

    let mut player_items = game.inventory.clone();
    for (payment, count) in &cost {
        let mut remaining = (*count).max(0) as u32;
        for slot in player_items.iter_mut().take(36) {
            let Some(stack) = slot
                .as_mut()
                .filter(|stack| super::create_machines::same_stack(stack, payment))
            else {
                continue;
            };
            let amount = stack.count.min(remaining);
            stack.count -= amount;
            remaining -= amount;
            if stack.count == 0 {
                *slot = None;
            }
            if remaining == 0 {
                break;
            }
        }
        if remaining > 0 {
            return true;
        }
    }

    let address = held
        .data()
        .and_then(|data| data.other(ADDRESS))
        .and_then(|value| match value {
            Tag::String(address) => Some(address.to_string_lossy()),
            _ => None,
        })
        .unwrap_or_default();
    let context = super::create_stock_network::encode_order(order.into_iter());
    let sent = game.with_level(|_, level, ticks| {
        super::create_stock_network::request(
            level,
            ticks,
            &network,
            &context,
            &address,
            super::create_stock_network::Request::Player,
        )
    });
    if !sent {
        return true;
    }

    game.inventory = player_items;
    game.native_with_mod_block_entity(pos, |entity| {
        entity
            .nbt
            .insert("ReceivedPayments".into(), encode_payments(&payments));
        entity.nbt.insert(
            "PreviousAddress".into(),
            Tag::String(address.as_str().into()),
        );
    });
    game.native_block_entity_sync(pos);
    *game.held_mut() = None;
    game.guest_inventory_resend |= game.lan_acting.is_some();
    true
}

pub(super) fn tooltip(game: &Game<'_>, stack: &ItemStack, lines: &mut Vec<(Text, u32)>) {
    if stack.item.as_ref() != ITEM {
        return;
    }
    lines.push((Text::literal("Shopping List"), 0xffaa00ff));
    if let Some(list) = held_list(game, Some(stack))
        && let Some((order, cost)) = shop_order(game, &list)
    {
        for item in order {
            let name = game.stack_display_name(&item).plain();
            lines.push((Text::literal(format!("{name} x{}", item.count)), 0xaaaaaaff));
        }
        if !cost.is_empty() {
            lines.push((Text::literal("Total cost"), 0xffaa00ff));
            for (item, amount) in cost {
                let name = game.stack_display_name(&item).plain();
                lines.push((Text::literal(format!("{name} x{amount}")), 0xffff55ff));
            }
        }
    }
    lines.push((Text::literal("Use at a Stock Ticker to order"), 0xaaaaaaff));
    lines.push((Text::literal("Sneak-use to discard"), 0x555555ff));
}

fn set_list_component(item: &mut ItemStack, list: Tag, address: horizon_world::nbt::JavaString) {
    let data = item.data_mut();
    data.set_other(LIST, Some(list));
    data.set_other(ADDRESS, Some(Tag::String(address)));
}

/// Use a configured Table Cloth as a shop. The block entity stores the same
/// AutoRequestData and price filter written by Create's FilteringBehaviour.
pub(super) fn shop_click(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if !game.native_authoritative() || game.hand != Hand::Main {
        return false;
    }
    let Some(entity) = super::create_machines::mod_entity(game, pos)
        .filter(|entity| entity.id == "create:table_cloth")
    else {
        return false;
    };
    let nbt = entity.nbt.clone();
    let request = request_entries(entity);
    if request.is_empty() {
        return false;
    }
    if price(&nbt).is_none() {
        return true;
    }

    let held = game.held().cloned();
    let held_is_list = held
        .as_ref()
        .is_some_and(|stack| stack.item.as_ref() == ITEM);
    let inventory_list_slot = (!held_is_list)
        .then(|| {
            game.inventory.iter().take(9).position(|stack| {
                stack
                    .as_ref()
                    .is_some_and(|stack| stack.item.as_ref() == ITEM)
            })
        })
        .flatten();
    if !held_is_list && inventory_list_slot.is_none() && held.is_some() {
        return true;
    }
    let Some(Tag::IntArray(owner)) = nbt.get(&"OwnerUUID".into()) else {
        return true;
    };
    let Ok(owner): Result<[i32; 4], _> = owner.as_slice().try_into() else {
        return true;
    };
    let Some(request_data) = request_data(&nbt) else {
        return true;
    };
    let address = tag(request_data, "encoded_target_address")
        .and_then(|value| match value {
            Tag::String(s) => Some(s.clone()),
            _ => None,
        })
        .unwrap_or_default();
    let Some(offset) = offset(request_data) else {
        return true;
    };
    let ticker_pos = [pos[0] + offset[0], pos[1] + offset[1], pos[2] + offset[2]];
    let Some(ticker) = super::create_machines::mod_entity(game, ticker_pos)
        .filter(|ticker| ticker.id == super::create_stock_ticker::TICKER)
    else {
        return true;
    };
    let Some(Tag::IntArray(network)) = ticker.nbt.get(&"Freq".into()) else {
        return true;
    };
    if network.len() != 4 {
        return true;
    }

    let network: [i32; 4] = match network.as_slice().try_into() {
        Ok(network) => network,
        Err(_) => return true,
    };
    let prior_list = if held_is_list {
        held.as_ref()
    } else {
        inventory_list_slot.and_then(|slot| game.inventory.get(slot).and_then(Option::as_ref))
    };
    let mut list = held_list(game, prior_list).unwrap_or_else(|| {
        Compound::from([
            ("purchases".into(), Tag::List(Vec::new())),
            ("shop_owner".into(), Tag::IntArray(owner.to_vec())),
            ("shop_network".into(), Tag::IntArray(network.to_vec())),
        ])
    });
    let same_shop = matches!(list.get(&"shop_owner".into()), Some(Tag::IntArray(saved)) if saved == owner.as_slice())
        && matches!(list.get(&"shop_network".into()), Some(Tag::IntArray(saved)) if saved.as_slice() == network);
    if !same_shop {
        return true;
    }

    let rows = purchase_rows(&list);
    let current = rows
        .iter()
        .find(|(at, _)| *at == pos)
        .map_or(0, |(_, count)| *count);
    let mut reserved = Vec::<(ItemStack, i32)>::new();
    for (at, count) in rows.iter().filter(|(at, _)| *at != pos) {
        let Some(_) = cloth_at(game, *at) else {
            continue;
        };
        let Some(entity) = super::create_machines::mod_entity(game, *at)
            .filter(|entity| entity.id == "create:table_cloth")
        else {
            continue;
        };
        for (item, amount) in request_entries(entity) {
            add_total(&mut reserved, &item, amount.saturating_mul(*count));
        }
    }

    super::create_stock_network::clear_summaries();
    let summary = super::create_stock_network::summary(game, network, true);
    let mut stock_limit = i32::MAX;
    for (item, amount) in &request {
        let stock = summary
            .items
            .iter()
            .find(|entry| super::create_machines::same_stack(entry, item))
            .map_or(0, |entry| entry.count.min(i32::MAX as u32) as i32);
        let already_reserved = reserved
            .iter()
            .find(|(entry, _)| super::create_machines::same_stack(entry, item))
            .map_or(0, |(_, count)| *count);
        stock_limit = stock_limit.min((stock - already_reserved).max(0) / *amount);
    }
    if stock_limit == 0 || current >= stock_limit {
        return true;
    }
    let new_count = (current + 1).min(stock_limit);
    let mut entries = purchases(list.get(&"purchases".into()));
    if let Some(entry) = entries
        .iter_mut()
        .find(|entry| matches!(entry.get("second"), Some(Tag::IntArray(at)) if at == &pos))
    {
        if let Some(Tag::Int(count)) = entry.get_mut("first") {
            *count = new_count;
        }
    } else {
        entries.push(Tag::Compound(Compound::from([
            ("first".into(), Tag::Int(new_count)),
            ("second".into(), Tag::IntArray(pos.to_vec())),
        ])));
    }
    list.insert("purchases".into(), Tag::List(entries));
    let mut result = ItemStack::new(ITEM, 1);
    set_list_component(&mut result, Tag::Compound(list), address);
    if held_is_list || held.is_none() {
        *game.held_mut() = Some(result);
    } else if let Some(slot) = inventory_list_slot {
        game.inventory[slot] = Some(result);
    }
    game.guest_inventory_resend |= game.lan_acting.is_some();
    game.swing_arm();
    true
}

pub(super) fn discard(game: &mut Game<'_>, stack: &ItemStack) -> bool {
    if stack.item.as_ref() != ITEM
        || !game.native_authoritative()
        || game.hand != Hand::Main
        || !game.native_sneaking()
    {
        return false;
    }
    *game.held_mut() = None;
    game.guest_inventory_resend |= game.lan_acting.is_some();
    let player = game.native_acting_id();
    game.native_action_bar(
        player,
        Text::translate("create.table_cloth.shopping_list_discarded", &[]),
    );
    game.native_play_sound_to(
        player,
        "minecraft:item.book.page_turn",
        "player",
        None,
        1.0,
        1.0,
    );
    true
}
