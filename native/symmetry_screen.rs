use std::cell::{Cell, RefCell};
use std::collections::HashMap;

use horizon_client::first_person::Hand;
use horizon_client::hud::HudBatch;
use horizon_client::mod_api::NativeScreenView;
use horizon_world::nbt::Tag;
use serde::{Deserialize, Serialize};

use super::{Game, commands::Target};
use crate::items::ItemStack;

const ITEM: &str = "create:wand_of_symmetry";
const CHANNEL: &str = "create:symmetry_screen";
const BACKGROUND: &str = "create:gui/curiosities";
const WIDGETS: &str = "create:gui/widgets";
const ICONS: &str = "create:gui/icons";
const WIDTH: f32 = 188.0;
const HEIGHT: f32 = 101.0;
const KINDS: [&str; 3] = ["plane", "cross_plane", "triple_plane"];

#[derive(Clone, Deserialize, Serialize)]
struct Settings {
    token: u64,
    kind: u8,
    orientation: u8,
}

struct Session {
    token: u64,
    slot: usize,
    main_hand: bool,
    held: ItemStack,
}

struct Editor {
    settings: Settings,
    closing: bool,
}

thread_local! {
    static SESSIONS: RefCell<HashMap<u128, Session>> = RefCell::new(HashMap::new());
    static SERIAL: Cell<u64> = const { Cell::new(0) };
    static EDITOR: RefCell<Option<Editor>> = const { RefCell::new(None) };
}

pub(super) fn open(game: &mut Game<'_>, stack: &ItemStack) -> bool {
    if stack.item.as_ref() != ITEM || !game.native_sneaking() {
        return false;
    }
    let Some(player) = game.native_acting_player() else {
        return false;
    };
    let slot = game.held_slot();
    let main_hand = game.hand == Hand::Main;
    // On-block and item use can arrive together for the same click.
    if SESSIONS.with_borrow(|sessions| {
        sessions.get(&player.uuid).is_some_and(|session| {
            session.slot == slot && session.main_hand == main_hand && &session.held == stack
        })
    }) {
        return true;
    }
    let (kind, orientation) = match game.native_component(stack, "create:symmetry_wand") {
        Ok(Some(Tag::Compound(data))) => (
            super::create_machines::string(data, "type")
                .and_then(|kind| KINDS.iter().position(|name| *name == kind))
                .unwrap_or(0) as u8,
            super::create_machines::int(data, "orientation_index")
                .unwrap_or(0)
                .clamp(0, 1) as u8,
        ),
        _ => (0, 0),
    };
    let token = SERIAL.with(|serial| {
        let next = serial.get().wrapping_add(1);
        serial.set(next);
        next
    });
    let settings = Settings {
        token,
        kind,
        orientation,
    };
    let Ok(data) = serde_json::to_vec(&settings) else {
        return false;
    };
    if game
        .native_net_send_to_player(player.uuid, CHANNEL, &data)
        .is_err()
    {
        return false;
    }
    SESSIONS.with_borrow_mut(|sessions| {
        sessions.insert(
            player.uuid,
            Session {
                token,
                slot,
                main_hand,
                held: stack.clone(),
            },
        )
    });
    true
}

pub(super) fn receive(game: &mut Game<'_>, channel: &str, data: &[u8]) {
    if channel != CHANNEL || data.len() > 256 || game.native_mod_screen() == Some(CHANNEL) {
        return;
    }
    let Ok(settings) = serde_json::from_slice::<Settings>(data) else {
        return;
    };
    if valid(&settings) && game.native_mod_screen_open(CHANNEL) {
        EDITOR.with_borrow_mut(|editor| {
            *editor = Some(Editor {
                settings,
                closing: false,
            })
        });
    }
}

fn valid(settings: &Settings) -> bool {
    settings.kind < 3 && settings.orientation < if settings.kind == 2 { 1 } else { 2 }
}

pub(super) fn save(game: &mut Game<'_>, player: u128, channel: &str, data: &[u8]) {
    if channel != CHANNEL || data.len() > 256 {
        return;
    }
    let Ok(settings) = serde_json::from_slice::<Settings>(data) else {
        return;
    };
    if !valid(&settings) {
        return;
    }
    let session = SESSIONS.with_borrow_mut(|sessions| {
        if sessions.get(&player)?.token != settings.token {
            return None;
        }
        sessions.remove(&player)
    });
    let Some(session) = session else { return };
    let Some(conn) = game.native_conn(player) else {
        return;
    };
    game.for_player(Target::Guest(conn), |actor| {
        if (session.main_hand && actor.selected != session.slot)
            || actor.stack_in(session.slot) != Some(&session.held)
        {
            return;
        }
        let mut held = session.held;
        let mut mirror = match actor.native_component(&held, "create:symmetry_wand") {
            Ok(Some(Tag::Compound(data))) => data.clone(),
            _ => horizon_world::nbt::Compound::from([
                ("position".into(), Tag::List(vec![Tag::Double(0); 3])),
                ("enable".into(), Tag::Byte(1)),
            ]),
        };
        mirror.insert(
            "type".into(),
            Tag::String(KINDS[settings.kind as usize].into()),
        );
        mirror.insert(
            "orientation_index".into(),
            Tag::Int(i32::from(settings.orientation)),
        );
        if actor
            .native_set_component(&mut held, "create:symmetry_wand", Tag::Compound(mirror))
            .is_err()
        {
            return;
        }
        *actor.stack_in_mut(session.slot) = Some(held);
    });
}

fn origin([x, y, w, h]: [f32; 4]) -> [f32; 2] {
    [
        x + ((w - WIDTH) / 2.0).floor() - 10.0,
        y + ((h - HEIGHT) / 2.0).floor(),
    ]
}

fn contains([x, y, w, h]: [f32; 4], [mx, my]: [f32; 2]) -> bool {
    mx >= x && mx < x + w && my >= y && my < y + h
}

fn selector([x, y]: [f32; 2], row: usize) -> [f32; 4] {
    [x + 45.0, y + 21.0 + row as f32 * 22.0, 109.0, 18.0]
}

fn confirm([x, y]: [f32; 2]) -> [f32; 4] {
    [x + WIDTH - 33.0, y + HEIGHT - 24.0, 18.0, 18.0]
}

pub(super) fn draw(game: &Game<'_>, screen: &NativeScreenView<'_>, out: &mut HudBatch) {
    if game.native_mod_screen() != Some(CHANNEL) {
        return;
    }
    EDITOR.with_borrow(|editor| {
        let Some(editor) = editor else { return };
        let [x, y] = origin(screen.rect);
        // The original wand panel occupies the lower part of curiosities.png.
        game.native_sprite(
            out,
            BACKGROUND,
            [0.0, 131.0, WIDTH, HEIGHT],
            [x, y, WIDTH, HEIGHT],
        );
        let title = game.translate("item.create.wand_of_symmetry", "Wand of Symmetry");
        game.native_text(
            out,
            &title,
            [x + (WIDTH - game.native_text_width(&title)) / 2.0, y + 4.0],
            0x592424,
            false,
        );
        let kind = editor.settings.kind;
        let orientation = editor.settings.orientation;
        let mode = ["Single Plane", "Double Plane", "Triple Plane"][kind as usize];
        let align = match (kind, orientation) {
            (0, 0) => "XY",
            (0, _) => "YZ",
            (1, 0) => "Orthogonal",
            (1, _) => "Diagonal",
            _ => "Horizontal",
        };
        for (row, label) in [
            format!("Mirror Type: {mode}"),
            format!("Orientation: {align}"),
        ]
        .iter()
        .enumerate()
        {
            let area = selector([x, y], row);
            game.native_text(
                out,
                if row == 0 { mode } else { align },
                [area[0] + 6.0, area[1] + 6.0],
                0xffffff,
                true,
            );
            horizon_client::widgets::record(label, area, true);
        }
        let area = confirm([x, y]);
        game.native_sprite(out, WIDGETS, [0.0, 0.0, 18.0, 18.0], area);
        game.native_sprite(
            out,
            ICONS,
            [0.0, 16.0, 16.0, 16.0],
            [area[0] + 1.0, area[1] + 1.0, 16.0, 16.0],
        );
        horizon_client::widgets::record("Confirm", area, true);
        game.native_item(out, ITEM, [x + 8.0, y + 28.0], 28.0);
    });
}

fn change(settings: &mut Settings, row: usize, delta: i32) {
    if row == 0 {
        settings.kind = (i32::from(settings.kind) + delta).clamp(0, 2) as u8;
        settings.orientation = 0;
    } else {
        settings.orientation = (i32::from(settings.orientation) + delta)
            .clamp(0, if settings.kind == 2 { 0 } else { 1 }) as u8;
    }
}

pub(super) fn mouse(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    button: i32,
    canceled: &mut bool,
) {
    if *canceled || game.native_mod_screen() != Some(CHANNEL) || button != 0 {
        return;
    }
    let origin = origin(screen.rect);
    EDITOR.with_borrow_mut(|editor| {
        let Some(editor) = editor else { return };
        if contains(confirm(origin), screen.mouse) {
            editor.closing = true;
            *canceled = true;
        }
    });
}

pub(super) fn scroll(
    game: &Game<'_>,
    mouse: [f32; 2],
    scroll: [f64; 2],
    _modifiers: u32,
    canceled: &mut bool,
) {
    if *canceled || game.native_mod_screen() != Some(CHANNEL) || scroll[1] == 0.0 {
        return;
    }
    let Some(renderer) = game.renderer.as_ref() else {
        return;
    };
    let batch = HudBatch::new([renderer.config.width, renderer.config.height]);
    let origin = origin([0.0, 0.0, batch.width, batch.height]);
    EDITOR.with_borrow_mut(|editor| {
        let Some(editor) = editor else { return };
        for row in 0..2 {
            if contains(selector(origin, row), mouse) {
                change(&mut editor.settings, row, scroll[1].signum() as i32);
                *canceled = true;
            }
        }
    });
}

pub(super) fn tick(game: &mut Game<'_>) {
    let closed = EDITOR.with_borrow_mut(|editor| {
        if game.native_mod_screen() != Some(CHANNEL)
            || editor.as_ref().is_some_and(|editor| editor.closing)
        {
            editor.take()
        } else {
            None
        }
    });
    if let Some(editor) = closed {
        if let Ok(data) = serde_json::to_vec(&editor.settings) {
            let _ = game.native_net_send_to_server(CHANNEL, &data);
        }
        game.native_mod_screen_close(CHANNEL);
    }
}
