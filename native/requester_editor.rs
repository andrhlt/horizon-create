use std::cell::{Cell, RefCell};
use std::collections::HashMap;

use horizon_client::{hud::HudBatch, menu::Input, mod_api::NativeScreenView, ui::EditBox};
use horizon_world::nbt::{self, Compound, Tag};

use crate::items::ItemStack;

use super::{
    Game, Screen,
    commands::Target,
    create_machines::{int, mod_entity},
    create_package_filter_editor::{contains, edit_address_key},
    create_redstone_requester::REQUESTER,
    create_stock_network,
};

const SCREEN: &str = "create:redstone_requester";
const WIDTH: f32 = 232.0;
const HEIGHT: f32 = 228.0;
const SLOTS: usize = 9;
const FIELD: [f32; 4] = [55.0, 68.0, 110.0, 10.0];
const PARTIAL: [f32; 4] = [12.0, 95.0, 18.0, 18.0];
const FULL: [f32; 4] = [30.0, 95.0, 18.0, 18.0];
const CONFIRM: [f32; 4] = [202.0, 95.0, 18.0, 18.0];
const LIMITS: nbt::Limits = nbt::Limits {
    max_bytes: 60_000,
    max_nodes: 2048,
    max_depth: 20,
};

#[derive(Clone, Default)]
struct Slots([Option<ItemStack>; SLOTS]);

impl Slots {
    fn read(order: Option<&Tag>) -> Self {
        let mut slots = Self::default();
        for (slot, item) in slots.0.iter_mut().zip(
            order
                .into_iter()
                .flat_map(create_stock_network::order_stacks),
        ) {
            *slot = Some(item);
        }
        slots
    }

    fn order(&self, counts: impl Iterator<Item = u16>) -> Tag {
        create_stock_network::encode_order(self.0.iter().flatten().zip(counts).map(
            |(item, count)| {
                let mut item = item.clone();
                item.count = u32::from(count);
                item
            },
        ))
    }

    fn view(&self) -> Tag {
        Tag::List(
            self.0
                .iter()
                .enumerate()
                .filter_map(|(index, item)| {
                    Some(Tag::compound([
                        ("slot", Tag::Int(index as i32)),
                        ("item", crate::save::item_to_nbt(item.as_ref()?)),
                    ]))
                })
                .collect(),
        )
    }

    fn from_view(view: &Tag) -> Self {
        let mut slots = Self::default();
        let Some(Tag::List(entries)) = view.get("Slots") else {
            return slots;
        };
        for entry in entries {
            if let (Some(Tag::Int(index)), Some(Tag::Compound(item))) =
                (entry.get("slot"), entry.get("item"))
                && let Some(slot) = slots.0.get_mut(*index as usize)
            {
                *slot = ItemStack::from_nbt(item);
            }
        }
        slots
    }

    fn sample(&mut self, index: usize, source: Option<&ItemStack>) {
        if let Some(slot) = self.0.get_mut(index) {
            *slot = source.cloned().map(|mut item| {
                item.count = 1;
                item
            });
        }
    }
}

struct Session {
    token: u64,
    pos: [i32; 3],
    dimension: String,
    frequency: Option<Tag>,
    slots: Slots,
}

struct Editor {
    token: u64,
    slots: Slots,
    counts: [u16; SLOTS],
    address: EditBox,
    partial: bool,
    actions: Vec<Action>,
}

enum Action {
    Inventory(usize, i32),
    QuickCopy(usize),
    Sample(usize),
    Clear(usize),
    Close,
}

thread_local! {
    static SERIAL: Cell<u64> = const { Cell::new(0) };
    static SESSIONS: RefCell<HashMap<u128, Session>> = RefCell::new(HashMap::new());
    static EDITOR: RefCell<Option<Editor>> = const { RefCell::new(None) };
}

fn packet(token: u64, action: u8, tag: &Tag) -> Option<Vec<u8>> {
    let body = nbt::write_network(tag, LIMITS).ok()?;
    let mut data = Vec::with_capacity(9 + body.len());
    data.extend_from_slice(&token.to_be_bytes());
    data.push(action);
    data.extend(body);
    Some(data)
}

fn word(data: &[u8]) -> Option<u64> {
    Some(u64::from_be_bytes(data.get(..8)?.try_into().ok()?))
}

fn body(data: &[u8]) -> Option<Tag> {
    let payload = data.get(9..)?;
    let (tag, count) = nbt::read_network(payload, LIMITS).ok()?;
    (count == payload.len()).then_some(tag)
}

pub(super) fn open(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if game.native_sneaking() || game.native_block(pos) != REQUESTER {
        return false;
    }
    let Some(player) = game.native_acting_player() else {
        return false;
    };
    if player.game_mode == 3 {
        return false;
    }
    let Some(entity) = mod_entity(game, pos) else {
        return false;
    };
    let token = SERIAL.with(|serial| {
        let token = serial.get().wrapping_add(1);
        serial.set(token);
        token
    });
    let session = Session {
        token,
        pos,
        dimension: player.dimension,
        frequency: entity.nbt.get(&"Freq".into()).cloned(),
        slots: Slots::read(entity.nbt.get(&"EncodedRequest".into())),
    };
    let view = Tag::compound([
        ("Slots", session.slots.view()),
        (
            "Address",
            entity
                .nbt
                .get(&"EncodedAddress".into())
                .cloned()
                .unwrap_or_else(|| Tag::String("".into())),
        ),
        (
            "Partial",
            Tag::Byte(i8::from(int(&entity.nbt, "AllowPartial") == Some(1))),
        ),
    ]);
    let Some(data) = packet(token, 1, &view) else {
        return false;
    };
    if game
        .native_net_send_to_player(player.uuid, SCREEN, &data)
        .is_err()
    {
        return false;
    }
    SESSIONS.with_borrow_mut(|sessions| sessions.insert(player.uuid, session));
    true
}

pub(super) fn receive(game: &mut Game<'_>, channel: &str, data: &[u8]) {
    if channel != SCREEN {
        return;
    }
    let (Some(token), Some(view), Some(&opening)) = (word(data), body(data), data.get(8)) else {
        return;
    };
    let slots = Slots::from_view(&view);
    if opening == 0 && game.native_mod_screen() == Some(SCREEN) {
        EDITOR.with_borrow_mut(|state| {
            if let Some(editor) = state.as_mut().filter(|editor| editor.token == token) {
                for (count, slot) in editor.counts.iter_mut().zip(&slots.0) {
                    if slot.is_none() {
                        *count = 1;
                    }
                }
                editor.slots = slots;
            }
        });
    } else if opening == 1 && game.native_mod_screen_open(SCREEN) {
        let mut address = EditBox::new(FIELD[0], FIELD[1], FIELD[2], FIELD[3]);
        address.bordered = false;
        address.max_length = 25;
        address.text_color = 0xff555555;
        address.set_value(&crate::save::text(view.get("Address")).unwrap_or_default());
        let counts = std::array::from_fn(|i| {
            slots.0[i]
                .as_ref()
                .map_or(1, |stack| stack.count.clamp(1, 256) as u16)
        });
        EDITOR.replace(Some(Editor {
            token,
            slots,
            counts,
            address,
            partial: view.get("Partial") == Some(&Tag::Byte(1)),
            actions: Vec::new(),
        }));
    }
}

fn valid(game: &Game<'_>, session: &Session) -> bool {
    game.native_dimension() == session.dimension
        && game.native_block(session.pos) == REQUESTER
        && mod_entity(game, session.pos)
            .is_some_and(|entity| entity.nbt.get(&"Freq".into()) == session.frequency.as_ref())
}

pub(super) fn edit(game: &mut Game<'_>, player: u128, channel: &str, data: &[u8]) {
    if channel != SCREEN {
        return;
    }
    let (Some(token), Some(&action)) = (word(data), data.get(8)) else {
        return;
    };
    let session = SESSIONS.with_borrow_mut(|sessions| {
        if sessions.get(&player)?.token == token {
            sessions.remove(&player)
        } else {
            None
        }
    });
    let (Some(mut session), Some(conn)) = (session, game.native_conn(player)) else {
        return;
    };
    let still_open = game.for_player(Target::Guest(conn), |actor| {
        if !valid(actor, &session) {
            return false;
        }
        if action == 3 {
            let Some(settings) = body(data) else {
                return false;
            };
            let Some(Tag::IntArray(counts)) = settings.get("Counts") else {
                return false;
            };
            let address = crate::save::text(settings.get("Address")).unwrap_or_default();
            if counts.len() != SLOTS
                || counts.iter().any(|n| !(1..=256).contains(n))
                || address.encode_utf16().count() > 25
                || address.chars().any(char::is_control)
            {
                return false;
            }
            let order = session.slots.order(counts.iter().map(|n| *n as u16));
            actor.native_with_mod_block_entity(session.pos, |entity| {
                entity.nbt.insert("EncodedRequest".into(), order);
                entity.nbt.insert(
                    "EncodedAddress".into(),
                    Tag::String(address.as_str().into()),
                );
                entity.nbt.insert(
                    "AllowPartial".into(),
                    Tag::Byte(i8::from(settings.get("Partial") == Some(&Tag::Byte(1)))),
                );
            });
            actor.native_block_entity_sync(session.pos);
            return false;
        }
        let Some(&index) = data.get(9).filter(|_| data.len() == 10) else {
            return false;
        };
        let index = usize::from(index);
        match action {
            0 if index < 36 => {
                if let Some(empty) = session.slots.0.iter().position(Option::is_none) {
                    session.slots.sample(empty, actor.stack_in(index));
                }
            }
            1 => session.slots.sample(index, actor.carried.as_ref()),
            2 => session.slots.sample(index, None),
            _ => return false,
        }
        true
    });
    if still_open.unwrap_or(false) {
        if let Some(view) = packet(token, 0, &Tag::compound([("Slots", session.slots.view())])) {
            let _ = game.native_net_send_to_player(player, SCREEN, &view);
        }
        SESSIONS.with_borrow_mut(|sessions| sessions.insert(player, session));
    }
}

fn origin([x, y, w, h]: [f32; 4]) -> [f32; 2] {
    [
        x + ((w - WIDTH) * 0.5).floor(),
        y + ((h - HEIGHT) * 0.5).floor(),
    ]
}

fn ghost(index: usize) -> [f32; 4] {
    [27.0 + index as f32 * 20.0, 28.0, 16.0, 16.0]
}

fn inventory(index: usize) -> [f32; 4] {
    let row = if index < 9 {
        58.0
    } else {
        18.0 * (index / 9 - 1) as f32
    };
    [5.0 + (index % 9) as f32 * 18.0, 142.0 + row, 16.0, 16.0]
}

pub(super) fn draw(game: &Game<'_>, screen: &NativeScreenView<'_>, batch: &mut HudBatch) {
    if game.native_mod_screen() != Some(SCREEN) {
        return;
    }
    let [left, top] = origin(screen.rect);
    game.native_sprite(
        batch,
        "create:gui/requester",
        [16.0, 16.0, WIDTH, 120.0],
        [left + 3.0, top, WIDTH, 120.0],
    );
    game.native_sprite(
        batch,
        "create:gui/player_inventory",
        [0.0, 0.0, 176.0, 108.0],
        [left - 3.0, top + 124.0, 176.0, 108.0],
    );
    let title = game.translate("block.create.redstone_requester", "Redstone Requester");
    game.native_text(
        batch,
        &title,
        [
            left + 117.0 - game.native_text_width(&title) * 0.5,
            top + 4.0,
        ],
        0x3d3c48,
        false,
    );
    game.native_item(batch, REQUESTER, [left + 245.0, top + 80.0], 48.0);
    EDITOR.with_borrow_mut(|state| {
        let Some(editor) = state.as_mut() else { return };
        for (index, entry) in editor.slots.0.iter().enumerate() {
            if let Some(item) = entry {
                let [x, y, ..] = ghost(index);
                let mut icon = item.clone();
                icon.count = 1;
                game.native_gui_draw_item(batch, &icon, [left + x, top + y]);
                let count = editor.counts[index].to_string();
                game.native_text(
                    batch,
                    &count,
                    [
                        left + x + 17.0 - game.native_text_width(&count),
                        top + y + 9.0,
                    ],
                    0xffffff,
                    true,
                );
            }
        }
        for ([x, y, w, h], [u, v], active) in [
            (PARTIAL, [32.0, 192.0], editor.partial),
            (FULL, [48.0, 192.0], !editor.partial),
            (CONFIRM, [0.0, 16.0], false),
        ] {
            let bounds = [left + x, top + y, w, h];
            let tile = if contains(bounds, screen.mouse) {
                18.0
            } else if active {
                72.0
            } else {
                0.0
            };
            game.native_sprite(batch, "create:gui/widgets", [tile, 0.0, w, h], bounds);
            game.native_sprite(
                batch,
                "create:gui/icons",
                [u, v, 16.0, 16.0],
                [bounds[0] + 1.0, bounds[1] + 1.0, 16.0, 16.0],
            );
        }
        editor.address.x = left + FIELD[0];
        editor.address.y = top + FIELD[1];
        editor.address.draw(batch, &game.gui.atlas, None);
    });
    for index in 0..36 {
        if let Some(stack) = game.stack_in(index) {
            let [x, y, ..] = inventory(index);
            game.native_gui_draw_item(batch, stack, [left + x, top + y]);
        }
    }
    if let Some(stack) = &game.carried {
        game.native_gui_draw_item(batch, stack, [screen.mouse[0] - 8.0, screen.mouse[1] - 8.0]);
    }
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
    let point = [screen.mouse[0] - left, screen.mouse[1] - top];
    EDITOR.with_borrow_mut(|state| {
        let Some(editor) = state.as_mut() else { return };
        *canceled = true;
        if !matches!(button, 0 | 1) {
            return;
        }
        if contains(FIELD, point) {
            if button == 1 {
                editor.address.set_value("");
            } else if editor.address.focused {
                editor
                    .address
                    .click(&game.gui.atlas, screen.mouse[0], modifiers & 1 != 0, false);
            } else {
                editor.address.move_cursor_to_end(false);
                editor.address.highlight = 0;
            }
            editor.address.focused = true;
            return;
        }
        editor.address.focused = false;
        let shift = modifiers & 1 != 0;
        if let Some(index) = (0..SLOTS).find(|&i| contains(ghost(i), point)) {
            editor.actions.push(if shift {
                Action::Clear(index)
            } else {
                Action::Sample(index)
            });
        } else if let Some(index) = (0..36).find(|&i| contains(inventory(i), point)) {
            editor.actions.push(if shift {
                Action::QuickCopy(index)
            } else {
                Action::Inventory(index, button)
            });
        } else if button == 0 {
            if contains(PARTIAL, point) {
                editor.partial = true;
            }
            if contains(FULL, point) {
                editor.partial = false;
            }
            if contains(CONFIRM, point) {
                editor.actions.push(Action::Close);
            }
        }
    });
}

pub(super) fn scroll(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    delta: [f64; 2],
    canceled: &mut bool,
) {
    if *canceled || game.native_mod_screen() != Some(SCREEN) || delta[1] == 0.0 {
        return;
    }
    let [left, top] = origin(screen.rect);
    let point = [screen.mouse[0] - left, screen.mouse[1] - top];
    let Some(index) = (0..SLOTS).find(|&i| contains(ghost(i), point)) else {
        return;
    };
    EDITOR.with_borrow_mut(|state| {
        if let Some(editor) = state.as_mut() {
            if editor.slots.0[index].is_some() {
                let unit = if game.native_sneaking() { 10 } else { 1 };
                editor.counts[index] = (i32::from(editor.counts[index])
                    + delta[1].signum() as i32 * unit)
                    .clamp(1, 256) as u16;
            }
            *canceled = true;
        }
    });
}

pub(super) fn character(game: &Game<'_>, c: char, canceled: &mut bool) {
    if *canceled || game.native_mod_screen() != Some(SCREEN) {
        return;
    }
    EDITOR.with_borrow_mut(|state| {
        if let Some(editor) = state.as_mut().filter(|e| e.address.focused) {
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
        if let Some(editor) = state.as_mut().filter(|e| e.address.focused) {
            *canceled = edit_address_key(&mut editor.address, key, modifiers);
        }
    });
}

fn send(game: &mut Game<'_>, token: u64, action: u8, index: usize) {
    let mut data = [0; 10];
    data[..8].copy_from_slice(&token.to_be_bytes());
    data[8] = action;
    data[9] = index as u8;
    let _ = game.native_net_send_to_server(SCREEN, &data);
}

pub(super) fn tick(game: &mut Game<'_>) {
    let visible = game.native_mod_screen() == Some(SCREEN);
    let pending = EDITOR.with_borrow_mut(|state| {
        let editor = state.as_mut()?;
        let mut actions = std::mem::take(&mut editor.actions);
        if !visible {
            actions.push(Action::Close);
        }
        Some((editor.token, actions))
    });
    let Some((token, actions)) = pending else {
        return;
    };
    for action in actions {
        match action {
            Action::Inventory(index, button) => {
                let screen = std::mem::replace(&mut game.screen, Screen::Inventory);
                game.menu_ops(&[(Some(index), button, Input::Pickup)]);
                game.screen = screen;
            }
            Action::QuickCopy(index) => send(game, token, 0, index),
            Action::Sample(index) => send(game, token, 1, index),
            Action::Clear(index) => send(game, token, 2, index),
            Action::Close => {
                let Some(editor) = EDITOR.take() else { break };
                if game.carried.is_some() {
                    game.close_container();
                }
                let settings = Tag::compound([
                    (
                        "Counts",
                        Tag::IntArray(editor.counts.map(i32::from).to_vec()),
                    ),
                    ("Address", Tag::String(editor.address.value.as_str().into())),
                    ("Partial", Tag::Byte(i8::from(editor.partial))),
                ]);
                if let Some(data) = packet(token, 3, &settings) {
                    let _ = game.native_net_send_to_server(SCREEN, &data);
                }
                game.native_mod_screen_close(SCREEN);
                break;
            }
        }
    }
}
