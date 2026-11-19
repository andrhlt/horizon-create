use std::cell::RefCell;

use horizon_client::hud::HudBatch;
use horizon_client::mod_api::NativeScreenView;
use horizon_world::nbt::Tag;
use horizon_world::player_inventory::EquipmentSlot;
use serde::{Deserialize, Serialize};

use super::Game;
use super::commands::Target;
use super::create_machines::{int, mod_entity, offset, set_float};
use super::create_threshold_switch::{self, THRESHOLD_SWITCH};

const CHANNEL: &str = "create:stockpile_switch";
const GUI: &str = "create:gui/threshold_switch";
const WIDTH: f32 = 182.0;
const HEIGHT: f32 = 103.0;

#[derive(Clone, Copy, Deserialize, Serialize)]
enum Measurement {
    Items,
    Fluid,
    Custom,
    Unsupported,
}

#[derive(Clone, Deserialize, Serialize)]
struct Settings {
    pos: [i32; 3],
    lower: i32,
    upper: i32,
    inverted: bool,
    stacks: bool,
}

#[derive(Deserialize, Serialize)]
struct Snapshot {
    settings: Settings,
    measurement: Measurement,
    min: i32,
    max: i32,
    target: String,
}

struct Editor {
    view: Snapshot,
    delay: Option<u8>,
    send: bool,
    closing: bool,
}

thread_local! {
    static EDITOR: RefCell<Option<Editor>> = const { RefCell::new(None) };
}

impl Snapshot {
    fn capture(game: &Game<'_>, pos: [i32; 3]) -> Option<Self> {
        let entity = mod_entity(game, pos)?;
        let nbt = &entity.nbt;
        let state = create_threshold_switch::observed_state(
            entity,
            game.world.block(pos[0], pos[1], pos[2]),
        );
        let attachment = game.native_block_state_property(state, "target")?;
        let facing = game.native_block_state_property(state, "facing")?;
        let target = offset(
            pos,
            create_threshold_switch::delta(create_threshold_switch::target(attachment, facing)),
        );
        let measurement = if game
            .world
            .block_entities
            .get(&(target[0], target[1], target[2]))
            .is_some_and(|entity| !entity.slots().is_empty())
        {
            Measurement::Items
        } else if super::create_fluid_tank::storage(game, target).is_some() {
            Measurement::Fluid
        } else if super::create_rope::observed(game, target).is_some() {
            Measurement::Custom
        } else {
            Measurement::Unsupported
        };
        Some(Self {
            settings: Settings {
                pos,
                lower: create_threshold_switch::configured(nbt, "OffBelowAmount", "OffBelow", 64),
                upper: create_threshold_switch::configured(nbt, "OnAboveAmount", "OnAbove", 128),
                inverted: int(nbt, "Inverted") == Some(1),
                stacks: int(nbt, "InStacks") == Some(1),
            },
            measurement,
            min: int(nbt, "CurrentMinAmount").unwrap_or(-1),
            max: int(nbt, "CurrentMaxAmount").unwrap_or(-1),
            target: game.native_block(target),
        })
    }

    fn is_items(&self) -> bool {
        matches!(self.measurement, Measurement::Items)
    }

    fn step(&self) -> i32 {
        match self.measurement {
            Measurement::Fluid => 1000,
            _ if self.settings.stacks => 64,
            _ => 1,
        }
    }

    fn limits(&self, upper: bool) -> (i32, i32) {
        let step = self.step();
        if upper {
            (self.min.saturating_add(step).min(self.max), self.max)
        } else {
            (self.min, self.max.saturating_sub(step).max(self.min))
        }
    }

    fn normalize(&mut self) -> bool {
        if matches!(self.measurement, Measurement::Unsupported) || self.max <= self.min {
            return false;
        }
        let step = self.step();
        let (lower_min, lower_max) = self.limits(false);
        let (upper_min, upper_max) = self.limits(true);
        let lower = (self.settings.lower / step * step).clamp(lower_min, lower_max);
        let upper = (self.settings.upper / step * step).clamp(upper_min, upper_max);
        let changed = self.settings.lower != lower || self.settings.upper != upper;
        self.settings.lower = lower;
        self.settings.upper = upper;
        changed
    }
}

fn open_view(game: &mut Game<'_>, mut view: Snapshot) {
    if game.native_mod_screen() == Some(CHANNEL) || !game.native_mod_screen_open(CHANNEL) {
        return;
    }
    view.normalize();
    EDITOR.with_borrow_mut(|state| {
        *state = Some(Editor {
            view,
            delay: Some(0),
            send: false,
            closing: false,
        });
    });
}

pub(super) fn open(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if game.native_block(pos) != THRESHOLD_SWITCH
        || [EquipmentSlot::MainHand, EquipmentSlot::OffHand]
            .into_iter()
            .any(|hand| {
                game.native_equipment(hand)
                    .is_some_and(|stack| stack.item.as_ref() == "create:wrench")
            })
    {
        return false;
    }
    if game.native_sneaking()
        && [EquipmentSlot::MainHand, EquipmentSlot::OffHand]
            .into_iter()
            .any(|slot| game.native_equipment(slot).is_some())
    {
        return false;
    }
    let Some(view) = Snapshot::capture(game, pos) else {
        return true;
    };
    if let Some(actor) = game.native_acting_player() {
        if let Ok(data) = serde_json::to_vec(&view) {
            let _ = game.native_net_send_to_player(actor.uuid, CHANNEL, &data);
        }
    } else if game.remote.is_none() {
        open_view(game, view);
    }
    true
}

pub(super) fn receive_server(game: &mut Game<'_>, channel: &str, data: &[u8]) {
    if channel == CHANNEL
        && let Ok(view) = serde_json::from_slice::<Snapshot>(data)
    {
        open_view(game, view);
    }
}

fn configure(game: &mut Game<'_>, data: &Settings) {
    if game.native_block(data.pos) != THRESHOLD_SWITCH || !game.may_build() {
        return;
    }
    let in_reach = game.eye_position().is_some_and(|eye| {
        let distance = eye
            .into_iter()
            .zip(data.pos)
            .map(|(coord, block)| {
                let low = f64::from(block);
                (coord - coord.clamp(low, low + 1.0)).powi(2)
            })
            .sum::<f64>();
        distance <= (game.reach() + 20.0).powi(2)
    });
    if !in_reach {
        return;
    }
    let changed = game.native_with_mod_block_entity(data.pos, |entity| {
        let nbt = &mut entity.nbt;
        set_float(nbt, "OffBelowAmount", data.lower as f32);
        set_float(nbt, "OnAboveAmount", data.upper as f32);
        nbt.insert("InStacks".into(), Tag::Byte(i8::from(data.stacks)));
        if (int(nbt, "Inverted") == Some(1)) == data.inverted {
            return None;
        }
        nbt.insert("Inverted".into(), Tag::Byte(i8::from(data.inverted)));
        // The original inversion button changes the output immediately.
        let powered = (int(nbt, "Powered") == Some(1)) != data.inverted;
        nbt.insert("PoweredAfterDelay".into(), Tag::Byte(i8::from(powered)));
        Some(powered)
    });
    if let Some(powered) = changed.flatten() {
        game.native_set_block_property(data.pos, "powered", if powered { "true" } else { "false" });
    }
    if changed.is_some() {
        game.native_block_entity_sync(data.pos);
    }
}

pub(super) fn receive_client(game: &mut Game<'_>, uuid: u128, channel: &str, data: &[u8]) {
    if channel != CHANNEL || data.len() > 256 {
        return;
    }
    let Ok(settings) = serde_json::from_slice::<Settings>(data) else {
        return;
    };
    let Some(conn) = game.lan.as_ref().and_then(|host| {
        host.hub
            .guests
            .iter()
            .find(|guest| guest.uuid == uuid && guest.placed && !guest.released)
            .map(|guest| guest.conn)
    }) else {
        return;
    };
    game.for_player(Target::Guest(conn), |actor| configure(actor, &settings));
}

pub(super) fn tick(game: &mut Game<'_>) {
    let visible = game.native_mod_screen() == Some(CHANNEL);
    let pending = EDITOR.with_borrow_mut(|state| {
        if !visible || state.as_ref().is_some_and(|editor| editor.closing) {
            return state.take().map(|editor| (editor.view.settings, true));
        }
        let editor = state.as_mut()?;
        if let Some(current) = Snapshot::capture(game, editor.view.settings.pos) {
            if game.remote.is_none() {
                editor.view.measurement = current.measurement;
                editor.view.target = current.target;
            }
            if current.max > current.min {
                editor.view.min = current.min;
                editor.view.max = current.max;
            }
            if editor.view.normalize() {
                editor.delay = Some(0);
            }
        }
        if let Some(delay) = editor.delay.as_mut() {
            *delay += 1;
        }
        if editor.delay == Some(20) || editor.send {
            editor.send = false;
            editor.delay = None;
            Some((editor.view.settings.clone(), false))
        } else {
            None
        }
    });
    if let Some((settings, closing)) = pending {
        if game.remote.is_none() {
            configure(game, &settings);
        } else if let Ok(data) = serde_json::to_vec(&settings) {
            let _ = game.native_net_send_to_server(CHANNEL, &data);
        }
        if closing {
            game.native_mod_screen_close(CHANNEL);
        }
    }
}

fn origin([x, y, w, h]: [f32; 4]) -> [f32; 2] {
    [
        x + ((w - WIDTH) / 2.0).floor() - 20.0,
        y + ((h - HEIGHT) / 2.0).floor(),
    ]
}

fn inside([x, y, w, h]: [f32; 4], [mx, my]: [f32; 2]) -> bool {
    mx >= x && mx < x + w && my >= y && my < y + h
}

fn button([x, y]: [f32; 2], flip: bool) -> [f32; 4] {
    [
        x + WIDTH - if flip { 62.0 } else { 33.0 },
        y + HEIGHT - 24.0,
        18.0,
        18.0,
    ]
}

fn threshold([x, y]: [f32; 2], upper: bool, items: bool) -> [f32; 4] {
    [
        x + 48.0,
        y + if upper { 23.0 } else { 47.0 },
        if items { 48.0 } else { 103.0 },
        18.0,
    ]
}

fn units([x, y]: [f32; 2]) -> [f32; 4] {
    [x + 100.0, y + 23.0, 52.0, 42.0]
}

pub(super) fn mouse(game: &Game<'_>, screen: &NativeScreenView<'_>, key: i32, canceled: &mut bool) {
    if *canceled || game.native_mod_screen() != Some(CHANNEL) || key != 0 {
        return;
    }
    let at = origin(screen.rect);
    EDITOR.with_borrow_mut(|state| {
        let Some(editor) = state.as_mut() else {
            return;
        };
        if inside(button(at, false), screen.mouse) {
            editor.closing = true;
            *canceled = true;
        } else if inside(button(at, true), screen.mouse) {
            editor.view.settings.inverted = !editor.view.settings.inverted;
            editor.send = true;
            *canceled = true;
        }
    });
}

pub(super) fn scroll(
    game: &Game<'_>,
    mouse: [f32; 2],
    dy: f64,
    modifiers: u32,
    canceled: &mut bool,
) {
    if *canceled || game.native_mod_screen() != Some(CHANNEL) || dy == 0.0 {
        return;
    }
    let Some(screen) = game.screen_view_now() else {
        return;
    };
    let at = origin(screen.rect);
    EDITOR.with_borrow_mut(|state| {
        let Some(editor) = state.as_mut() else {
            return;
        };
        let view = &mut editor.view;
        if view.is_items() && inside(units(at), mouse) {
            // SelectionScrollInput is reversed: down selects Stacks.
            let stacks = dy < 0.0;
            if view.settings.stacks != stacks {
                view.settings.stacks = stacks;
                if view.normalize() {
                    editor.delay = Some(0);
                }
            }
            *canceled = true;
            return;
        }
        if matches!(view.measurement, Measurement::Unsupported) || view.min > view.max {
            return;
        }
        let Some(upper) = [true, false]
            .into_iter()
            .find(|upper| inside(threshold(at, *upper, view.is_items()), mouse))
        else {
            return;
        };
        let step = view.step();
        let shifted = modifiers & 1 != 0;
        let (min, max) = view.limits(upper);
        let original = if upper {
            view.settings.upper
        } else {
            view.settings.lower
        };
        let mut next =
            original.saturating_add(dy.signum() as i32 * step * if shifted { 10 } else { 1 });
        if shifted {
            next -= next % 5;
        }
        let next = next.clamp(min, max);
        if next != original {
            if upper {
                view.settings.upper = next;
                if view.settings.lower / step >= next / step {
                    view.settings.lower = (next.saturating_sub(step) / step * step).max(view.min);
                }
            } else {
                view.settings.lower = next;
                if view.settings.upper / step <= next / step {
                    view.settings.upper = (next.saturating_add(step) / step * step).min(view.max);
                }
            }
            editor.delay = Some(0);
        }
        *canceled = true;
    });
}

pub(super) fn draw(game: &Game<'_>, screen: &NativeScreenView<'_>, out: &mut HudBatch) {
    if game.native_mod_screen() != Some(CHANNEL) {
        return;
    }
    EDITOR.with_borrow(|state| {
        let Some(editor) = state else {
            return;
        };
        let view = &editor.view;
        let at @ [x, y] = origin(screen.rect);
        game.native_sprite(out, GUI, [0.0, 0.0, WIDTH, HEIGHT], [x, y, WIDTH, HEIGHT]);
        let title = game.translate("create.gui.threshold_switch.title", "Stockpile Switch");
        game.native_text(
            out,
            &title,
            [x + (WIDTH - game.native_text_width(&title)) / 2.0, y + 4.0],
            0x592424,
            false,
        );
        let items = view.is_items();
        for upper in [true, false] {
            let row_y = y + if upper { 21.0 } else { 45.0 };
            game.native_sprite(
                out,
                GUI,
                [0.0, if items { 105.0 } else { 129.0 }, 115.0, 22.0],
                [x + 44.0, row_y, 115.0, 22.0],
            );
            let symbol = if upper { "≥" } else { "≤" };
            let value = if upper {
                view.settings.upper
            } else {
                view.settings.lower
            };
            let value = value / view.step();
            let label = match view.measurement {
                Measurement::Unsupported => symbol.to_owned(),
                Measurement::Fluid => format!(
                    "{symbol} {value} {}",
                    game.translate("create.schedule.condition.threshold.buckets", "Buckets")
                ),
                Measurement::Custom => {
                    let level =
                        game.translate("create.gui.threshold_switch.pulley_y_level", "%1$sy");
                    format!("{symbol} {}", level.replace("%1$s", &value.to_string()))
                }
                Measurement::Items => format!("{symbol} {value}"),
            };
            game.native_text(out, &label, [x + 53.0, row_y + 7.0], 0xffffffff, true);
            if !matches!(view.measurement, Measurement::Unsupported) {
                horizon_client::widgets::record(&label, threshold(at, upper, items), true);
            }
            if items {
                let (key, fallback) = if view.settings.stacks {
                    ("stacks", "Stacks")
                } else {
                    ("items", "Items")
                };
                let measure = game.translate(
                    &format!("create.schedule.condition.threshold.{key}"),
                    fallback,
                );
                game.native_text(out, &measure, [x + 105.0, row_y + 7.0], 0xffffffff, true);
                if upper {
                    horizon_client::widgets::record(&measure, units(at), true);
                }
            }
        }
        let result = mod_entity(game, view.settings.pos)
            .is_some_and(|entity| int(&entity.nbt, "PoweredAfterDelay") == Some(1));
        let highlight_y = y + if view.settings.inverted != result {
            20.0
        } else {
            44.0
        };
        game.native_sprite(
            out,
            GUI,
            [0.0, 153.0, 24.0, 24.0],
            [x + 20.0, highlight_y, 24.0, 24.0],
        );
        for (upper, row_y) in [(true, y + 24.0), (false, y + 50.0)] {
            let model = if view.settings.inverted != upper {
                "create:stockpile_on"
            } else {
                "create:stockpile_off"
            };
            game.native_item_model(
                out,
                "minecraft:redstone_torch",
                model,
                [x + 23.0, row_y],
                16.0,
            );
        }
        if !game.native_item(out, &view.target, [x + 13.0, y + 80.0], 16.0) {
            game.native_item(out, "minecraft:barrier", [x + 13.0, y + 80.0], 16.0);
        }
        game.native_item(
            out,
            THRESHOLD_SWITCH,
            [x + WIDTH + 6.0, y + HEIGHT - 56.0],
            80.0,
        );
        for (flip, icon, label) in [
            (false, [0.0, 16.0, 16.0, 16.0], "Confirm".to_owned()),
            (
                true,
                [128.0, 64.0, 16.0, 16.0],
                game.translate("create.gui.threshold_switch.invert_signal", "Invert Signal"),
            ),
        ] {
            let area = button(at, flip);
            let sprite_x = if inside(area, screen.mouse) {
                18.0
            } else {
                0.0
            };
            game.native_sprite(out, "create:gui/widgets", [sprite_x, 0.0, 18.0, 18.0], area);
            game.native_sprite(
                out,
                "create:gui/icons",
                icon,
                [area[0] + 1.0, area[1] + 1.0, 16.0, 16.0],
            );
            horizon_client::widgets::record(&label, area, true);
        }
    });
}
