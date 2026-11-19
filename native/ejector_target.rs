use std::cell::RefCell;
use std::collections::BTreeMap;

use horizon_client::text::Text;
use horizon_world::nbt::Tag;

use crate::items::ItemStack;

use super::Game;
use super::create_ejector::EJECTOR;

const PREVIEW_CHANNEL: &str = "create:ejector_target_preview";

#[derive(Clone, serde::Serialize, serde::Deserialize)]
struct Selection {
    pos: [i32; 3],
    dimension: String,
    slot: usize,
}

thread_local! {
    static SELECTIONS: RefCell<BTreeMap<([i32; 4], String), Selection>> =
        const { RefCell::new(BTreeMap::new()) };
    static CLIENT_SELECTION: RefCell<Option<(String, Selection)>> = const { RefCell::new(None) };
}

fn actor(game: &mut Game<'_>) -> ([i32; 4], String) {
    (game.acting_player_uuid(), game.level.name.clone())
}

fn local_preview(game: &Game<'_>, selection: Option<Selection>) {
    CLIENT_SELECTION.with_borrow_mut(|current| {
        *current = selection.map(|selection| (game.level.name.clone(), selection));
    });
}

fn publish_preview(game: &mut Game<'_>, selection: Option<Selection>) {
    if let Some(player) = game.native_acting_player() {
        if let Ok(data) = serde_json::to_vec(&selection) {
            let _ = game.native_net_send_to_player(player.uuid, PREVIEW_CHANNEL, &data);
        }
    } else {
        local_preview(game, selection);
    }
}

pub(super) fn receive_preview(game: &Game<'_>, channel: &str, data: &[u8]) {
    if channel == PREVIEW_CHANNEL && data.len() <= 256
        && let Ok(selection) = serde_json::from_slice::<Option<Selection>>(data)
    {
        local_preview(game, selection);
    }
}

fn preview_valid(game: &Game<'_>, (world, selection): &(String, Selection)) -> bool {
    game.title.is_none()
        && game.player.is_some()
        && game.level.name == *world
        && selection.dimension == game.native_dimension()
        && selection.slot == game.selected
        && game.stack_in(game.selected).is_some_and(|stack| stack.item.as_ref() == EJECTOR)
}

pub(super) fn clear_preview() {
    CLIENT_SELECTION.with_borrow_mut(|selection| *selection = None);
}

pub(super) fn client_tick(game: &Game<'_>) {
    CLIENT_SELECTION.with_borrow_mut(|selection| {
        if selection.as_ref().is_some_and(|preview| !preview_valid(game, preview)) {
            *selection = None;
        }
    });
}

pub(super) fn preview_target(game: &Game<'_>) -> Option<[i32; 3]> {
    CLIENT_SELECTION.with_borrow(|selection| {
        selection.as_ref().filter(|preview| preview_valid(game, preview)).map(|(_, selection)| selection.pos)
    })
}

pub(super) fn tick(game: &mut Game<'_>) {
    if SELECTIONS.with_borrow(BTreeMap::is_empty) {
        return;
    }
    let key = actor(game);
    SELECTIONS.with_borrow_mut(|selections| {
        if selections.get(&key).is_some_and(|selection| {
            selection.dimension != game.native_dimension()
                || selection.slot != game.selected
                || game.inventory[game.selected]
                    .as_ref()
                    .is_none_or(|stack| stack.item.as_ref() != EJECTOR)
        }) {
            selections.remove(&key);
        }
    });
}

pub(super) fn logged_out(player: u128) {
    let player = horizon_client::lan::playerdata::uuid_ints(player);
    SELECTIONS.with_borrow_mut(|selections| selections.retain(|(owner, _), _| *owner != player));
}

fn selecting(game: &Game<'_>) -> bool {
    game.native_authoritative()
        && game.hand == super::Hand::Main
        && game.native_sneaking()
        && game
            .held()
            .is_some_and(|stack| stack.item.as_ref() == EJECTOR)
}

pub(super) fn select(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if !selecting(game) {
        return false;
    }
    let key = actor(game);
    let selection = Selection {
        pos,
        dimension: game.native_dimension().to_owned(),
        slot: game.selected,
    };
    publish_preview(game, Some(selection.clone()));
    SELECTIONS.with_borrow_mut(|selections| selections.insert(key, selection));
    game.send_overlay_message(
        Text::translate("create.weighted_ejector.target_set", &[]).with_color(0xffaa00),
    );
    true
}

pub(super) fn deselect(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    let holding = game.inventory[game.selected]
        .as_ref()
        .is_some_and(|stack| stack.item.as_ref() == EJECTOR);
    if !game.native_authoritative() || !game.native_sneaking() || !holding {
        return false;
    }
    let key = actor(game);
    let canceled = SELECTIONS.with_borrow_mut(|selections| {
        let selected = selections.get(&key).is_some_and(|selection| {
            selection.pos == pos
                && selection.dimension == game.native_dimension()
                && selection.slot == game.selected
        });
        if selected {
            selections.remove(&key);
        }
        selected
    });
    if canceled {
        publish_preview(game, None);
    }
    canceled
}

pub(super) fn place(game: &mut Game<'_>, pos: [i32; 3], stack: &ItemStack) {
    if stack.item.as_ref() != EJECTOR
        || !game.native_authoritative()
        || game.native_block(pos) != EJECTOR
    {
        return;
    }
    let key = actor(game);
    let marked = SELECTIONS.with_borrow_mut(|selections| selections.remove(&key));
    publish_preview(game, None);
    let Some(marked) = marked.filter(|marked| {
        marked.dimension == game.native_dimension() && marked.slot == game.selected
    }) else {
        game.send_overlay_message(Text::translate("create.weighted_ejector.no_target", &[]));
        return;
    };
    let [x, y, z] = std::array::from_fn(|axis| marked.pos[axis] - pos[axis]);
    let facing = match (x, z) {
        (1..=32, 0) => Some("east"),
        (-32..=-1, 0) => Some("west"),
        (0, 1..=32) => Some("south"),
        (0, -32..=-1) => Some("north"),
        _ => None,
    };
    let Some(facing) = facing else {
        game.send_overlay_message(Text::translate(
            "create.weighted_ejector.target_not_valid",
            &[],
        ));
        return;
    };
    game.native_with_mod_block_entity(pos, |entity| {
        entity
            .nbt
            .insert("HorizontalDistance".into(), Tag::Int((x + z).abs()));
        entity.nbt.insert("VerticalDistance".into(), Tag::Int(y));
    });
    game.native_set_block_property(pos, "facing", facing);
    game.native_block_entity_sync(pos);
    let target = marked
        .pos
        .map(|coordinate| Text::literal(coordinate.to_string()));
    game.send_overlay_message(
        Text::translate("create.weighted_ejector.targeting", &target).with_color(0x55ff55),
    );
}
