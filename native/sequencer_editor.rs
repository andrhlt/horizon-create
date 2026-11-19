use std::cell::RefCell;

use horizon_client::hud::HudBatch;
use horizon_client::mod_api::NativeScreenView;
use horizon_world::player_inventory::EquipmentSlot;
use serde::{Deserialize, Serialize};

use super::Game;
use super::commands::Target;
use super::create_machines::{axis_index, mod_entity};
use super::create_sequencer::{self, Instruction, Mode, SEQUENCER};

const CHANNEL: &str = "create:sequenced_gearshift";
const ATLAS: &str = "create:gui/sequencer";
const ICONS: &str = "create:gui/icons";
const WIDGETS: &str = "create:gui/widgets";
const WIDTH: f32 = 173.0;
const HEIGHT: f32 = 161.0;
const MODES: [Mode; 5] = [
    Mode::TurnAngle,
    Mode::TurnDistance,
    Mode::Delay,
    Mode::Await,
    Mode::End,
];
const SPEEDS: [i32; 4] = [2, 1, -1, -2];
const CAPACITY: usize = 5;

#[derive(Deserialize, Serialize)]
struct Program {
    pos: [i32; 3],
    rows: Vec<Instruction>,
}

struct Editor {
    program: Program,
    closing: bool,
}

thread_local! {
    static EDITOR: RefCell<Option<Editor>> = const { RefCell::new(None) };
}

pub(super) fn open(game: &mut Game<'_>, pos: [i32; 3], face: [i32; 3]) -> bool {
    if game.native_block(pos) != SEQUENCER {
        return false;
    }
    // A wrench claims the click even if the engine is checking the other hand.
    let main = game.native_equipment(EquipmentSlot::MainHand);
    let off = game.native_equipment(EquipmentSlot::OffHand);
    if (game.native_sneaking() && (main.is_some() || off.is_some()))
        || [main.as_ref(), off.as_ref()]
            .into_iter()
            .flatten()
            .any(|stack| stack.item.as_ref() == "create:wrench")
    {
        return false;
    }
    if let Some(stack) = game.held() {
        let shaft_side = if game.native_block_property(pos, "vertical").as_deref() == Some("true") {
            face[1] != 0
        } else {
            game.native_block_property(pos, "axis")
                .and_then(|axis| axis_index(&axis))
                .is_some_and(|axis| face[axis] != 0)
        };
        if shaft_side
            && game
                .native_server_item_in_tag(stack, "create:kinetic_items")
                .unwrap_or(false)
        {
            return false;
        }
    }
    if let Some(player) = game.native_acting_player() {
        let rows = create_sequencer::program(mod_entity(game, pos));
        if let Ok(data) = serde_json::to_vec(&Program { pos, rows }) {
            let _ = game.native_net_send_to_player(player.uuid, CHANNEL, &data);
        }
    }
    true
}

pub(super) fn receive_server(game: &mut Game<'_>, channel: &str, data: &[u8]) {
    if channel == CHANNEL
        && game.native_mod_screen() != Some(CHANNEL)
        && let Ok(program) = serde_json::from_slice::<Program>(data)
        && game.native_mod_screen_open(CHANNEL)
    {
        EDITOR.with_borrow_mut(|editor| {
            *editor = Some(Editor {
                program,
                closing: false,
            })
        });
    }
}

pub(super) fn receive_client(game: &mut Game<'_>, uuid: u128, channel: &str, data: &[u8]) {
    if channel != CHANNEL || data.len() > 512 {
        return;
    }
    let Ok(program) = serde_json::from_slice::<Program>(data) else {
        return;
    };
    if program.rows.is_empty() || program.rows.len() > CAPACITY || !program.rows.iter().all(valid) {
        return;
    }
    let Some(conn) = game.lan.as_ref().and_then(|host| {
        host.hub
            .guests
            .iter()
            .find(|player| player.uuid == uuid && player.placed && !player.released)
            .map(|player| player.conn)
    }) else {
        return;
    };
    game.for_player(Target::Guest(conn), |actor| {
        if !actor.may_build() || actor.native_block(program.pos) != SEQUENCER {
            return;
        }
        if let Some(eye) = actor.eye_position() {
            let distance = eye
                .into_iter()
                .zip(program.pos)
                .map(|(coord, block)| {
                    let low = f64::from(block);
                    (coord - coord.clamp(low, low + 1.0)).powi(2)
                })
                .sum::<f64>();
            if distance <= (actor.reach() + 20.0).powi(2) {
                create_sequencer::set_program(actor, program.pos, &program.rows);
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
        if let Ok(data) = serde_json::to_vec(&editor.program) {
            let _ = game.native_net_send_to_server(CHANNEL, &data);
        }
        game.native_mod_screen_close(CHANNEL);
    }
}

fn parameter(mode: Mode) -> Option<(i32, i32, i32, &'static str, &'static str)> {
    match mode {
        Mode::TurnAngle => Some((90, 360, 45, "turn_angle.angle", "Angle")),
        Mode::TurnDistance => Some((5, 128, 5, "turn_distance.distance", "Distance")),
        Mode::Delay => Some((10, 600, 20, "delay.duration", "Duration")),
        _ => None,
    }
}

fn valid(row: &Instruction) -> bool {
    SPEEDS.contains(&row.modifier)
        && parameter(row.mode).is_none_or(|(_, max, ..)| (1..=max).contains(&row.value))
}

fn has_speed(mode: Mode) -> bool {
    matches!(mode, Mode::TurnAngle | Mode::TurnDistance)
}

fn position([x, y, w, h]: [f32; 4]) -> [f32; 2] {
    [
        x + ((w - WIDTH) / 2.0).floor() - 20.0,
        y + ((h - HEIGHT) / 2.0).floor(),
    ]
}

fn within([x, y, w, h]: [f32; 4], [mx, my]: [f32; 2]) -> bool {
    mx >= x && mx < x + w && my >= y && my < y + h
}

fn confirm([x, y]: [f32; 2]) -> [f32; 4] {
    [x + WIDTH - 33.0, y + HEIGHT - 24.0, 18.0, 18.0]
}

fn fields([x, y]: [f32; 2], row: usize) -> [[f32; 4]; 3] {
    let top = y + 20.0 + row as f32 * 22.0;
    [
        [x + 30.0, top, 50.0, 18.0],
        [x + 88.0, top, 28.0, 18.0],
        [x + 118.0, top, 28.0, 18.0],
    ]
}

fn name(mode: Mode) -> (&'static str, &'static str, f32) {
    match mode {
        Mode::TurnAngle => ("turn_angle", "Turn", 16.0),
        Mode::TurnDistance => ("turn_distance", "Piston", 16.0),
        Mode::Delay => ("delay", "Delay", 60.0),
        Mode::Await => ("await", "Await", 162.0),
        Mode::End => ("end", "End", 82.0),
    }
}

fn value_label(game: &Game<'_>, row: Instruction) -> String {
    match row.mode {
        Mode::TurnAngle => format!(
            "{}{}",
            row.value,
            game.translate("create.generic.unit.degrees", "°")
        ),
        Mode::TurnDistance => format!("{}m", row.value),
        Mode::Delay if row.value >= 20 => format!("{}s", row.value / 20),
        Mode::Delay => format!("{}t", row.value),
        _ => String::new(),
    }
}

pub(super) fn draw(game: &Game<'_>, screen: &NativeScreenView<'_>, out: &mut HudBatch) {
    if game.native_mod_screen() != Some(CHANNEL) {
        return;
    }
    EDITOR.with_borrow(|editor| {
        let Some(editor) = editor else { return };
        let [x, y] = position(screen.rect);
        game.native_sprite(out, ATLAS, [0.0, 0.0, WIDTH, HEIGHT], [x, y, WIDTH, HEIGHT]);
        for index in 0..CAPACITY {
            let row_top = y + 16.0 + index as f32 * 22.0;
            let row = editor.program.rows.get(index).copied();
            let sprite_y = row.map_or(104.0, |row| name(row.mode).2);
            game.native_sprite(
                out,
                ATLAS,
                [0.0, sprite_y, 162.0, 22.0],
                [x, row_top, 162.0, 22.0],
            );
            let Some(row) = row else { continue };
            let [kind_control, value_control, direction_control] = fields([x, y], index);
            let (key, short, _) = name(row.mode);
            let text = game.translate(
                &format!("create.gui.sequenced_gearshift.instruction.{key}"),
                short,
            );
            let line = row_top + 9.0;
            game.native_text(out, &text, [x + 36.0, line], 0xffffee, true);
            horizon_client::widgets::record(&format!("{}: {text}", index + 1), kind_control, true);
            if let Some((_, _, _, key, short)) = parameter(row.mode) {
                let text = value_label(game, row);
                let label = game.translate(
                    &format!("create.gui.sequenced_gearshift.instruction.{key}"),
                    short,
                );
                game.native_text(
                    out,
                    &text,
                    [x + 102.0 - game.native_text_width(&text) / 2.0, line],
                    0xffffee,
                    true,
                );
                horizon_client::widgets::record(&format!("{label}: {text}"), value_control, true);
            }
            if has_speed(row.mode) {
                let glyph = match row.modifier {
                    2 => ">>",
                    -1 => "<-",
                    -2 => "<<",
                    _ => "->",
                };
                game.native_text(out, glyph, [x + 127.0, line], 0xffffee, true);
                horizon_client::widgets::record(
                    &format!("Speed, Direction: {glyph}"),
                    direction_control,
                    true,
                );
            }
        }
        let title = game.translate(
            "create.gui.sequenced_gearshift.title",
            "Sequenced Gearshift",
        );
        game.native_text(
            out,
            &title,
            [
                x + (WIDTH - 8.0 - game.native_text_width(&title)) / 2.0,
                y + 4.0,
            ],
            0x592424,
            false,
        );
        let ok = confirm([x, y]);
        let sprite_x = if within(ok, screen.mouse) { 18.0 } else { 0.0 };
        game.native_sprite(out, WIDGETS, [sprite_x, 0.0, 18.0, 18.0], ok);
        game.native_sprite(
            out,
            ICONS,
            [0.0, 16.0, 16.0, 16.0],
            [ok[0] + 1.0, ok[1] + 1.0, 16.0, 16.0],
        );
        horizon_client::widgets::record("Confirm", ok, true);
        game.native_item(out, SEQUENCER, [x + WIDTH + 6.0, y + HEIGHT - 56.0], 80.0);
    });
}

pub(super) fn mouse(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    button: i32,
    canceled: &mut bool,
) {
    if !*canceled
        && game.native_mod_screen() == Some(CHANNEL)
        && button == 0
        && within(confirm(position(screen.rect)), screen.mouse)
    {
        EDITOR.with_borrow_mut(|state| {
            if let Some(editor) = state.as_mut() {
                editor.closing = true;
            }
        });
        *canceled = true;
    }
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
    let Some(renderer) = game.renderer.as_ref() else {
        return;
    };
    let batch = HudBatch::new([renderer.config.width, renderer.config.height]);
    let origin = position([0.0, 0.0, batch.width, batch.height]);
    let delta = dy.signum() as i32;
    let shift = modifiers & 1 != 0;
    EDITOR.with_borrow_mut(|editor| {
        let Some(editor) = editor else { return };
        for index in 0..editor.program.rows.len() {
            let row = &mut editor.program.rows[index];
            let [kind, value, speed] = fields(origin, index);
            if within(kind, mouse) {
                let current = MODES
                    .iter()
                    .position(|mode| *mode == row.mode)
                    .unwrap_or_default();
                let changed = (current as i32 + delta).clamp(0, MODES.len() as i32 - 1) as usize;
                if current != changed {
                    row.mode = MODES[changed];
                    row.value = parameter(row.mode).map_or(-1, |(default, ..)| default);
                    if row.mode == Mode::End {
                        editor.program.rows.truncate(index + 1);
                    } else if index + 1 == editor.program.rows.len()
                        && editor.program.rows.len() < CAPACITY
                    {
                        editor.program.rows.push(Instruction {
                            mode: Mode::End,
                            value: 1,
                            modifier: 1,
                        });
                    }
                }
            } else if within(value, mouse)
                && let Some((_, max, shift_step, ..)) = parameter(row.mode)
            {
                let step = if row.mode == Mode::Delay {
                    let below_second = row.value - i32::from(delta < 0) < 20;
                    match (below_second, shift) {
                        (true, false) => 1,
                        (true, true) | (false, false) => 20,
                        (false, true) => 100,
                    }
                } else if shift {
                    shift_step
                } else {
                    1
                };
                row.value = (row.value + delta * step).clamp(1, max);
            } else if within(speed, mouse) && has_speed(row.mode) {
                let current = SPEEDS
                    .iter()
                    .position(|speed| *speed == row.modifier)
                    .unwrap_or(1);
                row.modifier =
                    SPEEDS[(current as i32 + delta).clamp(0, SPEEDS.len() as i32 - 1) as usize];
            } else {
                continue;
            }
            *canceled = true;
            break;
        }
    });
}
