use std::cell::{Cell, RefCell};

use horizon_client::{hud::HudBatch, mod_api::NativeScreenView, text::Text};

use super::{
    Game,
    create_toolbox_links::{CHANNEL, Hotbar, Link, RANGE_SQUARED, Reply, Request, distance},
};

const SCREEN: &str = "create:toolbox_radial";
const WIDGETS: &str = "create:gui/widgets";
const ICONS: &str = "create:gui/icons";
const DEPOSIT: i32 = -7;
const UNEQUIP: i32 = -5;
const NONE: i32 = -1;

struct Radial {
    view: Reply,
    box_index: Option<usize>,
    detached: bool,
    scroll: Option<usize>,
}

thread_local! {
    static HUD_LINKS: Cell<Hotbar> = const { Cell::new([None; 9]) };
    static PRESSED: Cell<bool> = const { Cell::new(false) };
    static RADIAL: RefCell<Option<Radial>> = const { RefCell::new(None) };
    static PENDING: Cell<Option<i32>> = const { Cell::new(None) };
}

fn send(game: &mut Game<'_>, request: Request) {
    if let Ok(packet) = serde_json::to_vec(&request) {
        let _ = game.native_net_send_to_server(CHANNEL, &packet);
    }
}

fn binding(game: &Game<'_>) -> String {
    game.native_mod_key("create", "toolbelt", "key.keyboard.left.alt")
}

pub(super) fn key(game: &mut Game<'_>, key: &str, pressed: bool) {
    if key != binding(game) {
        return;
    }
    PRESSED.set(pressed);
    if pressed {
        if game.screen == super::Screen::Playing {
            send(game, Request::Browse);
        }
    } else if game.native_mod_screen() == Some(SCREEN) {
        let [x, y] = game.native_cursor();
        let target = RADIAL.with_borrow(|state| {
            state
                .as_ref()
                .map_or(NONE, |state| target(game, state, [x, y]))
        });
        finish(game, target);
    }
}

pub(super) fn receive(game: &mut Game<'_>, channel: &str, data: &[u8]) {
    if channel != CHANNEL {
        return;
    }
    let Ok(view) = serde_json::from_slice::<Reply>(data) else {
        return;
    };
    HUD_LINKS.set(view.links);
    if !PRESSED.get() || !view.browse || (view.boxes.is_empty() && view.link.is_none()) {
        return;
    }
    if game.native_mod_screen_open(SCREEN) {
        let box_index = view
            .link
            .and_then(|link| view.boxes.iter().position(|choice| choice.pos == link.pos))
            .or_else(|| (view.link.is_none() && view.boxes.len() == 1).then_some(0));
        let detached = view.link.is_some() && box_index.is_none();
        RADIAL.set(Some(Radial {
            view,
            box_index,
            detached,
            scroll: None,
        }));
    }
}

fn relative(game: &Game<'_>, [x, y]: [f32; 2]) -> [f32; 2] {
    let (width, height) = game.gui_size();
    [x - (width / 2.0).floor(), y - (height / 2.0).floor()]
}

fn target(game: &Game<'_>, state: &Radial, at: [f32; 2]) -> i32 {
    let [x, y] = relative(game, at);
    if state.detached {
        return if x.abs() < 20.0 && (-80.0..-20.0).contains(&y) {
            UNEQUIP
        } else {
            NONE
        };
    }
    let squared = x * x + y * y;
    if let Some(index) = state.scroll.filter(|_| squared <= 150.0) {
        return index as i32;
    }
    if (60.0..100.0).contains(&x) && y.abs() < 20.0 {
        DEPOSIT
    } else if state.view.link.is_some() && squared <= 150.0 {
        UNEQUIP
    } else if (25.0..10_000.0).contains(&squared) {
        ((y.atan2(x).to_degrees() + 517.5).floor() as i32 % 360) / 45
    } else {
        NONE
    }
}

fn active(state: &Radial, slot: usize) -> bool {
    if let Some(choice) = state.box_index {
        state.view.boxes[choice].compartments[slot]
            .as_ref()
            .is_some_and(|(_, count)| *count > 0)
    } else {
        !state.detached && slot < state.view.boxes.len()
    }
}

fn finish(game: &mut Game<'_>, target: i32) {
    let request = RADIAL.with_borrow_mut(|state| {
        let state = state.take()?;
        let slot = state.view.selected;
        if target == DEPOSIT && !state.detached {
            let mut boxes = state.view.boxes;
            let positions = if let Some(index) = state.box_index {
                vec![boxes.swap_remove(index).pos]
            } else {
                boxes.into_iter().map(|choice| choice.pos).collect()
            };
            return Some(Request::Deposit { positions });
        }
        if target == UNEQUIP && state.view.link.is_some() {
            return Some(Request::Unequip { slot });
        }
        let compartment = usize::try_from(target).ok().filter(|target| *target < 8)?;
        let choice = state.box_index?;
        active(&state, compartment).then_some(Request::Equip {
            slot,
            link: Link {
                pos: state.view.boxes[choice].pos,
                compartment,
            },
        })
    });
    if let Some(request) = request {
        send(game, request);
    }
    game.native_mod_screen_close(SCREEN);
}

fn choose(game: &mut Game<'_>, target: i32) {
    if target == NONE {
        return;
    }
    let opened = RADIAL.with_borrow_mut(|state| {
        let Some(state) = state.as_mut() else {
            return false;
        };
        if state.box_index.is_none()
            && !state.detached
            && let Ok(slot) = usize::try_from(target)
            && slot < state.view.boxes.len()
        {
            state.box_index = Some(slot);
            state.scroll = None;
            return true;
        }
        false
    });
    if !opened {
        finish(game, target);
    }
}

pub(super) fn client_tick(game: &mut Game<'_>) {
    if game.native_mod_screen() != Some(SCREEN) {
        RADIAL.set(None);
        PENDING.set(None);
        return;
    }
    if let Some(target) = PENDING.take() {
        choose(game, target);
    }
}

pub(super) fn click(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    button: i32,
    canceled: &mut bool,
) {
    if game.native_mod_screen() != Some(SCREEN) {
        return;
    }
    *canceled = true;
    if button == 0 {
        let target = RADIAL.with_borrow(|state| {
            state
                .as_ref()
                .map_or(NONE, |state| target(game, state, screen.mouse))
        });
        PENDING.set(Some(target));
    } else if button == 1 {
        RADIAL.with_borrow_mut(|state| {
            if let Some(state) = state.as_mut().filter(|state| state.view.boxes.len() > 1) {
                state.box_index = None;
                state.scroll = None;
            }
        });
    }
}

pub(super) fn screen_key(game: &Game<'_>, key: &str, canceled: &mut bool) {
    if game.native_mod_screen() != Some(SCREEN) {
        return;
    }
    let number = key
        .strip_prefix("key.keyboard.")
        .and_then(|name| name.parse::<usize>().ok());
    let Some(slot) = number
        .and_then(|slot| slot.checked_sub(1))
        .filter(|&slot| slot < 8)
    else {
        return;
    };
    if RADIAL.with_borrow(|state| state.as_ref().is_some_and(|state| active(state, slot))) {
        *canceled = true;
        PENDING.set(Some(slot as i32));
    }
}

pub(super) fn scroll(game: &Game<'_>, screen: &NativeScreenView<'_>, dy: f64, canceled: &mut bool) {
    if game.native_mod_screen() != Some(SCREEN) || dy == 0.0 {
        return;
    }
    let [x, y] = relative(game, screen.mouse);
    if x * x + y * y > 150.0 {
        return;
    }
    RADIAL.with_borrow_mut(|state| {
        if let Some(state) = state.as_mut().filter(|state| !state.detached) {
            let previous = state
                .scroll
                .or_else(|| state.view.link.map(|link| link.compartment))
                .unwrap_or(0);
            let delta = if dy > 0.0 { -1 } else { 1 };
            state.scroll = (1..=8)
                .map(|offset| (previous as i32 + offset * delta).rem_euclid(8) as usize)
                .find(|&slot| active(state, slot));
            *canceled = true;
        }
    });
}

fn slot_frame(
    game: &Game<'_>,
    batch: &mut HudBatch,
    at: [f32; 2],
    source: [f32; 2],
    highlighted: bool,
) {
    let [x, y] = at;
    game.native_sprite(
        batch,
        WIDGETS,
        [source[0], source[1], 22.0, 22.0],
        [x - 12.0, y - 12.0, 22.0, 22.0],
    );
    if highlighted {
        game.native_sprite(
            batch,
            WIDGETS,
            [27.0, 67.0, 24.0, 24.0],
            [x - 13.0, y - 13.0, 24.0, 24.0],
        );
    }
}

fn icon(game: &Game<'_>, batch: &mut HudBatch, [x, y]: [f32; 2], [u, v]: [f32; 2]) {
    game.native_sprite(
        batch,
        ICONS,
        [u, v, 16.0, 16.0],
        [x - 9.0, y - 9.0, 16.0, 16.0],
    );
}

pub(super) fn draw(game: &Game<'_>, screen: &NativeScreenView<'_>, batch: &mut HudBatch) {
    if game.native_mod_screen() != Some(SCREEN) {
        return;
    }
    let (width, height) = game.gui_size();
    let center = [(width / 2.0).floor(), (height / 2.0).floor()];
    RADIAL.with_borrow(|state| {
        let Some(state) = state.as_ref() else { return };
        let hovered = target(game, state, screen.mouse);
        let mut tip = None;
        let [cx, cy] = center;
        if state.detached {
            slot_frame(game, batch, center, [52.0, 98.0], false);
            game.native_item(batch, "create:brown_toolbox", [cx - 9.0, cy - 9.0], 16.0);
            slot_frame(
                game,
                batch,
                [cx, cy - 40.0],
                [0.0, 68.0],
                hovered == UNEQUIP,
            );
            icon(game, batch, [cx, cy - 40.0], [128.0, 160.0]);
            tip = Some(
                Text::translate(
                    if hovered == UNEQUIP {
                        "create.toolbox.detach"
                    } else {
                        "create.toolbox.outOfRange"
                    },
                    &[],
                )
                .plain(),
            );
        } else {
            slot_frame(
                game,
                batch,
                [cx + 80.0, cy],
                [0.0, 68.0],
                hovered == DEPOSIT,
            );
            icon(game, batch, [cx + 80.0, cy], [176.0, 48.0]);
            if hovered == DEPOSIT {
                let key = if state.box_index.is_some() {
                    "create.toolbox.depositBox"
                } else {
                    "create.toolbox.depositAll"
                };
                tip = Some(Text::translate(key, &[]).plain());
            }
            for index in 0..8 {
                let angle = (index as f32 * 45.0 - 45.0).to_radians();
                let at = [cx + angle.sin() * 40.0, cy - angle.cos() * 40.0];
                let enabled = active(state, index);
                let highlighted = hovered == index as i32 && enabled;
                let (item, label) = if let Some(choice) = state.box_index {
                    let entry = state.view.boxes[choice].compartments[index].as_ref();
                    let item = entry.map(|(item, _)| item.as_str());
                    let label = item.map(|item| game.pack.names.display_item(item));
                    (item, label)
                } else {
                    let choice = state.view.boxes.get(index);
                    (
                        choice.map(|item| item.item.as_str()),
                        choice.map(|item| item.title.clone()),
                    )
                };
                let sprite = if enabled {
                    [0.0, 68.0]
                } else if item.is_some() {
                    [52.0, 98.0]
                } else {
                    [27.0, 98.0]
                };
                slot_frame(game, batch, at, sprite, highlighted);
                if let Some(item) = item {
                    game.native_item(batch, item, [at[0] - 9.0, at[1] - 9.0], 16.0);
                }
                if highlighted {
                    tip = label;
                }
            }
            if state.view.link.is_some() {
                slot_frame(game, batch, center, [0.0, 68.0], hovered == UNEQUIP);
                icon(game, batch, center, [128.0, 64.0]);
                let item = game.held().map_or_else(
                    || Text::literal(""),
                    |stack| Text::literal(game.pack.names.display_item(&stack.item)),
                );
                let label = Text::translate("create.toolbox.unequip", &[item]).plain();
                horizon_client::widgets::record(&label, [cx - 11.0, cy - 11.0, 22.0, 22.0], true);
                if hovered == UNEQUIP {
                    tip = Some(label);
                }
            }
        }
        if let Some(tip) = tip {
            let x = cx - game.native_text_width(&tip) / 2.0;
            game.native_text(batch, &tip, [x, cy - 78.0], 0xffffff, true);
        }
    });
}

pub(super) fn clear() {
    HUD_LINKS.set([None; 9]);
    PRESSED.set(false);
    RADIAL.set(None);
    PENDING.set(None);
}

pub(super) fn hud(game: &Game<'_>, batch: &mut HudBatch) {
    if game.spectator() || game.screen != super::Screen::Playing {
        return;
    }
    let Some(player) = game.player.as_ref() else {
        return;
    };
    let (width, height) = game.gui_size();
    let feet = [player.position.x, player.position.y, player.position.z];
    for (slot, link) in HUD_LINKS.get().into_iter().enumerate() {
        let Some(link) = link else { continue };
        let selected = game.selected == slot;
        let near = distance(feet, link.pos) < RANGE_SQUARED;
        let size = if selected { [22.0, 22.0] } else { [20.0, 24.0] };
        let sprite_x = if near { size[0] } else { 0.0 };
        let sprite_y = if selected { 155.0 } else { 130.0 };
        let offset = if selected { 1.0 } else { 0.0 };
        let x = (width / 2.0).floor() - 90.0 + 20.0 * slot as f32 - offset;
        let y = height - 23.0 + offset;
        game.native_sprite(
            batch,
            WIDGETS,
            [sprite_x, sprite_y, size[0], size[1]],
            [x, y, size[0], size[1]],
        );
    }
}
