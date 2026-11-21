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

fn set_list_component(item: &mut ItemStack, list: Tag, address: String) {
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
    let request = request_entries(entity);
    if request.is_empty() {
        return false;
    }

    let held = game.held().cloned();
    if held
        .as_ref()
        .is_some_and(|stack| stack.item.as_ref() != ITEM)
    {
        return true;
    }
    let Some(Tag::IntArray(owner)) = entity.nbt.get(&"OwnerUUID".into()) else {
        return true;
    };
    let Ok(owner): Result<[i32; 4], _> = owner.as_slice().try_into() else {
        return true;
    };
    let Some(request_data) = entity.nbt.get(&"RequestData".into()) else {
        return true;
    };
    let Some(address) = tag(request_data, "encoded_target_address").and_then(|value| match value {
        Tag::String(s) => Some(s.clone()),
        _ => None,
    }) else {
        return true;
    };
    let Some(offset) = tag(request_data, "target_offset").and_then(|value| match value {
        Tag::IntArray(a) if a.len() == 3 => Some([a[0], a[1], a[2]]),
        _ => None,
    }) else {
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

    let mut list = held
        .as_ref()
        .and_then(|held| held.data()?.other(LIST).cloned())
        .and_then(|value| match value {
            Tag::Compound(compound) => Some(compound),
            _ => None,
        })
        .unwrap_or_else(|| {
            Compound::from([
                ("purchases".into(), Tag::List(Vec::new())),
                ("shop_owner".into(), Tag::IntArray(owner.to_vec())),
                ("shop_network".into(), Tag::IntArray(network.clone())),
            ])
        });
    let same_shop = matches!(list.get(&"shop_owner".into()), Some(Tag::IntArray(saved)) if saved == owner.as_slice())
        && matches!(list.get(&"shop_network".into()), Some(Tag::IntArray(saved)) if saved == network);
    if !same_shop {
        return true;
    }

    let mut entries = purchases(list.get(&"purchases".into()));
    if let Some(entry) = entries
        .iter_mut()
        .find(|entry| matches!(entry.get("second"), Some(Tag::IntArray(at)) if at == &pos))
    {
        if let Some(Tag::Int(count)) = entry.get_mut("first") {
            *count = count.saturating_add(1);
        }
    } else {
        entries.push(Tag::Compound(Compound::from([
            ("first".into(), Tag::Int(1)),
            ("second".into(), Tag::IntArray(pos.to_vec())),
        ])));
    }
    list.insert("purchases".into(), Tag::List(entries));
    let mut result = ItemStack::new(ITEM, 1);
    set_list_component(&mut result, Tag::Compound(list), address);
    *game.held_mut() = Some(result);
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
