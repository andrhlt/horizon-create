use std::cell::{Cell, RefCell};
use std::collections::HashMap;
use std::time::{Duration, Instant};

use horizon_client::{
    clipboard::{
        Clipboard, EditShortcut, MemoryClipboard, edit_shortcut, helper_clipboard_contents,
    },
    first_person::Hand,
    hud::HudBatch,
    mod_api::NativeScreenView,
    multiline_edit::split_ranges,
    text::Text,
    ui::EditBox,
};
use horizon_core::{
    geometry::{Aabb, Vec3},
    position::BlockPos,
    random::RandomSource,
};
use horizon_world::nbt::{self, Compound, Tag};

use crate::items::ItemStack;

use super::{
    Game,
    commands::Target,
    create_clipboard::{COMPONENT, ITEM, content},
    create_clipboard_block as board,
    create_machines::int,
    create_package_address::is_blank,
};

const SCREEN: &str = "create:clipboard_editor";
const BACKGROUND: &str = "create:gui/clipboard";
const LINE_HEIGHT: f32 = 9.0;
const ENTRY_GAP: f32 = 3.0;
const PAGE_HEIGHT: f32 = 185.0;
const LIMITS: nbt::Limits = nbt::Limits {
    max_bytes: 30_000 - size_of::<u64>(),
    max_nodes: 8_192,
    max_depth: 32,
};

#[derive(Clone, Copy, PartialEq, Eq)]
enum EditedClipboard {
    Held(usize),
    Placed {
        dimension: &'static str,
        pos: [i32; 3],
    },
}

#[derive(Clone)]
struct Session {
    token: u64,
    target: EditedClipboard,
    original: Compound,
}

struct Editor {
    token: u64,
    target: Option<[i32; 3]>,
    pages: Vec<Vec<Tag>>,
    page: usize,
    remembered: i32,
    read_only: bool,
    active: Option<(usize, EditBox)>,
    closing: bool,
    dirty: bool,
    note_sound: Option<bool>,
    last_click: Option<(usize, usize, Instant)>,
    shortcuts: Vec<EditShortcut>,
}

thread_local! {
    static SESSIONS: RefCell<HashMap<u128, Session>> = RefCell::new(HashMap::new());
    static SERIAL: Cell<u64> = const { Cell::new(0) };
    static EDITOR: RefCell<Option<Editor>> = const { RefCell::new(None) };
    static OFFSCREEN_CLIPBOARD: RefCell<MemoryClipboard> = const { RefCell::new(MemoryClipboard(String::new())) };
}

fn packet(token: u64, data: Compound) -> Option<Vec<u8>> {
    let body = nbt::write_network(&Tag::Compound(data), LIMITS).ok()?;
    let mut packet = token.to_be_bytes().to_vec();
    packet.extend(body);
    Some(packet)
}

fn unpack(data: &[u8]) -> Option<(u64, Compound)> {
    let token = u64::from_be_bytes(data.get(..8)?.try_into().ok()?);
    let body = data.get(8..)?;
    let (Tag::Compound(content), bytes) = nbt::read_network(body, LIMITS).ok()? else {
        return None;
    };
    (bytes == body.len()).then_some((token, content))
}

fn text(entry: &Tag) -> String {
    match entry {
        Tag::Compound(entry) => entry.get(&"text".into()).map_or_else(String::new, |text| {
            horizon_protocol::text::plain(text, &Default::default())
        }),
        _ => String::new(),
    }
}

fn nonempty(entry: &Tag) -> bool {
    !is_blank(&text(entry))
}

fn blank_entry() -> Tag {
    Tag::Compound(Compound::from([
        ("checked".into(), Tag::Byte(0)),
        ("text".into(), Tag::String("".into())),
        ("icon".into(), Tag::Compound(Compound::new())),
        ("item_amount".into(), Tag::Int(0)),
    ]))
}

fn pages(content: &Compound) -> Option<Vec<Vec<Tag>>> {
    let Tag::List(pages) = content.get(&"pages".into())? else {
        return None;
    };
    pages
        .iter()
        .map(|page| match page {
            Tag::List(entries) => Some(entries.clone()),
            _ => None,
        })
        .collect()
}

fn checked(entry: &Tag) -> bool {
    matches!(entry, Tag::Compound(entry) if int(entry, "checked") == Some(1))
}

fn has_click_event(tag: &Tag) -> bool {
    match tag {
        Tag::Compound(values) => values.iter().any(|(key, value)| {
            key == &"click_event".into() || key == &"clickEvent".into() || has_click_event(value)
        }),
        Tag::List(values) => values.iter().any(has_click_event),
        _ => false,
    }
}

fn entry_height(game: &Game<'_>, value: &str, width: f32) -> f32 {
    let chars: Vec<_> = value.chars().collect();
    let lines = split_ranges(&game.gui.atlas.font, &chars, width)
        .len()
        .max(1);
    lines as f32 * LINE_HEIGHT + ENTRY_GAP
}

fn icon(entry: &Tag) -> Option<ItemStack> {
    let Tag::Compound(entry) = entry else {
        return None;
    };
    ItemStack::from_nbt(super::create_depot::compound(entry, "icon")?)
}

fn entry_width(entry: &Tag) -> f32 {
    if icon(entry).is_some() { 134.0 } else { 150.0 }
}

fn text_rows(game: &Game<'_>, chars: &[char], width: f32) -> Vec<(usize, usize)> {
    let mut lines = split_ranges(&game.gui.atlas.font, chars, width);
    if lines.is_empty() || chars.last() == Some(&'\n') {
        lines.push((chars.len(), chars.len()));
    }
    lines
}

fn point_cursor(game: &Game<'_>, chars: &[char], line: (usize, usize), x: f32) -> usize {
    let (start, end) = line;
    let mut width = 0.0;
    for (relative, &ch) in chars[start..end].iter().enumerate() {
        width += game.gui.atlas.font.advance(ch, &Default::default());
        if width > x {
            return start + relative;
        }
    }
    end
}

fn enter_shortcut(game: &Game<'_>, field: &mut EditBox, key: &str, shift: bool, control: bool) {
    match key {
        "key.keyboard.a" if control => {
            field.move_cursor_to_end(false);
            field.highlight = 0;
        }
        "key.keyboard.backspace" | "key.keyboard.delete" => {
            let direction = if key == "key.keyboard.backspace" {
                -1
            } else {
                1
            };
            let delta = if control {
                field.word_position(direction) as isize - field.cursor as isize
            } else {
                direction
            };
            field.delete_chars(delta);
        }
        "key.keyboard.left" | "key.keyboard.right" => {
            let backwards = key == "key.keyboard.left";
            let at = if control {
                field.word_position(if backwards { -1 } else { 1 })
            } else if backwards {
                field.cursor.saturating_sub(1)
            } else {
                field.cursor + 1
            };
            field.set_cursor(at, shift);
        }
        "key.keyboard.home" | "key.keyboard.end" | "key.keyboard.up" | "key.keyboard.down" => {
            let chars: Vec<_> = field.value.chars().collect();
            let lines = text_rows(game, &chars, field.width);
            let line = lines
                .partition_point(|&(from, _)| from <= field.cursor)
                .saturating_sub(1);
            let (start, end) = lines[line];
            let at = match key {
                "key.keyboard.home" => start,
                "key.keyboard.end" => end,
                _ => {
                    let next = if key == "key.keyboard.up" {
                        line.checked_sub(1)
                    } else {
                        Some(line + 1)
                    };
                    next.and_then(|next| lines.get(next))
                        .map_or(field.cursor, |&(from, to)| {
                            (from + field.cursor.saturating_sub(start)).min(to)
                        })
                }
            };
            field.set_cursor(at, shift);
        }
        _ => {}
    }
}

impl Editor {
    fn change_page(&mut self, next: bool) {
        self.finish_entry();
        let page = if next {
            (self.page + 1).min(50)
        } else {
            self.page.saturating_sub(1)
        };
        if self.read_only && page >= self.pages.len() {
            return;
        }
        if page >= self.pages.len() {
            self.pages.push(Vec::new());
        } else if page < self.page && self.pages[self.page].iter().all(|entry| !nonempty(entry)) {
            self.pages.remove(self.page);
        }
        self.page = page;
        self.last_click = None;
        self.start_empty_page();
    }

    fn start_empty_page(&mut self) {
        if self.pages[self.page].is_empty() && !self.read_only {
            self.pages[self.page].push(blank_entry());
            self.edit_line(0);
        }
    }

    fn edit_line(&mut self, line: usize) {
        self.finish_entry();
        if self.read_only {
            return;
        }
        let Some(entry) = self.pages[self.page].get(line) else {
            return;
        };
        let mut field = EditBox::new(0.0, 0.0, entry_width(entry), 10.0);
        field.bordered = false;
        field.focused = true;
        field.multiline = true;
        field.max_length = usize::MAX;
        field.text_color = 0xff311a00;
        field.set_value(&text(entry));
        self.active = Some((line, field));
    }

    fn store_entry(&mut self) {
        let Some((line, field)) = &self.active else {
            return;
        };
        let tag = &mut self.pages[self.page][*line];
        if text(tag) != field.value
            && let Tag::Compound(entry) = tag
        {
            entry.insert("text".into(), Tag::String(field.value.as_str().into()));
        }
    }

    fn finish_entry(&mut self) {
        self.store_entry();
        self.active = None;
    }

    fn draft(&mut self) -> Option<Vec<u8>> {
        if self.target.is_none() || !std::mem::take(&mut self.dirty) {
            return None;
        }
        self.store_entry();
        packet(
            self.token,
            Compound::from([
                ("Draft".into(), Tag::Byte(1)),
                (
                    "pages".into(),
                    Tag::List(self.pages.iter().cloned().map(Tag::List).collect()),
                ),
                ("previously_opened_page".into(), Tag::Int(self.remembered)),
            ]),
        )
    }

    fn edit_value(&mut self, game: &Game<'_>, change: impl FnOnce(&mut EditBox)) {
        let Some((line, field)) = &mut self.active else {
            return;
        };
        let previous = field.clone();
        change(field);
        if field.value == previous.value {
            return;
        }
        if Self::height(game, &self.pages[self.page], Some((*line, &field.value))) < PAGE_HEIGHT {
            self.dirty = true;
        } else {
            *field = previous;
        }
    }

    fn height(game: &Game<'_>, entries: &[Tag], edited: Option<(usize, &str)>) -> f32 {
        entries
            .iter()
            .enumerate()
            .map(|(line, entry)| {
                if let Some((_, value)) = edited.filter(|(edited, _)| *edited == line) {
                    entry_height(game, value, 150.0)
                } else {
                    entry_height(game, &text(entry), 150.0)
                }
            })
            .sum()
    }

    fn next_line(&mut self, game: &Game<'_>) {
        if let Some((line, _)) = &self.active {
            let previous = *line;
            let following = previous + 1;
            self.finish_entry();
            let entries = &mut self.pages[self.page];
            if entries.len() == following || entries.get(following).is_some_and(nonempty) {
                entries.insert(following, blank_entry());
                if Self::height(game, entries, Some((following, " "))) >= PAGE_HEIGHT {
                    entries.remove(following);
                    self.edit_line(previous);
                    return;
                }
            }
            self.edit_line(following);
        }
    }

    fn remove_empty_line(&mut self) -> bool {
        let Some((line, field)) = &self.active else {
            return false;
        };
        if !field.value.is_empty() || self.pages[self.page].len() <= 1 {
            return false;
        }
        let line = *line;
        self.active = None;
        self.pages[self.page].remove(line);
        self.edit_line(line.saturating_sub(1));
        true
    }

    fn cursor_at(&self, game: &Game<'_>, [x, y]: [f32; 2]) -> Option<(usize, usize)> {
        let (line, field) = self.active.as_ref()?;
        let entries = &self.pages[self.page];
        let height: f32 = entries[..*line]
            .iter()
            .map(|entry| entry_height(game, &text(entry), entry_width(entry)))
            .sum();
        let chars: Vec<_> = field.value.chars().collect();
        let lines = text_rows(game, &chars, field.width);
        let row = ((y - 50.0 - height) / LINE_HEIGHT) as isize;
        let pos = if row < 0 {
            0
        } else if let Some(&row) = lines.get(row as usize) {
            let x = x - if icon(&entries[*line]).is_some() {
                74.0
            } else {
                58.0
            };
            point_cursor(game, &chars, row, x)
        } else {
            chars.len()
        };
        Some((*line, pos))
    }

    fn click_cursor(&mut self, game: &Game<'_>, point: [f32; 2], shift: bool) {
        let Some((line, pos)) = self.cursor_at(game, point) else {
            return;
        };
        let Some((_, field)) = &mut self.active else {
            return;
        };
        let now = Instant::now();
        let double = self
            .last_click
            .is_some_and(|(previous_line, previous_pos, at)| {
                previous_line == line
                    && previous_pos == pos
                    && now.duration_since(at) < Duration::from_millis(250)
            });
        if !double {
            field.set_cursor(pos, shift);
        } else if field.cursor == field.highlight {
            let chars: Vec<_> = field.value.chars().collect();
            let separator = |ch: &char| matches!(ch, ' ' | '\n');
            let low = chars[..pos]
                .iter()
                .rposition(separator)
                .map_or(0, |space| space + 1);
            let high = pos
                + chars[pos..]
                    .iter()
                    .position(separator)
                    .unwrap_or(chars.len() - pos);
            field.set_cursor(low, false);
            field.set_cursor(high, true);
        } else {
            field.move_cursor_to_end(false);
            field.highlight = 0;
        }
        self.last_click = Some((line, pos, now));
    }

    fn apply_shortcuts(&mut self, game: &mut Game<'_>) {
        for shortcut in std::mem::take(&mut self.shortcuts) {
            let Some((_, field)) = self.active.as_ref() else {
                continue;
            };
            let copied = match shortcut {
                EditShortcut::Copy | EditShortcut::Cut => Some(field.selected_text()),
                _ => None,
            };
            if let Some(copied) = copied {
                if game.options.offscreen {
                    OFFSCREEN_CLIPBOARD.with_borrow_mut(|clipboard| clipboard.set(&copied));
                } else {
                    game.clipboard.set(&copied);
                }
            }
            match shortcut {
                EditShortcut::Cut => self.edit_value(game, |field| field.insert_text("")),
                EditShortcut::Paste => {
                    let pasted = if game.options.offscreen {
                        OFFSCREEN_CLIPBOARD.with_borrow_mut(Clipboard::get)
                    } else {
                        game.clipboard.get()
                    };
                    let pasted = helper_clipboard_contents(&pasted);
                    self.edit_value(game, |field| field.insert_text(&pasted));
                }
                _ => {}
            }
        }
    }

    fn row_at(&self, game: &Game<'_>, height: f32) -> Option<usize> {
        let mut bottom = 0.0;
        let entries = &self.pages[self.page];
        for (line, entry) in entries.iter().enumerate() {
            let value = self
                .active
                .as_ref()
                .filter(|(index, _)| *index == line)
                .map_or_else(|| text(entry), |(_, field)| field.value.clone());
            bottom += entry_height(game, &value, entry_width(entry));
            if height < bottom {
                return Some(line);
            }
        }
        if Self::height(game, entries, None) + entry_height(game, " ", 150.0) < PAGE_HEIGHT {
            Some(entries.len())
        } else {
            None
        }
    }

    fn close(mut self) -> Option<Vec<u8>> {
        self.finish_entry();
        let had_entries = self.pages[self.page].iter().any(nonempty);
        let opened = self.pages[..self.page]
            .iter()
            .filter(|page| page.iter().any(nonempty))
            .count() as i32;
        let pages = self
            .pages
            .into_iter()
            .map(|page| page.into_iter().filter(nonempty).collect::<Vec<_>>())
            .filter(|page| !page.is_empty())
            .map(Tag::List)
            .collect();
        packet(
            self.token,
            Compound::from([
                ("pages".into(), Tag::List(pages)),
                (
                    "previously_opened_page".into(),
                    Tag::Int(if had_entries { opened } else { self.remembered }),
                ),
            ]),
        )
    }
}

fn open_editor(game: &mut Game<'_>, target: EditedClipboard, original: Compound) -> bool {
    let Some(player) = game.native_acting_player() else {
        return false;
    };
    let token = SERIAL.with(|serial| {
        let next = serial.get().wrapping_add(1);
        serial.set(next);
        next
    });
    let mut data = original.clone();
    if let EditedClipboard::Placed { pos, .. } = target {
        data.insert("Target".into(), Tag::IntArray(pos.to_vec()));
    }
    let Some(message) = packet(token, data) else {
        return false;
    };
    if game
        .native_net_send_to_player(player.uuid, SCREEN, &message)
        .is_err()
    {
        return false;
    }
    SESSIONS.with_borrow_mut(|sessions| {
        sessions.insert(
            player.uuid,
            Session {
                token,
                target,
                original,
            },
        )
    });
    true
}

pub(super) fn open(game: &mut Game<'_>, stack: &ItemStack, claimed: &mut bool) {
    if *claimed || stack.item.as_ref() != ITEM || game.hand != Hand::Main {
        return;
    }
    let Some(mut original) = content(game, stack) else {
        return;
    };
    original.insert("type".into(), Tag::String("editing".into()));
    let mut held = stack.clone();
    if game
        .native_set_component(&mut held, COMPONENT, Tag::Compound(original.clone()))
        .is_err()
        || !open_editor(game, EditedClipboard::Held(game.selected), original)
    {
        return;
    }
    *game.held_mut() = Some(held);
    game.guest_inventory_resend |= game.lan_acting.is_some();
    game.add_cooldown(ITEM.into(), 10);
    *claimed = true;
}

pub(super) fn open_placed(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if game.hand != Hand::Main || game.native_sneaking() || game.native_block(pos) != ITEM {
        return false;
    }
    let Some(original) = board::stack_at(game, pos).and_then(|stack| content(game, &stack)) else {
        return false;
    };
    open_editor(
        game,
        EditedClipboard::Placed {
            dimension: game.native_dimension(),
            pos,
        },
        original,
    )
}

fn can_reach(game: &mut Game<'_>, [x, y, z]: [i32; 3], buffer: f64) -> bool {
    let Some([ex, ey, ez]) = game.eye_position() else {
        return false;
    };
    let range = game.interaction_range("minecraft:block_interaction_range", 4.5, 5.0) + buffer;
    Aabb::block(BlockPos::new(x, y, z)).distance_squared_to_point(Vec3::new(ex, ey, ez))
        < range * range
}

pub(super) fn receive(game: &mut Game<'_>, channel: &str, data: &[u8]) {
    if channel != SCREEN {
        return;
    }
    let Some((token, content)) = unpack(data) else {
        return;
    };
    let Some(mut pages) = pages(&content) else {
        return;
    };
    if pages.is_empty() {
        pages.push(Vec::new());
    }
    let remembered = int(&content, "previously_opened_page").unwrap_or_default();
    let read_only = int(&content, "read_only") == Some(1);
    if int(&content, "Refresh") == Some(1) {
        if game.native_mod_screen() == Some(SCREEN) {
            EDITOR.with_borrow_mut(|editor| {
                let Some(editor) = editor.as_mut().filter(|editor| editor.token == token) else {
                    return;
                };
                editor.page = editor.page.min(pages.len() - 1);
                editor.pages = pages;
                editor.remembered = remembered;
                editor.read_only = read_only;
                editor.active = None;
                editor.last_click = None;
                editor.dirty = false;
                editor.start_empty_page();
            });
        }
        return;
    }
    if game.native_mod_screen() == Some(SCREEN) || !game.native_mod_screen_open(SCREEN) {
        return;
    }
    let target = match content.get(&"Target".into()) {
        Some(Tag::IntArray(values)) => values.as_slice().try_into().ok(),
        _ => None,
    };
    let mut editor = Editor {
        token,
        target,
        page: (remembered.max(0) as usize).min(pages.len() - 1),
        pages,
        remembered,
        read_only,
        active: None,
        closing: false,
        dirty: false,
        note_sound: None,
        last_click: None,
        shortcuts: Vec::new(),
    };
    editor.start_empty_page();
    EDITOR.replace(Some(editor));
}

fn refresh_other_editors(
    game: &mut Game<'_>,
    author: u128,
    target: EditedClipboard,
    mut state: Compound,
) {
    state.insert("Refresh".into(), Tag::Byte(1));
    let viewers = SESSIONS.with_borrow(|sessions| {
        sessions
            .iter()
            .filter_map(|(&player, session)| {
                (player != author && session.target == target).then_some((player, session.token))
            })
            .collect::<Vec<_>>()
    });
    for (viewer, token) in viewers {
        if let Some(data) = packet(token, state.clone()) {
            let _ = game.native_net_send_to_player(viewer, SCREEN, &data);
        }
    }
}

pub(super) fn save(game: &mut Game<'_>, player: u128, channel: &str, data: &[u8]) {
    if channel != SCREEN {
        return;
    }
    let Some((token, edits)) = unpack(data) else {
        return;
    };
    let Some(pages) = pages(&edits) else {
        return;
    };
    let draft = int(&edits, "Draft") == Some(1);
    let Some(Session {
        target,
        mut original,
        ..
    }) = SESSIONS.with_borrow_mut(|sessions| {
        let session = sessions.get(&player)?;
        if session.token != token {
            return None;
        }
        if draft {
            return matches!(session.target, EditedClipboard::Placed { .. })
                .then(|| session.clone());
        }
        sessions.remove(&player)
    })
    else {
        return;
    };
    if draft && game.native_server_players().len() < 2 {
        return;
    }
    let Some(conn) = game.native_conn(player) else {
        return;
    };
    let contains_click_event = pages.iter().flatten().any(|entry| {
        matches!(entry, Tag::Compound(entry) if entry.get(&"text".into()).is_some_and(has_click_event))
    });
    let content = if pages.is_empty() || contains_click_event {
        None
    } else {
        original.insert("type".into(), Tag::String("written".into()));
        original.insert(
            "pages".into(),
            Tag::List(pages.into_iter().map(Tag::List).collect()),
        );
        if let Some(page) = int(&edits, "previously_opened_page") {
            original.insert("previously_opened_page".into(), Tag::Int(page));
        }
        Some(Tag::Compound(original))
    };
    game.for_player(Target::Guest(conn), |actor| match target {
        EditedClipboard::Held(slot) => {
            let Some(mut stack) = actor
                .stack_in(slot)
                .filter(|stack| stack.item.as_ref() == ITEM)
                .cloned()
            else {
                return;
            };
            let result = match content {
                Some(content) => actor.native_set_component(&mut stack, COMPONENT, content),
                None => actor.native_remove_component(&mut stack, COMPONENT),
            };
            if result.is_ok() {
                *actor.stack_in_mut(slot) = Some(stack);
                actor.guest_inventory_resend |= actor.lan_acting.is_some();
            }
        }
        EditedClipboard::Placed { dimension, pos } => {
            if actor.native_dimension() == dimension
                && actor.native_block(pos) == ITEM
                && can_reach(actor, pos, 20.0)
            {
                board::save_contents(actor, pos, content);
                if let Some(state) = board::stack_at(actor, pos)
                    .and_then(|stack| super::create_clipboard::content(actor, &stack))
                {
                    refresh_other_editors(actor, player, target, state);
                }
            }
        }
    });
}

fn origin([x, y, w, h]: [f32; 4]) -> [f32; 2] {
    [
        x + ((w - 256.0) / 2.0).floor(),
        y + ((h - 256.0) / 2.0).floor() - 8.0,
    ]
}

fn draw_entry(
    game: &Game<'_>,
    batch: &mut HudBatch,
    value: &str,
    field: Option<&EditBox>,
    [x, y]: [f32; 2],
    width: f32,
    green: bool,
) {
    let chars: Vec<_> = value.chars().collect();
    let lines = text_rows(game, &chars, width);
    let color = if green && field.is_none() {
        0xff31b25d
    } else {
        0xff311a00
    };
    for (row, &(from, to)) in lines.iter().enumerate() {
        let y = y + row as f32 * LINE_HEIGHT;
        let width =
            |start, end| game.native_text_width(&chars[start..end].iter().collect::<String>());
        if let Some(field) = field {
            let low = field.cursor.min(field.highlight).max(from);
            let high = field.cursor.max(field.highlight).min(to);
            if low < high {
                game.native_fill(
                    batch,
                    [x + width(from, low), y - 1.0, width(low, high), 10.0],
                    0x660000ff,
                );
            }
        }
        game.native_text(
            batch,
            &chars[from..to].iter().collect::<String>(),
            [x, y],
            color,
            false,
        );
        if let Some(field) = field.filter(|field| field.cursor_visible()) {
            let at = field.cursor;
            let next = lines.get(row + 1).map(|&(start, _)| start);
            if at >= from && next.is_none_or(|next| at < next) {
                let caret = x + width(from, at.min(to));
                if at == chars.len() {
                    game.native_text(batch, "_", [caret, y], 0xff000000, false);
                } else {
                    game.native_fill(batch, [caret, y - 1.0, 1.0, 10.0], 0xff000000);
                }
            }
        }
    }
}

pub(super) fn draw(game: &Game<'_>, screen: &NativeScreenView<'_>, batch: &mut HudBatch) {
    if game.native_mod_screen() != Some(SCREEN) {
        return;
    }
    let [x, y] = origin(screen.rect);
    game.native_sprite(
        batch,
        BACKGROUND,
        [0.0, 0.0, 256.0, 256.0],
        [x, y, 256.0, 256.0],
    );
    EDITOR.with_borrow_mut(|state| {
        let Some(editor) = state else { return };
        game.native_text(
            batch,
            &horizon_protocol::text::format_java(
                &game.translate("book.pageIndicator", "Page %1$s of %2$s"),
                &[
                    (editor.page + 1).to_string(),
                    editor.pages.len().to_string(),
                ],
            ),
            [x + 150.0, y + 9.0],
            0xffefddbc,
            false,
        );
        let mut row = y + 50.0;
        for (line, entry) in editor.pages[editor.page].iter().enumerate() {
            let checked = checked(entry);
            let active = editor
                .active
                .as_ref()
                .filter(|(active, _)| *active == line)
                .map(|(_, field)| field);
            let value = active.map_or_else(|| text(entry), |field| field.value.clone());
            let icon = icon(entry);
            let text_x = x + if icon.is_some() { 74.0 } else { 58.0 };
            let width = entry_width(entry);
            let is_address = value
                .strip_prefix('#')
                .is_some_and(|address| !is_blank(address));
            if is_address {
                let u = if checked { 125.0 } else { 116.0 };
                game.native_sprite(
                    batch,
                    "create:gui/widgets",
                    [u, 7.0, 8.0, 8.0],
                    [x + 44.0, row, 8.0, 8.0],
                );
            } else {
                game.native_text(batch, "□", [x + 45.0, row + 1.0], 0xff8d7f6b, false);
                if checked {
                    game.native_text(batch, "✔", [x + 45.0, row], 0xff31b25d, false);
                }
            }
            if let Some(stack) = &icon {
                game.native_gui_draw_item(batch, stack, [x + 54.0, row]);
            }
            let shown = if is_address && active.is_none() {
                value[1..].trim_start()
            } else {
                &value
            };
            draw_entry(
                game,
                batch,
                shown,
                active,
                [text_x, row],
                width,
                checked && !is_address,
            );
            row += entry_height(game, shown, width);
        }
        let hover = |bx, by, w, h| {
            let [mx, my] = screen.mouse;
            mx >= bx && my >= by && mx < bx + w && my < by + h
        };
        for (show, bx, name) in [
            (editor.page > 0, x + 53.0, "page_backward"),
            (
                editor.page < 50 && (!editor.read_only || editor.page + 1 < editor.pages.len()),
                x + 176.0,
                "page_forward",
            ),
        ] {
            if show {
                let suffix = if hover(bx, y + 229.0, 23.0, 13.0) {
                    "_highlighted"
                } else {
                    ""
                };
                batch.sprite(
                    &game.gui.atlas,
                    &format!("gui/sprites/widget/{name}{suffix}"),
                    bx,
                    y + 229.0,
                );
            }
        }
        let mut tooltip = None;
        for (by, icon_y, tip, fallback) in [
            (
                y + 153.0,
                112.0,
                "create.gui.clipboard.erase_checked",
                "Erase checked items",
            ),
            (y + 175.0, 0.0, "create.station.close", "Close Window"),
        ] {
            let u = if hover(x + 234.0, by, 18.0, 18.0) {
                tooltip = Some(Text::literal(game.translate(tip, fallback)));
                if game
                    .physical_buttons
                    .contains(&winit::event::MouseButton::Left)
                {
                    36.0
                } else {
                    18.0
                }
            } else {
                0.0
            };
            game.native_sprite(
                batch,
                "create:gui/widgets",
                [u, 0.0, 18.0, 18.0],
                [x + 234.0, by, 18.0, 18.0],
            );
            game.native_sprite(
                batch,
                "create:gui/icons",
                [64.0, icon_y, 16.0, 16.0],
                [x + 235.0, by + 1.0, 16.0, 16.0],
            );
        }
        if let Some(tooltip) = tooltip {
            horizon_client::ui::tooltip(
                batch,
                &game.gui.atlas,
                &[tooltip],
                (screen.mouse[0], screen.mouse[1]),
            );
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
    if *canceled || button != 0 || game.native_mod_screen() != Some(SCREEN) {
        return;
    }
    let [x, y] = origin(screen.rect);
    let dx = screen.mouse[0] - x;
    let dy = screen.mouse[1] - y;
    EDITOR.with_borrow_mut(|state| {
        let Some(editor) = state else { return };
        if (234.0..252.0).contains(&dx) && (175.0..193.0).contains(&dy) {
            editor.closing = true;
        } else if (234.0..252.0).contains(&dx) && (153.0..171.0).contains(&dy) {
            editor.finish_entry();
            let entries = &mut editor.pages[editor.page];
            entries.retain(|entry| !checked(entry));
            if entries.is_empty() {
                entries.push(blank_entry());
            }
            editor.dirty = true;
        } else if (229.0..243.0).contains(&dy) && (53.0..76.0).contains(&dx) {
            editor.change_page(false);
        } else if (229.0..243.0).contains(&dy) && (176.0..199.0).contains(&dx) {
            editor.change_page(true);
        } else if (44.0..208.0).contains(&dx)
            && (50.0..235.0).contains(&dy)
            && let Some(line) = editor.row_at(game, dy - 50.0)
        {
            if dx < 57.0 {
                editor.finish_entry();
                if let Some(entry) = editor.pages[editor.page].get_mut(line) {
                    let next = !checked(entry);
                    if let Tag::Compound(values) = entry {
                        values.insert("checked".into(), Tag::Byte(i8::from(next)));
                        editor.dirty = true;
                        editor.note_sound = Some(next);
                    }
                }
            } else if !editor.read_only {
                if line == editor.pages[editor.page].len() {
                    editor.finish_entry();
                    editor.pages[editor.page].push(blank_entry());
                }
                if editor
                    .active
                    .as_ref()
                    .is_none_or(|(active, _)| *active != line)
                {
                    editor.edit_line(line);
                }
                editor.click_cursor(game, [dx, dy], modifiers & 1 != 0);
            }
        }
    });
    *canceled = true;
}

pub(super) fn drag(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    button: i32,
    canceled: &mut bool,
) {
    if *canceled || button != 0 || game.native_mod_screen() != Some(SCREEN) {
        return;
    }
    let [x, y] = origin(screen.rect);
    EDITOR.with_borrow_mut(|state| {
        let Some(editor) = state else { return };
        let Some((_, pos)) = editor.cursor_at(game, [screen.mouse[0] - x, screen.mouse[1] - y])
        else {
            return;
        };
        if let Some((_, field)) = &mut editor.active {
            field.set_cursor(pos, true);
            *canceled = true;
        }
    });
}

pub(super) fn character(game: &Game<'_>, c: char, canceled: &mut bool) {
    if *canceled || game.native_mod_screen() != Some(SCREEN) {
        return;
    }
    EDITOR.with_borrow_mut(|state| {
        if let Some(editor) = state
            && c != '§'
            && !c.is_control()
        {
            editor.edit_value(game, |field| field.insert_text(&c.to_string()));
        }
    });
    *canceled = true;
}

pub(super) fn key(game: &Game<'_>, key: &str, modifiers: u32, canceled: &mut bool) {
    if *canceled || game.native_mod_screen() != Some(SCREEN) || key == "key.keyboard.escape" {
        return;
    }
    let shift = modifiers & 1 != 0;
    let control = modifiers & 10 != 0;
    EDITOR.with_borrow_mut(|state| {
        let Some(editor) = state else { return };
        let letter = key
            .strip_prefix("key.keyboard.")
            .filter(|key| key.len() == 1)
            .and_then(|key| key.chars().next());
        let edit_modifier = modifiers & (if cfg!(target_os = "macos") { 8 } else { 2 }) != 0;
        if let Some(shortcut @ (EditShortcut::Copy | EditShortcut::Cut | EditShortcut::Paste)) =
            edit_shortcut(letter, edit_modifier, shift, modifiers & 4 != 0)
        {
            editor.shortcuts.push(shortcut);
            return;
        }
        match key {
            "key.keyboard.page.up" => editor.change_page(false),
            "key.keyboard.page.down" => editor.change_page(true),
            "key.keyboard.enter" | "key.keyboard.keypad.enter" if !shift && !control => {
                editor.next_line(game)
            }
            "key.keyboard.enter" | "key.keyboard.keypad.enter" if shift => {
                editor.edit_value(game, |field| field.insert_text("\n"))
            }
            "key.keyboard.enter" | "key.keyboard.keypad.enter" => editor.finish_entry(),
            "key.keyboard.backspace" if editor.remove_empty_line() => {}
            _ => editor.edit_value(game, |field| {
                enter_shortcut(game, field, key, shift, control)
            }),
        }
    });
    *canceled = true;
}

pub(super) fn scroll(game: &Game<'_>, delta: f64, canceled: &mut bool) {
    if *canceled || delta == 0.0 || game.native_mod_screen() != Some(SCREEN) {
        return;
    }
    EDITOR.with_borrow_mut(|state| {
        if let Some(editor) = state {
            editor.change_page(delta < 0.0);
        }
    });
    *canceled = true;
}

pub(super) fn tick(game: &mut Game<'_>) {
    let (closed, draft, sound) = EDITOR.with_borrow_mut(|state| {
        if let Some(editor) = state {
            editor.apply_shortcuts(game);
        }
        let sound = state.as_mut().and_then(|editor| editor.note_sound.take());
        if game.native_mod_screen() != Some(SCREEN)
            || state.as_ref().is_some_and(|editor| {
                editor.closing
                    || editor.target.is_some_and(|pos| {
                        game.native_block(pos) != ITEM || !can_reach(game, pos, 10.0)
                    })
            })
        {
            (state.take(), None, sound)
        } else {
            (None, state.as_mut().and_then(Editor::draft), sound)
        }
    });
    if let Some(checked) = sound {
        let mut random = horizon_client::random_source::create();
        let (event, pitch) = if checked {
            ("create:clipboard_check", 0.95 + random.next_float() * 0.05)
        } else {
            ("create:clipboard_erase", 0.90 + random.next_float() * 0.2)
        };
        if std::env::var_os("CREATE_CLIPBOARD_AUDIO_TRACE").is_some() {
            println!("CREATE_CLIPBOARD_AUDIO {event} {pitch}");
        }
        game.audio.play_unshared(event, None, 0.25, pitch);
    }
    if let Some(draft) = draft {
        let _ = game.native_net_send_to_server(SCREEN, &draft);
    }
    if let Some(editor) = closed {
        if let Some(packet) = editor.close() {
            let _ = game.native_net_send_to_server(SCREEN, &packet);
        }
        game.native_mod_screen_close(SCREEN);
    }
}
