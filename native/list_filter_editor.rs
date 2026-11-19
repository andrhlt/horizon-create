use std::cell::{Cell, RefCell};
use std::collections::HashMap;

use horizon_client::first_person::Hand;
use horizon_client::hud::HudBatch;
use horizon_client::menu::Input;
use horizon_client::mod_api::NativeScreenView;
use horizon_world::nbt::{self, Compound, Tag};

use crate::{items::ItemStack, save::item_to_nbt};

use super::{Game, Screen, commands::Target, create_depot, create_machines::int};

use super::create_attribute_filter_ui::{self as attributes, Attributes};

const ITEM: &str = "create:filter";
const SCREEN: &str = "create:list_filter_editor";
const ENTRIES: &str = "create:filter_items";
const BLACKLIST: &str = "create:filter_items_blacklist";
const RESPECT: &str = "create:filter_items_respect_nbt";
const LIMITS: nbt::Limits = nbt::Limits {
    max_bytes: 60_000,
    max_nodes: 2048,
    max_depth: 20,
};
const GHOSTS: usize = 18;

#[derive(Clone, Default)]
struct Draft {
    entries: [Option<ItemStack>; GHOSTS],
    blacklist: bool,
    respect: bool,
    attributes: Option<Attributes>,
}

struct Session {
    token: u64,
    holder: ItemStack,
    index: usize,
    draft: Draft,
}

struct Editor {
    token: u64,
    draft: Draft,
    actions: Vec<Action>,
}

enum Action {
    Inventory(usize, i32),
    QuickCopy(usize),
    Ghost(usize),
    ClearGhost(usize),
    Blacklist(bool),
    Respect(bool),
    Clear,
    Save,
    PickAttribute(bool),
    AddAttribute(bool),
    AttributeMode(usize),
}

thread_local! {
    static SERIAL: Cell<u64> = const { Cell::new(0) };
    static SESSIONS: RefCell<HashMap<u128, Session>> = RefCell::new(HashMap::new());
    static EDITOR: RefCell<Option<Editor>> = const { RefCell::new(None) };
}

pub(super) fn register(types: &mut Vec<String>) {
    types.extend([ENTRIES, BLACKLIST, RESPECT].map(str::to_owned));
    attributes::register(types);
}

fn list_tag(entries: &[Option<ItemStack>; GHOSTS]) -> Tag {
    Tag::List(
        entries
            .iter()
            .enumerate()
            .filter_map(|(slot, entry)| {
                let mut entry_tag = Compound::new();
                entry_tag.insert("slot".into(), Tag::Int(slot as i32));
                entry_tag.insert("item".into(), item_to_nbt(entry.as_ref()?));
                Some(Tag::Compound(entry_tag))
            })
            .collect(),
    )
}

fn entries(tag: Option<&Tag>) -> [Option<ItemStack>; GHOSTS] {
    let mut entries = std::array::from_fn(|_| None);
    if let Some(Tag::List(list)) = tag {
        for item in list {
            let Tag::Compound(item) = item else { continue };
            let Some(slot) = int(item, "slot")
                .or_else(|| int(item, "Slot"))
                .and_then(|slot| usize::try_from(slot).ok())
                .filter(|&slot| slot < GHOSTS)
            else {
                continue;
            };
            entries[slot] =
                ItemStack::from_nbt(create_depot::compound(item, "item").unwrap_or(item));
        }
    }
    entries
}

impl Draft {
    fn read(game: &Game<'_>, holder: &ItemStack) -> Self {
        let component = |id| game.native_component(holder, id).ok().flatten();
        let flag = |id| matches!(component(id), Some(Tag::Byte(1) | Tag::Int(1)));
        Self {
            entries: entries(component(ENTRIES)),
            blacklist: flag(BLACKLIST),
            respect: flag(RESPECT),
            attributes: (holder.item.as_ref() == attributes::ITEM)
                .then(|| Attributes::read(game, holder)),
        }
    }

    fn screen(&self) -> &'static str {
        if self.attributes.is_some() {
            attributes::SCREEN
        } else {
            SCREEN
        }
    }

    fn ghost_count(&self) -> usize {
        if self.attributes.is_some() { 1 } else { GHOSTS }
    }

    fn set_reference(&mut self, items: &crate::items::Items, sample: Option<&ItemStack>) {
        if let Some(attributes) = &mut self.attributes {
            let sample = sample.cloned().map(|mut stack| {
                stack.count = 1;
                stack
            });
            if self.entries[0] != sample {
                attributes.reference(items, sample.as_ref());
            }
            self.entries[0] = sample;
        }
    }

    fn encode(&self, token: u64, opening: bool) -> Option<Vec<u8>> {
        let mut state = Compound::new();
        state.insert("Entries".into(), list_tag(&self.entries));
        state.insert("Blacklist".into(), Tag::Byte(i8::from(self.blacklist)));
        state.insert("Respect".into(), Tag::Byte(i8::from(self.respect)));
        if let Some(attributes) = &self.attributes {
            state.insert("Attributes".into(), attributes.tag());
        }
        let body = nbt::write_network(&Tag::Compound(state), LIMITS).ok()?;
        let mut packet = Vec::with_capacity(9 + body.len());
        packet.extend_from_slice(&token.to_be_bytes());
        packet.push(u8::from(opening));
        packet.extend(body);
        Some(packet)
    }

    fn decode(data: &[u8]) -> Option<(u64, bool, Self)> {
        let (Tag::Compound(state), bytes) = nbt::read_network(data.get(9..)?, LIMITS).ok()? else {
            return None;
        };
        if bytes != data.len() - 9 {
            return None;
        }
        Some((
            token(data)?,
            *data.get(8)? == 1,
            Self {
                entries: entries(state.get(&"Entries".into())),
                blacklist: int(&state, "Blacklist") == Some(1),
                respect: int(&state, "Respect") == Some(1),
                attributes: state
                    .get(&"Attributes".into())
                    .and_then(Attributes::from_tag),
            },
        ))
    }

    fn write(&self, game: &Game<'_>, holder: &mut ItemStack) -> bool {
        if let Some(attributes) = &self.attributes {
            return attributes.write(game, holder);
        }
        let any = self.entries.iter().any(Option::is_some);
        let list = if any {
            game.native_set_component(holder, ENTRIES, list_tag(&self.entries))
        } else {
            game.native_remove_component(holder, ENTRIES)
        };
        if list.is_err() {
            return false;
        }
        for (key, enabled) in [(BLACKLIST, self.blacklist), (RESPECT, self.respect)] {
            let result = if any || self.blacklist || self.respect {
                game.native_set_component(holder, key, Tag::Byte(i8::from(enabled)))
            } else {
                game.native_remove_component(holder, key)
            };
            if result.is_err() {
                return false;
            }
        }
        true
    }

    fn quick_copy(&mut self, sample: Option<&ItemStack>) {
        let Some(sample) = sample else { return };
        let mut sample = sample.clone();
        sample.count = 1;
        for entry in &mut self.entries {
            if entry.as_ref() == Some(&sample) {
                return;
            }
            if entry.is_none() {
                *entry = Some(sample);
                return;
            }
        }
    }
}

fn token(data: &[u8]) -> Option<u64> {
    Some(u64::from_be_bytes(data.get(..8)?.try_into().ok()?))
}

pub(super) fn open(game: &mut Game<'_>, stack: &ItemStack, claimed: &mut bool) {
    if *claimed
        || !matches!(stack.item.as_ref(), ITEM | attributes::ITEM)
        || game.hand != Hand::Main
        || game.native_sneaking()
    {
        return;
    }
    let Some(player) = game.native_acting_player() else {
        return;
    };
    let token = SERIAL.with(|serial| {
        let token = serial.get().wrapping_add(1);
        serial.set(token);
        token
    });
    let draft = Draft::read(game, stack);
    let Some(view) = draft.encode(token, true) else {
        return;
    };
    if game
        .native_net_send_to_player(player.uuid, SCREEN, &view)
        .is_ok()
    {
        let session = Session {
            token,
            holder: stack.clone(),
            index: game.selected,
            draft,
        };
        SESSIONS.with_borrow_mut(|sessions| sessions.insert(player.uuid, session));
        *claimed = true;
    }
}

pub(super) fn receive(game: &mut Game<'_>, channel: &str, data: &[u8]) {
    if channel != SCREEN {
        return;
    }
    let Some((token, opening, draft)) = Draft::decode(data) else {
        return;
    };
    if game.native_mod_screen() == Some(draft.screen()) {
        EDITOR.with_borrow_mut(|state| {
            if let Some(editor) = state.as_mut().filter(|editor| editor.token == token) {
                editor.draft = draft;
            }
        });
    } else if opening && game.native_mod_screen_open(draft.screen()) {
        EDITOR.replace(Some(Editor {
            token,
            draft,
            actions: Vec::new(),
        }));
    }
}

pub(super) fn edit(game: &mut Game<'_>, player: u128, channel: &str, data: &[u8]) {
    if channel != SCREEN || data.len() != 10 {
        return;
    }
    let Some(token) = token(data) else { return };
    let op = data[8];
    let index = usize::from(data[9]);
    let session = SESSIONS.with_borrow_mut(|sessions| {
        if sessions.get(&player)?.token != token {
            return None;
        }
        sessions.remove(&player)
    });
    let Some(mut session) = session else { return };
    let Some(conn) = game.native_conn(player) else {
        return;
    };
    let mut valid = false;
    game.for_player(Target::Guest(conn), |actor| {
        if actor.selected != session.index || actor.stack_in(session.index) != Some(&session.holder)
        {
            return;
        }
        valid = true;
        match op {
            0 if index < 36 && index != session.index => {
                if session.draft.attributes.is_some() {
                    session
                        .draft
                        .set_reference(actor.items(), actor.stack_in(index));
                } else {
                    session.draft.quick_copy(actor.stack_in(index));
                }
            }
            1 if index == 0 && session.draft.attributes.is_some() => {
                session
                    .draft
                    .set_reference(actor.items(), actor.carried.as_ref());
            }
            1 if index < session.draft.ghost_count() => {
                session.draft.entries[index] = actor.carried.clone().map(|mut stack| {
                    stack.count = 1;
                    stack
                });
            }
            2 if session.draft.attributes.is_none() && index < GHOSTS => {
                session.draft.entries[index] = None
            }
            3 => session.draft.blacklist = index != 0,
            4 => session.draft.respect = index != 0,
            5 => {
                if let Some(attributes) = &mut session.draft.attributes {
                    attributes.clear();
                } else {
                    session.draft.entries.fill(None);
                }
            }
            6 => {
                let mut holder = session.holder.clone();
                if session.draft.write(actor, &mut holder) {
                    *actor.stack_in_mut(session.index) = Some(holder);
                }
            }
            7 => {
                if let Some(attributes) = &mut session.draft.attributes {
                    attributes.pick(index != 0);
                }
            }
            8 => {
                if let Some(attributes) = &mut session.draft.attributes {
                    attributes.add(index != 0);
                }
            }
            9 => {
                if let Some(attributes) = &mut session.draft.attributes {
                    attributes.mode(index);
                }
            }
            _ => {}
        }
    });
    if valid && op != 6 {
        if let Some(view) = session.draft.encode(token, false) {
            let _ = game.native_net_send_to_player(player, SCREEN, &view);
        }
        SESSIONS.with_borrow_mut(|sessions| sessions.insert(player, session));
    }
}

fn origin([x, y, w, h]: [f32; 4], attr: bool) -> [f32; 2] {
    let [width, height, offset] = if attr {
        [241.0, 197.0, 7.0]
    } else {
        [214.0, 211.0, 5.0]
    };
    [
        x + ((w - width) / 2.0).floor() - 11.0,
        y + ((h - height) / 2.0).floor() + offset,
    ]
}

fn slot(index: usize, ghost: bool, attr: bool) -> [f32; 2] {
    let col = (index % 9) as f32 * 18.0;
    if ghost {
        return if attr {
            [16.0, 27.0]
        } else {
            [23.0 + col, 25.0 + (index / 9) as f32 * 18.0]
        };
    }
    let row = if index < 9 {
        58.0
    } else {
        (index / 9 - 1) as f32 * 18.0
    };
    let [left, top] = if attr { [51.0, 107.0] } else { [38.0, 121.0] };
    [left + col, top + row]
}

fn contains([x, y]: [f32; 2], size: f32, [mouse_x, mouse_y]: [f32; 2]) -> bool {
    mouse_x >= x && mouse_x < x + size && mouse_y >= y && mouse_y < y + size
}

fn buttons(draft: &Draft) -> [([f32; 2], [f32; 2], bool); 6] {
    [
        ([18.0, 75.0], [128.0, 0.0], draft.blacklist),
        ([36.0, 75.0], [144.0, 0.0], !draft.blacklist),
        ([60.0, 75.0], [208.0, 0.0], draft.respect),
        ([78.0, 75.0], [224.0, 0.0], !draft.respect),
        ([152.0, 75.0], [16.0, 0.0], false),
        ([181.0, 75.0], [0.0, 16.0], false),
    ]
}

pub(super) fn draw(game: &Game<'_>, screen: &NativeScreenView<'_>, batch: &mut HudBatch) {
    let Some(mod_id @ (SCREEN | attributes::SCREEN)) = game.native_mod_screen() else {
        return;
    };
    let attr = mod_id == attributes::SCREEN;
    let [left, top] = origin(screen.rect, attr);
    let [width, height, atlas_y, inventory_x] = if attr {
        [241.0, 85.0, 99.0, 43.0]
    } else {
        [214.0, 99.0, 0.0, 30.0]
    };
    game.native_sprite(
        batch,
        "create:gui/filters",
        [0.0, atlas_y, width, height],
        [left, top, width, height],
    );
    game.native_sprite(
        batch,
        "create:gui/player_inventory",
        [0.0, 0.0, 176.0, 108.0],
        [left + inventory_x, top + height + 4.0, 176.0, 108.0],
    );
    let title = if attr {
        game.translate("item.create.attribute_filter", "Attribute Filter")
    } else {
        game.translate("item.create.filter", "List Filter")
    };
    game.native_text(
        batch,
        &title,
        [
            left + (width - 8.0 - game.native_text_width(&title)) * 0.5,
            top + 4.0,
        ],
        0x303030,
        false,
    );
    game.native_item(
        batch,
        if attr { attributes::ITEM } else { ITEM },
        [left + width + 8.0, top + height - 52.0],
        64.0,
    );
    EDITOR.with_borrow(|state| {
        let Some(editor) = state.as_ref() else { return };
        for (index, item) in editor.draft.entries.iter().enumerate() {
            if let Some(item) = item {
                let [x, y] = slot(index, true, attr);
                game.native_gui_draw_item(batch, item, [left + x, top + y]);
            }
        }
        let mut draw_button =
            |[x, y]: [f32; 2], [icon_x, icon_y]: [f32; 2], active: bool, enabled: bool| {
                let at = [left + x, top + y];
                let tile = if !enabled {
                    90.0
                } else if contains(at, 18.0, screen.mouse) {
                    18.0
                } else if active {
                    72.0
                } else {
                    0.0
                };
                game.native_sprite(
                    batch,
                    "create:gui/widgets",
                    [tile, 0.0, 18.0, 18.0],
                    [at[0], at[1], 18.0, 18.0],
                );
                game.native_sprite(
                    batch,
                    "create:gui/icons",
                    [icon_x, icon_y, 16.0, 16.0],
                    [at[0] + 1.0, at[1] + 1.0, 16.0, 16.0],
                );
            };
        if let Some(attributes) = &editor.draft.attributes {
            for (position, icon, active, enabled) in attributes.buttons() {
                draw_button(position, icon, active, enabled);
            }
            attributes.draw_label(game, batch, [left, top]);
        } else {
            for (position, icon, active) in buttons(&editor.draft) {
                draw_button(position, icon, active, true);
            }
        }
    });
    for index in 0..36 {
        if let Some(stack) = game.stack_in(index) {
            let [x, y] = slot(index, false, attr);
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
    if *canceled {
        return;
    }
    let Some(mod_id @ (SCREEN | attributes::SCREEN)) = game.native_mod_screen() else {
        return;
    };
    let attr = mod_id == attributes::SCREEN;
    let [left, top] = origin(screen.rect, attr);
    let at = [screen.mouse[0] - left, screen.mouse[1] - top];
    EDITOR.with_borrow_mut(|state| {
        let Some(editor) = state.as_mut() else { return };
        *canceled = true;
        if !matches!(button, 0 | 1) {
            return;
        }
        let shift = modifiers & 1 != 0;
        let action = if let Some(index) =
            (0..editor.draft.ghost_count()).find(|&i| contains(slot(i, true, attr), 16.0, at))
        {
            if shift {
                Action::ClearGhost(index)
            } else {
                Action::Ghost(index)
            }
        } else if let Some(index) = (0..36).find(|&i| contains(slot(i, false, attr), 16.0, at)) {
            if index == game.selected {
                return;
            }
            if shift {
                Action::QuickCopy(index)
            } else {
                Action::Inventory(index, button)
            }
        } else if button == 0 {
            let action = if let Some(attributes) = &editor.draft.attributes {
                match attributes
                    .buttons()
                    .iter()
                    .position(|&(point, _, _, enabled)| enabled && contains(point, 18.0, at))
                {
                    Some(index @ 0..=2) => Some(Action::AttributeMode(index)),
                    Some(idx @ (3 | 4)) => Some(Action::AddAttribute(idx == 4)),
                    Some(5) => Some(Action::Clear),
                    Some(6) => Some(Action::Save),
                    _ => None,
                }
            } else {
                let row = buttons(&editor.draft)
                    .iter()
                    .position(|&(point, _, _)| contains(point, 18.0, at));
                match row {
                    Some(0 | 1) => Some(Action::Blacklist(row == Some(0))),
                    Some(2 | 3) => Some(Action::Respect(row == Some(2))),
                    Some(4) => Some(Action::Clear),
                    Some(5) => Some(Action::Save),
                    _ => None,
                }
            };
            let Some(action) = action else { return };
            action
        } else {
            return;
        };
        editor.actions.push(action);
    });
}

pub(super) fn scroll(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    scroll: [f64; 2],
    canceled: &mut bool,
) {
    if *canceled || game.native_mod_screen() != Some(attributes::SCREEN) || scroll[1] == 0.0 {
        return;
    }
    let [left, top] = origin(screen.rect, true);
    let [x, y, w, h] = attributes::CHOICE;
    let [mx, my] = [screen.mouse[0] - left, screen.mouse[1] - top];
    if mx >= x && mx < x + w && my >= y && my < y + h {
        EDITOR.with_borrow_mut(|state| {
            if let Some(editor) = state.as_mut() {
                editor.actions.push(Action::PickAttribute(scroll[1] > 0.0));
                *canceled = true;
            }
        });
    }
}

fn send(game: &mut Game<'_>, token: u64, op: u8, index: usize) {
    let mut data = [0; 10];
    data[..8].copy_from_slice(&token.to_be_bytes());
    data[8] = op;
    data[9] = index as u8;
    let _ = game.native_net_send_to_server(SCREEN, &data);
}

pub(super) fn tick(game: &mut Game<'_>) {
    let pending = EDITOR.with_borrow_mut(|state| {
        let editor = state.as_mut()?;
        let id = editor.draft.screen();
        if game.native_mod_screen() == Some(id) {
            Some((editor.token, id, std::mem::take(&mut editor.actions)))
        } else {
            state.take().map(|mut editor| {
                editor.actions.push(Action::Save);
                (editor.token, id, editor.actions)
            })
        }
    });
    let Some((token, screen, actions)) = pending else {
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
            Action::Ghost(index) => send(game, token, 1, index),
            Action::ClearGhost(index) => send(game, token, 2, index),
            Action::Blacklist(enabled) => send(game, token, 3, usize::from(enabled)),
            Action::Respect(enabled) => send(game, token, 4, usize::from(enabled)),
            Action::Clear => send(game, token, 5, 0),
            Action::PickAttribute(forward) => send(game, token, 7, usize::from(forward)),
            Action::AddAttribute(inverted) => send(game, token, 8, usize::from(inverted)),
            Action::AttributeMode(mode) => send(game, token, 9, mode),
            Action::Save => {
                EDITOR.replace(None);
                if game.carried.is_some() {
                    game.close_container();
                }
                send(game, token, 6, 0);
                game.native_mod_screen_close(screen);
                break;
            }
        }
    }
}
