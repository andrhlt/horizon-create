use std::cell::RefCell;

use horizon_client::hud::{HudBatch, rgba};
use horizon_client::keybinds;
use horizon_client::mod_api::NativeScreenView;
use horizon_client::text::Text;
use horizon_client::ui::EditBox;
use horizon_world::nbt::Tag;

use super::Game;
use super::commands::Target;
use super::create_machines::{FROGPORT, int, mod_entity, string};

const CHANNEL: &str = "create:frogport_settings";
const ATLAS: &str = "create:gui/frogport_and_mailbox";
const MAX_LENGTH: usize = 25;
const CONFIRM: f32 = 187.0;
const RECEIVE: f32 = 37.0;
const SEND_ONLY: f32 = 55.0;

struct Editor {
    pos: [i32; 3],
    address: EditBox,
    receive: bool,
    linked: bool,
    confirm: bool,
}

thread_local! {
    static EDITOR: RefCell<Option<Editor>> = const { RefCell::new(None) };
}

fn settings(game: &Game<'_>, pos: [i32; 3]) -> Option<(String, bool, bool)> {
    let entity = mod_entity(game, pos)
        .filter(|entity| matches!(entity.id.as_str(), FROGPORT | super::create_postbox::ENTITY))?;
    Some((
        string(&entity.nbt, "AddressFilter").unwrap_or_default(),
        int(&entity.nbt, "AcceptsPackages") != Some(0),
        entity.nbt.contains_key(&"Target".into()),
    ))
}

pub(super) fn extra(game: &Game<'_>, block: &str, pos: [i32; 3], data: &mut Option<Vec<u8>>) {
    if (block == FROGPORT || super::create_postbox::block(block)) && data.is_none() {
        *data = settings(game, pos).and_then(|state| serde_json::to_vec(&state).ok());
    }
}

fn label(key: &str) -> String {
    Text::translate(key, &[]).plain()
}

pub(super) fn draw(game: &Game<'_>, batch: &mut HudBatch, [x, y]: [f32; 2]) {
    let Some(pos) = game.native_screen_pos() else {
        return;
    };
    EDITOR.with_borrow_mut(|slot| {
        if slot.as_ref().is_none_or(|edit| edit.pos != pos) {
            let Some((address, receive, linked)) = game
                .native_screen_extra_data()
                .and_then(|data| serde_json::from_slice(data).ok())
                .or_else(|| settings(game, pos))
            else {
                return;
            };
            let mut input = EditBox::new(x + 23.0, y - 11.0, 200.0, 10.0);
            input.bordered = false;
            input.focused = false;
            input.max_length = MAX_LENGTH;
            input.text_color = rgba(0x3D, 0x3C, 0x48, 255);
            input.message = "Frogport Address".into();
            input.set_value(&address);
            *slot = Some(Editor {
                pos,
                address: input,
                receive,
                linked,
                confirm: false,
            });
        }
        let edit = slot.as_mut().unwrap();
        let block = game.native_block(pos);
        let fallback = label(&format!("block.{}", block.replace(':', ".")));
        let address = if !edit.address.focused && edit.address.value.is_empty() {
            &fallback
        } else {
            &edit.address.value
        };
        let width = game.native_text_width(address);
        let left = x + 110.0 - ((width.min(edit.address.width) + 10.0) / 2.0).floor();
        edit.address.x = left;
        edit.address.y = y - 11.0;
        horizon_client::widgets::record("Frogport Address", [x, y - 17.0, 214.0, 17.0], true);
        if edit.address.focused {
            edit.address.draw(batch, &game.gui.atlas, None);
        } else {
            game.native_text(batch, address, [left, y - 11.0], 0x3D3C48, false);
            game.native_sprite(
                batch,
                ATLAS,
                [230.0, 3.0, 13.0, 13.0],
                [left + width + 5.0, y - 14.0, 13.0, 13.0],
            );
        }
        let mut button = |name: &str, left: f32, icon: [f32; 2], selected: bool| {
            let rect = [x + left, y + 58.0, 18.0, 18.0];
            horizon_client::widgets::record(name, rect, true);
            let [cx, cy] = game.native_cursor();
            let hovered =
                (rect[0]..rect[0] + 18.0).contains(&cx) && (rect[1]..rect[1] + 18.0).contains(&cy);
            let background = if hovered {
                18.0
            } else if selected {
                72.0
            } else {
                0.0
            };
            game.native_sprite(
                batch,
                "create:gui/widgets",
                [background, 0.0, 18.0, 18.0],
                rect,
            );
            game.native_sprite(
                batch,
                "create:gui/icons",
                [icon[0], icon[1], 16.0, 16.0],
                [rect[0] + 1.0, rect[1] + 1.0, 16.0, 16.0],
            );
        };
        button("Confirm", CONFIRM, [0.0, 16.0], false);
        if edit.linked {
            button(
                &label("create.gui.package_port.send_and_receive"),
                RECEIVE,
                [16.0, 192.0],
                edit.receive,
            );
            button(
                &label("create.gui.package_port.send_only"),
                SEND_ONLY,
                [0.0, 192.0],
                !edit.receive,
            );
            game.native_sprite(
                batch,
                ATLAS,
                [26.0, 55.0, 18.0, 18.0],
                [x + 13.0, y + 58.0, 18.0, 18.0],
            );
            game.native_item(batch, "create:chain_conveyor", [x + 14.0, y + 59.0], 16.0);
        }
    });
}

pub(super) fn mouse(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    button: i32,
    canceled: &mut bool,
) {
    if *canceled || button != 0 || screen.menu != Some(FROGPORT) {
        return;
    }
    let [left, top, _, _] = screen.rect;
    let [x, y] = screen.mouse;
    EDITOR.with_borrow_mut(|slot| {
        let Some(edit) = slot
            .as_mut()
            .filter(|e| Some(e.pos) == game.native_screen_pos())
        else {
            return;
        };
        if (top - 17.0..top).contains(&y) && (left..left + 214.0).contains(&x) {
            if !edit.address.focused {
                edit.address.focused = true;
                edit.address.move_cursor_to_end(false);
                edit.address.reset_blink();
            } else {
                edit.address.click(&game.gui.atlas, x, false, false);
            }
            *canceled = true;
            return;
        }
        edit.address.focused = false;
        if !(58.0..76.0).contains(&(y - top)) {
            return;
        }
        let x = x - left;
        if (CONFIRM..CONFIRM + 18.0).contains(&x) {
            edit.confirm = true;
        } else if edit.linked && (RECEIVE..SEND_ONLY + 18.0).contains(&x) {
            edit.receive = x < SEND_ONLY;
        } else {
            return;
        }
        *canceled = true;
    });
}

fn edit_address(game: &Game<'_>, canceled: &mut bool, change: impl FnOnce(&mut EditBox) -> bool) {
    if *canceled {
        return;
    }
    EDITOR.with_borrow_mut(|slot| {
        if let Some(edit) = slot
            .as_mut()
            .filter(|e| e.address.focused && Some(e.pos) == game.native_screen_pos())
        {
            *canceled = change(&mut edit.address);
        }
    });
}

pub(super) fn key(game: &Game<'_>, key: &str, modifiers: u32, canceled: &mut bool) {
    use winit::keyboard::KeyCode;
    edit_address(game, canceled, |input| {
        let Some(key) = keybinds::key_code(key) else {
            return false;
        };
        match key {
            KeyCode::Enter | KeyCode::NumpadEnter => input.focused = false,
            KeyCode::Escape => return false,
            _ => {
                let control = if cfg!(target_os = "macos") { 8 } else { 2 };
                input.key(key, modifiers & control != 0, modifiers & 1 != 0);
            }
        }
        true
    });
}

pub(super) fn character(game: &Game<'_>, c: char, canceled: &mut bool) {
    edit_address(game, canceled, |input| {
        input.insert_text(c.encode_utf8(&mut [0; 4]));
        true
    });
}

pub(super) fn tick(game: &mut Game<'_>) {
    let open = game.native_screen_pos();
    let closing = EDITOR.with_borrow_mut(|slot| {
        let edit = slot.as_ref()?;
        (edit.confirm || Some(edit.pos) != open).then(|| slot.take().unwrap())
    });
    if let Some(edit) = closing {
        if edit.confirm && Some(edit.pos) == open {
            game.close_container();
            game.screen = super::Screen::Playing;
            game.capture(true);
        }
        if let Ok(packet) = serde_json::to_vec(&(edit.pos, edit.address.value, edit.receive)) {
            let _ = game.native_net_send_to_server(CHANNEL, &packet);
        }
    }
}

pub(super) fn receive(game: &mut Game<'_>, player: u128, channel: &str, data: &[u8]) {
    if channel != CHANNEL {
        return;
    }
    let Ok((pos, address, receive)) = serde_json::from_slice::<([i32; 3], String, bool)>(data)
    else {
        return;
    };
    if address.encode_utf16().count() > MAX_LENGTH {
        return;
    }
    let Some(conn) = game.native_conn(player) else {
        return;
    };
    game.for_player(Target::Guest(conn), |actor| {
        let block = actor.native_block(pos);
        if actor.spectator()
            || actor.mode_id() == 2
            || (block != FROGPORT && !super::create_postbox::block(&block))
        {
            return;
        }
        let Some(eye) = actor.eye_position() else {
            return;
        };
        let radius = actor.interaction_range("minecraft:block_interaction_range", 4.5, 5.0) + 20.0;
        let distance_sq: f64 = eye
            .into_iter()
            .zip(pos)
            .map(|(at, block)| {
                let min = f64::from(block);
                (at - at.clamp(min, min + 1.0)).powi(2)
            })
            .sum();
        if distance_sq > radius * radius {
            return;
        }
        if actor.native_with_mod_block_entity(pos, |entity| {
            if string(&entity.nbt, "AddressFilter").unwrap_or_default() == address
                && (int(&entity.nbt, "AcceptsPackages") != Some(0)) == receive
            {
                return false;
            }
            entity
                .nbt
                .insert("AddressFilter".into(), Tag::String(address.as_str().into()));
            entity
                .nbt
                .insert("AcceptsPackages".into(), Tag::Byte(i8::from(receive)));
            true
        }) == Some(true)
        {
            actor.native_block_entity_sync(pos);
        }
    });
}

pub(super) fn clear() {
    EDITOR.with_borrow_mut(|slot| *slot = None);
}
