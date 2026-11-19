use std::cell::RefCell;
use std::sync::OnceLock;

use horizon_client::text::Text;
use serde::{Deserialize, Serialize};

use super::Game;
use super::create_elevator_floors::Floor;
use super::native_world_draw::NativeWorldDraw;

const BUTTON: &str = "create:block/contraption_controls/button";
const INDICATOR: [&str; 8] = [
    "create:block/contraption_controls/indicator_0",
    "create:block/contraption_controls/indicator_1",
    "create:block/contraption_controls/indicator_2",
    "create:block/contraption_controls/indicator_3",
    "create:block/contraption_controls/indicator_4",
    "create:block/contraption_controls/indicator_5",
    "create:block/contraption_controls/indicator_6",
    "create:block/contraption_controls/indicator_7",
];

const SCROLL: &str = "create:scroll_value";
const CLICK: &str = "create:controller_click";
const START: &str = "create:contraption_assemble";
const CHEST: &str = "create:contraption_assemble_compounded_1";
const STOP: &str = "create:contraption_disassemble";

#[derive(Clone, Serialize, Deserialize)]
pub(super) struct Control {
    pub id: u32,
    pub position: [f64; 3],
    pub yaw: f32,
    pub current: i32,
    pub target: i32,
    pub floors: Vec<Floor>,
}

#[derive(Default)]
struct Animation {
    previous: f32,
    value: f32,
    target: f32,
    previous_button: f32,
    button: f32,
}

impl Animation {
    fn tick(&mut self, floor: i32, target: i32) {
        self.tick_chasers();
        let at_target = floor == target;
        let below = if at_target {
            self.target > 0.0
        } else {
            target <= floor
        };
        if self.target == 0.0 && !at_target {
            let first = if below { 181.0 } else { -181.0 };
            self.set_angle(first);
            self.tick_chasers();
            return;
        }

        let stage = ((self.target % 360.0 + 360.0) % 360.0) as i32 / 45;
        if !at_target || stage != 0 {
            let increment = if stage == if below { 4 } else { 3 } {
                2.25
            } else {
                33.75
            };
            let next = self.target + if below { increment } else { -increment };
            self.target = self.value + angle_difference(self.value, next);
        } else {
            self.set_angle(0.0);
        }
    }

    fn tick_chasers(&mut self) {
        self.previous = self.value;
        self.value += (self.target - self.value).clamp(-45.0, 45.0);
        self.previous_button = self.button;
        self.button = if f64::from(self.button) < 1e-5 {
            0.0
        } else {
            self.button * 0.875
        };
    }

    fn set_angle(&mut self, value: f32) {
        self.previous = self.value;
        self.value = value;
        self.target = value;
    }

    fn frame(&self, partial: f32) -> usize {
        let value = self.previous + partial * angle_difference(self.previous, self.value);
        ((value as i32 / 45).rem_euclid(8)) as usize
    }

    fn press(&mut self) {
        self.previous_button = self.button;
        self.button = 1.0;
    }
}

fn angle_difference(from: f32, to: f32) -> f32 {
    let from = f64::from(from) % 360.0;
    let to = f64::from(to) % 360.0;
    (((to - from) % 360.0 + 540.0) % 360.0 - 180.0) as f32
}

struct Display {
    control: Control,
    previous_position: [f64; 3],
    animation: Animation,
    index: usize,
    tick: i64,
    rendered: bool,
}

thread_local! {
    static CONTROLS: RefCell<Vec<Display>> = const { RefCell::new(Vec::new()) };
}

fn trace() -> bool {
    static ENABLED: OnceLock<bool> = OnceLock::new();
    *ENABLED.get_or_init(|| std::env::var_os("HORIZON_CREATE_ELEVATOR_TRACE").is_some())
}

pub(super) fn models(models: &mut Vec<String>) {
    models.push(BUTTON.into());
    models.extend(INDICATOR.map(String::from));
}

pub(super) fn update(tick: i64, controls: Vec<Control>) {
    CONTROLS.with_borrow_mut(|displays| {
        let mut previous = std::mem::take(displays);
        for control in controls {
            let mut display = previous
                .iter()
                .position(|previous| previous.control.id == control.id && previous.tick <= tick)
                .map(|index| previous.swap_remove(index))
                .unwrap_or_else(|| Display {
                    previous_position: control.position,
                    control: control.clone(),
                    animation: Animation::default(),
                    index: 0,
                    tick: tick - 1,
                    rendered: false,
                });
            display.index = display.index.min(control.floors.len().saturating_sub(1));
            if display.tick < tick {
                display.previous_position = display.control.position;
                display.animation.tick(control.current, control.target);
                display.tick = tick;
                display.rendered = false;
                if trace() {
                    let a = &display.animation;
                    let (short, long, selected) = label(&control, display.index);
                    eprintln!(
                        "CREATE_ELEVATOR_INDICATOR {tick},{},{},{},{},{},{},{},{},{},{},{:?},{:?}",
                        control.id,
                        control.current,
                        control.target,
                        a.previous,
                        a.value,
                        a.target,
                        a.frame(1.0),
                        a.previous_button,
                        a.button,
                        selected,
                        short,
                        long,
                    );
                }
            }
            display.control = control;
            displays.push(display);
        }
    });
}

fn label(control: &Control, index: usize) -> (&str, &str, bool) {
    control
        .floors
        .get(index)
        .map_or(("X", "No Floors", true), |floor| {
            (
                floor.short.as_str(),
                floor.long.as_str(),
                control.target == floor.y,
            )
        })
}

pub(super) fn scroll(game: &mut Game<'_>, id: u32, steps: i32) -> bool {
    let selection = CONTROLS.with_borrow_mut(|displays| {
        let display = displays
            .iter_mut()
            .find(|display| display.control.id == id)?;
        let count = display.control.floors.len();
        let previous = display.index;
        display.index = previous
            .saturating_add_signed(steps as isize)
            .min(count.saturating_sub(1));
        Some((display.index, previous, count, display.control.position))
    });
    let Some((index, previous, count, position)) = selection else {
        return false;
    };
    if index != previous && count != 0 {
        let pitch = 1.0 + 0.5 * index as f32 / count as f32;
        game.audio
            .play_on(7, SCROLL, Some(sound_center(position)), 0.124, pitch);
    }
    true
}

pub(super) fn choose(id: u32) -> Option<Option<i32>> {
    CONTROLS.with_borrow_mut(|displays| {
        let display = displays
            .iter_mut()
            .find(|display| display.control.id == id)?;
        let target = display
            .control
            .floors
            .get(display.index)
            .map(|floor| floor.y);
        if target.is_some_and(|y| y != display.control.target) {
            display.animation.press();
        }
        Some(target)
    })
}

pub(super) fn render(game: &Game<'_>, draw: &mut NativeWorldDraw) {
    CONTROLS.with_borrow_mut(|displays| {
        let original_light = draw.light;
        for display in displays {
            let control = &display.control;
            let partial = draw.partial;
            let at = std::array::from_fn(|i| {
                let previous = display.previous_position[i];
                previous + (control.position[i] - previous) * f64::from(partial)
            });
            let distance = draw
                .camera
                .into_iter()
                .zip(at)
                .map(|(a, b)| (a - b).powi(2))
                .sum::<f64>();
            if distance > 64.0 * 64.0 {
                continue;
            }
            draw.push();
            if !draw.translate_world([at[0] - 0.5, at[1], at[2] - 0.5]) {
                draw.pop();
                continue;
            }
            let (block, sky) = game.native_light(at.map(|coord| coord.floor() as i32));
            draw.light = (u32::from(sky) * 16) | (u32::from(block) * 16 << 8);
            let a = &display.animation;
            let frame = a.frame(partial);
            let button = a.previous_button + partial * (a.button - a.previous_button);
            let depth = -button / 24.0;

            let start = draw.vertices_mut().len();
            draw.push();
            draw.rotate_about([0.0, 1.0, 0.0], control.yaw, [0.5; 3]);
            game.native_draw_model(draw, INDICATOR[frame], 0xFFFFFF);
            draw.translate([0.0, depth, 0.0]);
            game.native_draw_model(draw, BUTTON, 0xFFFFFF);
            draw.pop();

            draw.rotate_about([0.0, 1.0, 0.0], control.yaw + 180.0, [0.5; 3]);
            draw.translate([0.4, 1.125, 0.5]);
            draw.rotate_about([-1.0, 0.0, 0.0], 67.5, [0.0; 3]);
            let (short, long, selected) = label(control, display.index);
            let (bright, dark) = if selected {
                (0xEDEAE5, 0xBBB6B0)
            } else {
                (0xEE9246, 0xD94927)
            };
            let flicker = (draw.game_time as f32 + partial)
                .mul_add(13.0, control.id as f32)
                .sin()
                .abs();
            let color = blend(bright, dark, flicker / 4.0);
            if distance < 100.0 {
                text(
                    game,
                    draw,
                    short,
                    [0.0, 0.15, depth - 0.25],
                    12.0,
                    5.0,
                    color,
                    Some(blend(dark, 0, 0.35)),
                );
            }
            if distance < 20.0 {
                text(
                    game,
                    draw,
                    long,
                    [-0.0635, 0.06, depth - 0.25],
                    55.0,
                    3.0,
                    color,
                    None,
                );
            }
            draw.pop();

            let vertices = draw.vertices_mut().len() - start;
            if trace() && vertices > 0 && !display.rendered {
                display.rendered = true;
                eprintln!(
                    "CREATE_ELEVATOR_RENDER {},{},{frame},{vertices}",
                    display.tick, control.id
                );
            }
        }
        draw.light = original_light;
    });
}

fn blend(a: u32, b: u32, amount: f32) -> u32 {
    [0, 8, 16].into_iter().fold(0, |out, shift| {
        let from = ((a >> shift) & 255) as f32;
        let to = ((b >> shift) & 255) as f32;
        out | (((from + amount * (to - from)) as u32) << shift)
    })
}

fn text(
    game: &Game<'_>,
    draw: &mut NativeWorldDraw,
    label: &str,
    position: [f32; 3],
    minimum: f32,
    divisor: f32,
    color: u32,
    shadow: Option<u32>,
) {
    if label.trim().is_empty() {
        return;
    }
    let width = game.native_text_width(label);
    let layout_width = width.max(minimum);
    let scale = 1.0 / (divisor * (layout_width - 0.5));
    let label = Text::literal(label);
    draw.push();
    draw.translate(position);
    draw.scale([scale, -scale, scale]);
    draw.translate([
        (layout_width - width) / 2.0,
        (layout_width - 8.0) / 2.0,
        0.0,
    ]);
    game.native_draw_text(draw, &label, [0.0, 0.0], color, true, 0);
    if let Some(shadow) = shadow {
        draw.translate([0.5, 0.5, -1.0 / 16.0]);
        game.native_draw_text(draw, &label, [0.0, 0.0], shadow, true, 0);
    }
    draw.pop();
}

fn sound_center(at: [f64; 3]) -> [f64; 3] {
    at.map(|value| value.floor() + 0.5)
}

pub(super) fn play(game: &mut Game<'_>, id: &str, at: [f64; 3], volume: f32, pitch: f32) {
    let at = sound_center(at);
    if game.native_play_sound_in_place(id, at, 4, volume, pitch) {
        trace_sound(game, id, at, volume, pitch);
    }
}

pub(super) fn confirm(game: &mut Game<'_>, at: [f64; 3]) {
    play(game, CLICK, at, 0.35, 1.5);
    play(game, START, at, 0.5 * 0.75, 0.5 * 0.8);
    play(game, CHEST, at, 0.045 * 0.75, 0.74 * 0.8);
}

pub(super) fn arrive(game: &mut Game<'_>, at: [i32; 3]) {
    play(game, STOP, at.map(f64::from), 0.35 * 0.75, 0.75 * 0.8);
}

pub(super) fn disassemble(game: &mut Game<'_>, at: [i32; 3]) {
    play(game, STOP, at.map(f64::from), 0.35, 0.75);
}

pub(super) fn trace_sound(game: &Game<'_>, id: &str, at: [f64; 3], volume: f32, pitch: f32) {
    if trace() {
        let [x, y, z] = at;
        eprintln!(
            "CREATE_ELEVATOR_SOUND {},{id},{x},{y},{z},{volume},{pitch}",
            game.world.game_time
        );
    }
}
