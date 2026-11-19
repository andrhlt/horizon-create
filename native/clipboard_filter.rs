use horizon_client::text::Text;
use horizon_world::nbt::{Compound, Tag};

use crate::{items::ItemStack, save::item_to_nbt};

use super::{
    Game,
    create_belt::BELT,
    create_belt_funnel,
    create_depot::{compound, encode},
    create_funnel,
    create_machines::{CHUTE, chute_exposes_filter_amount, int, mod_entity},
};

fn installed(game: &Game<'_>, pos: [i32; 3]) -> Option<ItemStack> {
    ItemStack::from_nbt(compound(&mod_entity(game, pos)?.nbt, "Filter")?)
}

fn is_filter(stack: &ItemStack) -> bool {
    matches!(
        stack.item.as_ref(),
        "create:filter" | "create:attribute_filter" | "create:package_filter"
    )
}

fn empty_stack() -> Tag {
    Tag::Compound(Compound::new())
}

fn exposes_amount(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    match game.native_block(pos).as_str() {
        CHUTE => chute_exposes_filter_amount(game, pos),
        create_funnel::BRASS => {
            game.native_block_property(pos, "extracting").as_deref() == Some("true")
        }
        create_belt_funnel::BRASS => {
            game.native_block_property(pos, "shape").as_deref() == Some("pushing")
                || mod_entity(game, [pos[0], pos[1] - 1, pos[2]])
                    .is_some_and(|entity| entity.id == BELT)
        }
        _ => false,
    }
}

pub(super) fn capture(game: &mut Game<'_>, pos: [i32; 3]) -> Option<Compound> {
    let visible = exposes_amount(game, pos);
    let entity = mod_entity(game, pos)?;
    let filter = installed(game, pos);
    let limit = filter
        .as_ref()
        .map_or(64, |stack| game.stack_max_size(stack)) as i32;
    let mut settings = Compound::from([(
        "Filter".into(),
        filter.as_ref().map_or_else(empty_stack, item_to_nbt),
    )]);
    if visible && limit > 1 {
        let amount = int(&entity.nbt, "FilterAmount")
            .filter(|amount| *amount > 0)
            .unwrap_or(limit);
        settings.insert("Value".into(), Tag::Int(amount));
        settings.insert(
            "Row".into(),
            Tag::Int(i32::from(int(&entity.nbt, "UpTo") == Some(0))),
        );
    }
    Some(settings)
}

fn consume_filter(game: &mut Game<'_>, item: &str) -> bool {
    let slots = 0..game.inventory.len();
    let preferred = slots.clone().find(|&slot| {
        game.stack_in(slot).is_some_and(|stack| {
            stack.item.as_ref() == item && item_to_nbt(stack).get("components").is_none()
        })
    });
    let Some(slot) = preferred.or_else(|| {
        slots.into_iter().find(|&slot| {
            game.stack_in(slot)
                .is_some_and(|stack| stack.item.as_ref() == item)
        })
    }) else {
        return false;
    };
    let cell = game.stack_in_mut(slot);
    if let Some(stack) = cell {
        stack.count -= 1;
        if stack.count == 0 {
            *cell = None;
        }
    }
    game.guest_inventory_resend |= game.lan_acting.is_some();
    true
}

pub(super) fn paste(game: &mut Game<'_>, pos: [i32; 3], settings: &Compound) -> bool {
    let Some(current) = capture(game, pos) else {
        return false;
    };
    let previous = installed(game, pos);
    let limit = previous
        .as_ref()
        .map_or(64, |stack| game.stack_max_size(stack)) as i32;
    let amount =
        int(&current, "Value").and_then(|_| int(settings, "Row").zip(int(settings, "Value")));
    if let Some((row, value)) = amount {
        let value = value.clamp(1, limit);
        let up_to = row == 0;
        if int(&current, "Value") != Some(value) || int(&current, "Row") != Some(row) {
            game.native_with_mod_block_entity(pos, |entity| {
                entity.nbt.insert("FilterAmount".into(), Tag::Int(value));
                entity.nbt.insert("UpTo".into(), Tag::Byte(i8::from(up_to)));
            });
            super::create_speed_controller::setting_feedback(game, pos);
            game.native_block_entity_sync(pos);
        }
    }

    let Some(tag) = compound(settings, "Filter") else {
        return amount.is_some();
    };
    let copied = ItemStack::from_nbt(tag);
    let refund = previous.filter(|stack| is_filter(stack) && !game.creative);
    if let Some(sample) = copied
        .as_ref()
        .filter(|stack| is_filter(stack) && !game.creative)
        && refund.as_ref().is_none_or(|old| old.item != sample.item)
        && !consume_filter(game, &sample.item)
    {
        if let Some(player) = game.native_acting_player() {
            let key = format!("item.{}", sample.item.replace(':', "."));
            game.native_action_bar(
                player.uuid,
                Text::translate(
                    "create.logistics.filter.requires_item_in_inventory",
                    &[Text::translate(&key, &[])],
                ),
            );
            game.native_play_sound_in_place("create:deny", player.position, 4, 1.0, 1.0);
        }
        return false;
    }
    if let Some(refund) =
        refund.filter(|old| copied.as_ref().is_none_or(|sample| sample.item != old.item))
    {
        game.give_or_drop(refund);
        game.guest_inventory_resend |= game.lan_acting.is_some();
    }
    let max = copied
        .as_ref()
        .map(|stack| game.stack_max_size(stack) as i32);
    let tag = copied.as_ref().map_or_else(empty_stack, encode);
    game.native_with_mod_block_entity(pos, |entity| {
        if int(&entity.nbt, "UpTo") == Some(0)
            && let (Some(max), Some(amount)) = (max, int(&entity.nbt, "FilterAmount"))
            && amount > max
        {
            entity.nbt.insert("FilterAmount".into(), Tag::Int(max));
        }
        entity.nbt.insert("Filter".into(), tag);
    });
    game.native_block_entity_sync(pos);
    true
}
