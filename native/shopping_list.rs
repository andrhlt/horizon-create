use horizon_client::{first_person::Hand, text::Text};
use crate::items::ItemStack;
use super::Game;

const ITEM: &str = "create:shopping_list";

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
