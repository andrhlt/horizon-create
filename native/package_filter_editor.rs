use std::cell::{Cell, RefCell};
use std::collections::HashMap;

use horizon_client::first_person::Hand;
use horizon_client::hud::HudBatch;
use horizon_client::menu::Input;
use horizon_client::mod_api::NativeScreenView;
use horizon_client::ui::EditBox;
use horizon_world::nbt::Tag;

use crate::items::ItemStack;

use super::{Game, Screen, commands::Target};

const ITEM: &str = "create:package_filter";
const COMPONENT: &str = "create:package_address";
const SCREEN: &str = "create:package_filter_editor";
const CHANNEL: &str = "create:package_filter_editor";
const BACKGROUND: &str = "create:gui/filters_2";
const INVENTORY: &str = "create:gui/player_inventory";
const ICONS: &str = "create:gui/icons";
const BUTTONS: &str = "create:gui/widgets";
const SIZE: [f32; 2] = [218.0, 191.0];
const FIELD: [f32; 4] = [44.0, 28.0, 129.0, 9.0];
const RESET: [f32; 4] = [156.0, 55.0, 18.0, 18.0];
const CONFIRM: [f32; 4] = [185.0, 55.0, 18.0, 18.0];
const MAX_ADDRESS: usize = 25;

struct EditSession {
    token: u64,
    held: ItemStack,
    slot: usize,
}

struct Editor {
    token: u64,
    address: EditBox,
    closing: bool,
    clicks: Vec<(Option<usize>, i32, Input)>,
}

thread_local! {
    static EDITS: RefCell<HashMap<u128, EditSession>> = RefCell::new(HashMap::new());
    static SERIAL: Cell<u64> = const { Cell::new(0) };
    static EDITOR: RefCell<Option<Editor>> = const { RefCell::new(None) };
}

pub(super) fn register(types: &mut Vec<String>) {
    types.push(COMPONENT.into());
}

fn address(game: &Game<'_>, stack: &ItemStack) -> Option<String> {
    match game.native_component(stack, COMPONENT).ok()? {
        Some(Tag::String(value)) => value.to_string().ok(),
        None => Some(String::new()),
        _ => None,
    }
}

fn packet(token: u64, address: &str) -> Vec<u8> {
    let mut packet = Vec::with_capacity(8 + address.len());
    packet.extend_from_slice(&token.to_be_bytes());
    packet.extend_from_slice(address.as_bytes());
    packet
}

fn contents(data: &[u8]) -> Option<(u64, &str)> {
    let token = u64::from_be_bytes(data.get(..8)?.try_into().ok()?);
    let address = std::str::from_utf8(data.get(8..)?).ok()?;
    Some((token, address))
}

pub(super) fn open(game: &mut Game<'_>, stack: &ItemStack, claimed: &mut bool) {
    if *claimed || stack.item.as_ref() != ITEM || game.hand != Hand::Main || game.native_sneaking()
    {
        return;
    }
    let Some(player) = game.native_acting_player() else {
        return;
    };
    let Some(address) = address(game, stack) else {
        return;
    };
    let token = SERIAL.with(|serial| {
        let token = serial.get().wrapping_add(1);
        serial.set(token);
        token
    });
    if game
        .native_net_send_to_player(player.uuid, CHANNEL, &packet(token, &address))
        .is_ok()
    {
        let session = EditSession {
            token,
            held: stack.clone(),
            slot: game.selected,
        };
        EDITS.with_borrow_mut(|edits| edits.insert(player.uuid, session));
        *claimed = true;
    }
}

pub(super) fn receive(game: &mut Game<'_>, channel: &str, data: &[u8]) {
    if channel != CHANNEL || game.native_mod_screen() == Some(SCREEN) {
        return;
    }
    let Some((token, value)) = contents(data) else {
        return;
    };
    if !game.native_mod_screen_open(SCREEN) {
        return;
    }
    let mut address = EditBox::new(FIELD[0], FIELD[1], FIELD[2], FIELD[3]);
    address.bordered = false;
    address.max_length = MAX_ADDRESS;
    address.text_color = 0xffffffff;
    address.set_value(value);
    EDITOR.replace(Some(Editor {
        token,
        address,
        closing: false,
        clicks: Vec::new(),
    }));
}

fn is_blank(address: &str) -> bool {
    address
        .chars()
        .all(|c| c.is_whitespace() && !matches!(c, '\u{85}' | '\u{a0}' | '\u{2007}' | '\u{202f}'))
}

pub(super) fn save(game: &mut Game<'_>, player: u128, channel: &str, data: &[u8]) {
    if channel != CHANNEL || data.len() > 108 {
        return;
    }
    let Some((token, address)) = contents(data) else {
        return;
    };
    if address.encode_utf16().count() > MAX_ADDRESS || address.chars().any(char::is_control) {
        return;
    }
    let session = EDITS.with_borrow_mut(|edits| {
        if edits.get(&player)?.token != token {
            return None;
        }
        edits.remove(&player)
    });
    let Some(session) = session else { return };
    let Some(conn) = game.native_conn(player) else {
        return;
    };
    game.for_player(Target::Guest(conn), |actor| {
        if actor.selected != session.slot || actor.stack_in(session.slot) != Some(&session.held) {
            return;
        }
        let mut stack = session.held;
        let changed = if is_blank(address) {
            actor.native_remove_component(&mut stack, COMPONENT)
        } else {
            actor.native_set_component(&mut stack, COMPONENT, Tag::String(address.into()))
        };
        if changed.is_ok() {
            *actor.stack_in_mut(session.slot) = Some(stack);
        }
    });
}

fn origin([x, y, w, h]: [f32; 4]) -> [f32; 2] {
    [
        x + ((w - SIZE[0]) / 2.0).floor() - 11.0,
        y + ((h - SIZE[1]) / 2.0).floor() + 7.0,
    ]
}

pub(super) fn contains([x, y, w, h]: [f32; 4], point: [f32; 2]) -> bool {
    point[0] >= x && point[0] < x + w && point[1] >= y && point[1] < y + h
}

fn slot_rect(index: usize) -> [f32; 4] {
    let column = index % 9;
    let row = if index < 9 {
        58.0
    } else {
        ((index / 9 - 1) * 18) as f32
    };
    [40.0 + column as f32 * 18.0, 101.0 + row, 16.0, 16.0]
}

pub(super) fn draw(game: &Game<'_>, screen: &NativeScreenView<'_>, batch: &mut HudBatch) {
    if game.native_mod_screen() != Some(SCREEN) {
        return;
    }
    let [left, top] = origin(screen.rect);
    game.native_sprite(
        batch,
        BACKGROUND,
        [0.0, 0.0, 218.0, 79.0],
        [left, top, 218.0, 79.0],
    );
    game.native_sprite(
        batch,
        INVENTORY,
        [0.0, 0.0, 176.0, 108.0],
        [left + 32.0, top + 83.0, 176.0, 108.0],
    );
    let title = game.translate("item.create.package_filter", "Package Filter");
    game.native_text(
        batch,
        &title,
        [
            left + 105.0 - game.native_text_width(&title) * 0.5,
            top + 4.0,
        ],
        0x3d3c48,
        false,
    );
    game.native_item_model(
        batch,
        ITEM,
        "create:cardboard_package_12x12",
        [left + 16.0, top + 23.0],
        16.0,
    );
    game.native_item(batch, ITEM, [left + 226.0, top + 27.0], 64.0);
    for (bounds, source) in [
        (RESET, [16.0, 0.0, 16.0, 16.0]),
        (CONFIRM, [0.0, 16.0, 16.0, 16.0]),
    ] {
        let [x, y, w, h] = bounds;
        let button = [left + x, top + y, w, h];
        let u = if contains(button, screen.mouse) {
            18.0
        } else {
            0.0
        };
        game.native_sprite(batch, BUTTONS, [u, 0.0, w, h], button);
        game.native_sprite(
            batch,
            ICONS,
            source,
            [left + bounds[0] + 1.0, top + bounds[1] + 1.0, 16.0, 16.0],
        );
    }
    for index in 0..36 {
        if let Some(stack) = game.stack_in(index) {
            let [sx, sy, _, _] = slot_rect(index);
            game.native_gui_draw_item(batch, stack, [left + sx, top + sy]);
        }
    }
    if let Some(stack) = &game.carried {
        game.native_gui_draw_item(batch, stack, [screen.mouse[0] - 8.0, screen.mouse[1] - 8.0]);
    }
    EDITOR.with_borrow_mut(|state| {
        if let Some(editor) = state {
            editor.address.x = left + FIELD[0];
            editor.address.y = top + FIELD[1];
            editor.address.draw(batch, &game.gui.atlas, None);
        }
    });
}

pub(super) fn mouse(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    button: i32,
    modifiers: u32,
    canceled: &mut bool,
) {
    if *canceled || game.native_mod_screen() != Some(SCREEN) {
        return;
    }
    let [left, top] = origin(screen.rect);
    let at = [screen.mouse[0] - left, screen.mouse[1] - top];
    EDITOR.with_borrow_mut(|state| {
        let Some(editor) = state else {
            return;
        };
        *canceled = true;
        if contains(FIELD, at) {
            if button == 1 {
                editor.address.set_value("");
            } else if button == 0 {
                if editor.address.focused {
                    editor.address.click(
                        &game.gui.atlas,
                        screen.mouse[0],
                        modifiers & 1 != 0,
                        false,
                    );
                } else {
                    editor.address.move_cursor_to_end(false);
                    editor.address.highlight = 0;
                }
                editor.address.focused = true;
            }
            return;
        }
        if button == 0 && contains(CONFIRM, at) {
            editor.closing = true;
        } else if button == 0 && contains(RESET, at) {
            editor.address.set_value("");
            editor.address.focused = true;
        } else if button == 0 || button == 1 {
            editor.address.focused = false;
            let picked = (0..36).find(|&index| contains(slot_rect(index), at));
            if let Some(slot) = picked.filter(|&slot| slot != game.selected) {
                editor.clicks.push((Some(slot), button, Input::Pickup));
            }
        }
    });
}

pub(super) fn character(game: &Game<'_>, c: char, canceled: &mut bool) {
    if *canceled || game.native_mod_screen() != Some(SCREEN) {
        return;
    }
    EDITOR.with_borrow_mut(|state| {
        if let Some(editor) = state.as_mut().filter(|editor| editor.address.focused) {
            editor.address.insert_text(&c.to_string());
            *canceled = true;
        }
    });
}

pub(super) fn key(game: &Game<'_>, key: &str, modifiers: u32, canceled: &mut bool) {
    if *canceled || game.native_mod_screen() != Some(SCREEN) {
        return;
    }
    EDITOR.with_borrow_mut(|state| {
        let Some(editor) = state.as_mut().filter(|editor| editor.address.focused) else {
            return;
        };
        *canceled = edit_address_key(&mut editor.address, key, modifiers);
    });
}

pub(super) fn edit_address_key(field: &mut EditBox, key: &str, modifiers: u32) -> bool {
    let shift = modifiers & 1 != 0;
    let control = modifiers & 10 != 0;
    match key {
        "key.keyboard.enter" => field.focused = false,
        "key.keyboard.a" if control => {
            field.move_cursor_to_end(false);
            field.highlight = 0;
        }
        "key.keyboard.backspace" => field.delete_chars(-1),
        "key.keyboard.delete" => field.delete_chars(1),
        "key.keyboard.home" => field.set_cursor(0, shift),
        "key.keyboard.end" => field.move_cursor_to_end(shift),
        "key.keyboard.left" => field.set_cursor(
            if control {
                field.word_position(-1)
            } else {
                field.cursor.saturating_sub(1)
            },
            shift,
        ),
        "key.keyboard.right" => field.set_cursor(
            if control {
                field.word_position(1)
            } else {
                field.cursor + 1
            },
            shift,
        ),
        _ => return false,
    }
    true
}

pub(super) fn tick(game: &mut Game<'_>) {
    let visible = game.native_mod_screen() == Some(SCREEN);
    let (closed, clicks) = EDITOR.with_borrow_mut(|state| {
        if !visible || state.as_ref().is_some_and(|editor| editor.closing) {
            return (state.take(), Vec::new());
        }
        (
            None,
            state
                .as_mut()
                .map_or_else(Vec::new, |editor| std::mem::take(&mut editor.clicks)),
        )
    });
    if !clicks.is_empty() {
        let screen = std::mem::replace(&mut game.screen, Screen::Inventory);
        game.menu_ops(&clicks);
        game.screen = screen;
    }
    if let Some(editor) = closed {
        if game.carried.is_some() {
            game.close_container();
        }
        let _ =
            game.native_net_send_to_server(CHANNEL, &packet(editor.token, &editor.address.value));
        game.native_mod_screen_close(SCREEN);
    }
}
