use std::cell::RefCell;

use horizon_client::hud::{HudBatch, rgba};
use horizon_client::keybinds;
use horizon_client::mod_api::NativeScreenView;
use horizon_client::ui::EditBox;
use horizon_world::nbt::Tag;

use super::Game;
use super::commands::Target;
use super::create_elevator_doors::{self, DoorMode};
use super::create_machines::mod_entity;
use super::create_station::STATION;

const DEFAULT: &str = "Track Station";
const CHANNEL: &str = "create:station_name";
const EDIT_ICON: &str = "create:gui/schedule_2";
const MAX_LENGTH: usize = 25;

struct Editor {
    pos: [i32; 3],
    input: EditBox,
    sent: String,
    commit: bool,
    assembly: bool,
    mode: DoorMode,
    sent_mode: DoorMode,
}

thread_local! {
    static EDITOR: RefCell<Option<Editor>> = const { RefCell::new(None) };
}

pub(super) fn extra(game: &Game<'_>, block: &str, pos: [i32; 3], data: &mut Option<Vec<u8>>) {
    if data.is_some() || block != STATION {
        return;
    }
    let name = mod_entity(game, pos)
        .and_then(|be| be.nbt.get(&"Name".into()))
        .and_then(|tag| match tag {
            Tag::String(name) => name.to_string().ok(),
            _ => None,
        })
        .unwrap_or_else(|| DEFAULT.to_owned());
    *data = serde_json::to_vec(&(name, create_elevator_doors::mode(game, pos))).ok();
}

pub(super) fn assembly_mode() {
    EDITOR.with_borrow_mut(|editor| {
        if let Some(editor) = editor.as_mut() {
            editor.assembly = true;
        }
    });
}

pub(super) fn draw(game: &Game<'_>, batch: &mut HudBatch, [left, top]: [f32; 2]) {
    let Some(pos) = game.native_screen_pos() else {
        return;
    };
    EDITOR.with_borrow_mut(|slot| {
        let (name, mode) = game
            .native_screen_extra_data()
            .and_then(|data| serde_json::from_slice::<(String, DoorMode)>(data).ok())
            .unwrap_or_else(|| (DEFAULT.to_owned(), DoorMode::All));
        if slot
            .as_ref()
            .is_none_or(|edit| edit.pos != pos || edit.assembly)
        {
            let mut input = EditBox::new(left + 23.0, top + 4.0, 180.0, 10.0);
            input.bordered = false;
            input.max_length = MAX_LENGTH;
            input.text_color = rgba(0x59, 0x24, 0x24, 255);
            input.focused = false;
            input.message = "Station Name".to_owned();
            input.set_value(&name);
            *slot = Some(Editor {
                pos,
                sent: input.value.clone(),
                input,
                commit: false,
                assembly: false,
                mode,
                sent_mode: mode,
            });
        }
        let edit = slot.as_mut().unwrap();
        let [mx, my] = game.native_cursor();
        let at = [left + 35.0, top + 102.0, 53.0, 16.0];
        if (at[0]..at[0] + at[2]).contains(&mx) && (at[1]..at[1] + at[3]).contains(&my) {
            game.native_fill(batch, at, 0x44FFFFFF);
        }
        horizon_client::widgets::record("Onboard Door Control", at, true);
        game.native_text(
            batch,
            edit.mode.label(),
            [at[0] + 4.0, at[1] + 6.0],
            0xFFFFFF,
            true,
        );
        let width = game.native_text_width(&edit.input.value);
        let x = left + 100.0 - ((width.min(edit.input.width) + 10.0) / 2.0).floor();
        edit.input.x = x;
        edit.input.y = top + 4.0;
        horizon_client::widgets::record("Station Name", [left, top, 200.0, 14.0], true);
        if edit.input.focused {
            edit.input.draw(batch, &game.gui.atlas, None);
        } else {
            game.native_text(batch, &edit.input.value, [x, top + 4.0], 0x592424, false);
            game.native_sprite(
                batch,
                EDIT_ICON,
                [0.0, 239.0, 13.0, 13.0],
                [x + width + 5.0, top + 1.0, 13.0, 13.0],
            );
        }
    });
}

pub(super) fn scroll(game: &Game<'_>, screen: &NativeScreenView<'_>, dy: f64, canceled: &mut bool) {
    if *canceled || dy == 0.0 || screen.menu != Some(STATION) {
        return;
    }
    let [left, top, _, _] = screen.rect;
    let [x, y] = screen.mouse;
    if !(left + 35.0..left + 88.0).contains(&x) || !(top + 102.0..top + 118.0).contains(&y) {
        return;
    }
    EDITOR.with_borrow_mut(|slot| {
        if let Some(edit) = slot
            .as_mut()
            .filter(|e| !e.assembly && Some(e.pos) == game.native_screen_pos())
        {
            edit.mode = edit.mode.scroll(dy);
            *canceled = true;
        }
    });
}

pub(super) fn mouse(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    button: i32,
    canceled: &mut bool,
) {
    if *canceled || button != 0 || screen.menu != Some(STATION) {
        return;
    }
    let [left, top, width, _] = screen.rect;
    let [x, y] = screen.mouse;
    let in_header = y > top && y < top + 14.0 && x > left && x < left + width;
    EDITOR.with_borrow_mut(|slot| {
        let Some(edit) = slot
            .as_mut()
            .filter(|e| !e.assembly && Some(e.pos) == game.native_screen_pos())
        else {
            return;
        };
        if in_header {
            if edit.input.focused {
                edit.input.click(&game.gui.atlas, x, false, false);
            } else {
                edit.input.focused = true;
                edit.input.move_cursor_to_end(false);
                edit.input.highlight = 0;
                edit.input.reset_blink();
            }
            *canceled = true;
        } else {
            edit.input.focused = false;
        }
    });
}

pub(super) fn key(game: &Game<'_>, key: &str, modifiers: u32, canceled: &mut bool) {
    if *canceled {
        return;
    }
    EDITOR.with_borrow_mut(|slot| {
        let Some(edit) = slot
            .as_mut()
            .filter(|e| e.input.focused && !e.assembly && Some(e.pos) == game.native_screen_pos())
        else {
            return;
        };
        use winit::keyboard::KeyCode;
        let Some(key) = keybinds::key_code(key) else {
            return;
        };
        if matches!(key, KeyCode::Enter | KeyCode::NumpadEnter) {
            edit.input.focused = false;
            edit.commit = true;
            *canceled = true;
        } else if key != KeyCode::Escape {
            let modifier = if cfg!(target_os = "macos") { 8 } else { 2 };
            let _ = edit
                .input
                .key(key, modifiers & modifier != 0, modifiers & 1 != 0);
            *canceled = true;
        }
    });
}

pub(super) fn character(game: &Game<'_>, character: char, canceled: &mut bool) {
    if *canceled || character.is_control() {
        return;
    }
    EDITOR.with_borrow_mut(|slot| {
        if let Some(edit) = slot
            .as_mut()
            .filter(|e| e.input.focused && !e.assembly && Some(e.pos) == game.native_screen_pos())
        {
            edit.input.insert_text(character.encode_utf8(&mut [0; 4]));
            *canceled = true;
        }
    });
}

pub(super) fn tick(game: &mut Game<'_>) {
    let open = game.native_screen_pos();
    let packet = EDITOR.with_borrow_mut(|slot| {
        let edit = slot.as_mut()?;
        let closing = edit.assembly || Some(edit.pos) != open;
        if !closing && !edit.commit {
            return None;
        }
        edit.commit = false;
        let data = (edit.input.value != edit.sent || closing && edit.mode != edit.sent_mode)
            .then(|| serde_json::to_vec(&(edit.pos, &edit.input.value, edit.mode)).ok())
            .flatten();
        if closing {
            slot.take();
        } else if data.is_some() {
            edit.sent.clone_from(&edit.input.value);
            edit.sent_mode = edit.mode;
        }
        data
    });
    if let Some(data) = packet {
        let _ = game.native_net_send_to_server(CHANNEL, &data);
    }
}

pub(super) fn receive(game: &mut Game<'_>, player: u128, channel: &str, data: &[u8]) {
    if channel != CHANNEL {
        return;
    }
    let Ok((pos, name, mode)) = serde_json::from_slice::<([i32; 3], String, DoorMode)>(data) else {
        return;
    };
    let blank = name.chars().all(|c| {
        matches!(c, '\u{0009}'..='\u{000d}' | '\u{001c}'..='\u{001f}'
        | ' ' | '\u{1680}' | '\u{2000}'..='\u{2006}' | '\u{2008}'..='\u{200a}'
        | '\u{2028}' | '\u{2029}' | '\u{205f}' | '\u{3000}')
    });
    let valid_name = !blank && name.encode_utf16().count() <= MAX_LENGTH;
    let Some(conn) = game.native_conn(player) else {
        return;
    };
    game.for_player(Target::Guest(conn), |actor| {
        if actor.spectator() || actor.mode_id() == 2 || actor.native_block(pos) != STATION {
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
        let changed_mode = create_elevator_doors::mode(actor, pos) != mode;
        if changed_mode {
            create_elevator_doors::write_mode(actor, pos, mode);
        }
        let changed_name = valid_name
            && actor.native_with_mod_block_entity(pos, |entity| {
                if entity.nbt.get(&"Name".into()).is_some_and(
                |tag| matches!(tag, Tag::String(name_tag) if name_tag.to_string_lossy() == name),
            ) {
                return false;
            }
                entity
                    .nbt
                    .insert("Name".into(), Tag::String(name.as_str().into()));
                true
            }) == Some(true);
        if changed_name || changed_mode {
            actor.native_block_entity_sync(pos);
        }
    });
}
