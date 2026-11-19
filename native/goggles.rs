use std::cell::Cell;
use std::sync::OnceLock;

use crate::containers::ModBlockEntity;
use horizon_client::hud::{HudBatch, rgba};
use horizon_client::text::{
    AQUA, DARK_GRAY, GOLD, GRAY, GREEN, LIGHT_PURPLE, RED, Style, Text, WHITE, YELLOW,
};
use horizon_world::player_inventory::EquipmentSlot;

use super::Game;
use super::create_analog_lever::{LEVER, strength};
use super::create_chain_conveyor_packages::BLOCKED_EXPORT;
use super::create_machines::{
    FROGPORT, SPEEDOMETER, STRESSOMETER, int, mod_entity, network_values,
};

const GOGGLES: &str = "create:goggles";

thread_local! {
    static HOVER_FRAMES: Cell<u8> = const { Cell::new(0) };
}

pub(super) fn draw(game: &Game<'_>, batch: &mut HudBatch) {
    let Some(lines) = target(game).and_then(|entity| readout(game, &entity.id, &entity.nbt)) else {
        HOVER_FRAMES.set(0);
        return;
    };
    trace(game.world.game_time, &lines);
    let frames = (HOVER_FRAMES.get() + 1).min(24);
    HOVER_FRAMES.set(frames);
    let fade = ((f32::from(frames) + game.clock.fraction() as f32) / 24.0).min(1.0);
    let atlas = &game.gui.atlas;
    let width = lines
        .iter()
        .map(|line| atlas.font.width_text(line))
        .fold(0.0, f32::max);
    let height = if lines.len() == 1 {
        8.0
    } else {
        lines.len() as f32 * 10.0
    };
    let left = ((batch.width / 2.0).floor() + 20.0).min(batch.width - width - 20.0);
    let top = (batch.height / 2.0)
        .floor()
        .min(batch.height - height - 20.0);
    let shift = (1.0 - fade).powi(3) * 8.0;
    let x = left + 12.0 + shift;
    let y = (top - 12.0).max(4.0);
    let background = rgba(16, 0, 16, (180.0 * fade) as u8);
    let border_top = rgba(80, 0, 255, (80.0 * fade) as u8);
    let border_bottom = rgba(40, 0, 127, (80.0 * fade) as u8);

    batch.fill(atlas, x - 3.0, y - 4.0, width + 6.0, 1.0, background);
    batch.fill(
        atlas,
        x - 4.0,
        y - 3.0,
        width + 8.0,
        height + 6.0,
        background,
    );
    batch.fill(
        atlas,
        x - 3.0,
        y + height + 3.0,
        width + 6.0,
        1.0,
        background,
    );
    batch.fill(atlas, x - 3.0, y - 3.0, width + 6.0, 1.0, border_top);
    batch.fill(
        atlas,
        x - 3.0,
        y + height + 2.0,
        width + 6.0,
        1.0,
        border_bottom,
    );
    for edge in [x - 3.0, x + width + 2.0] {
        batch.fill_gradient(
            atlas,
            (edge, y - 2.0, 1.0, height + 4.0),
            border_top,
            border_bottom,
        );
    }
    for (index, line) in lines.iter().enumerate() {
        let offset = if index == 0 {
            0.0
        } else {
            2.0 + index as f32 * 10.0
        };
        batch.text_styled(atlas, line, x, y + offset, u32::MAX, true);
    }
    game.native_item(batch, GOGGLES, [left + 10.0 + shift, top - 16.0], 16.0);
}

fn target<'a>(game: &'a Game<'_>) -> Option<&'a ModBlockEntity> {
    if game.spectator() {
        return None;
    }
    let hit = game.pick()?;
    if game.pick_entity_hit().is_some() {
        return None;
    }
    let entity = mod_entity(game, hit.pos)?;
    (entity.id == FROGPORT
        || game
            .native_equipment(EquipmentSlot::Head)
            .is_some_and(|item| item.item.as_ref() == GOGGLES))
    .then_some(entity)
}

fn readout(game: &Game<'_>, id: &str, nbt: &horizon_world::nbt::Compound) -> Option<Vec<Text>> {
    match id {
        FROGPORT if int(nbt, BLOCKED_EXPORT) == Some(1) => {
            let title = label("create.hint.blocked_frogport.title").with_color(GOLD);
            let body = label("create.hint.blocked_frogport").plain();
            let text = body
                .split('_')
                .enumerate()
                .fold(Text::empty(), |text, (i, segment)| {
                    text.append(Text::colored(
                        segment,
                        if i % 2 == 0 { GRAY } else { WHITE },
                    ))
                });
            let mut lines = vec![indented(title, 0)];
            lines.extend(
                game.gui
                    .atlas
                    .font
                    .split(&text, 200.0)
                    .into_iter()
                    .map(|line| indented(line, 0)),
            );
            Some(lines)
        }
        LEVER => Some(vec![indented(
            Text::translate_with_fallback(
                "create.tooltip.analogStrength",
                "Analog Strength: %1$s/15",
                &[Text::literal(strength(nbt).to_string())],
            ),
            0,
        )]),
        SPEEDOMETER => Some(speedometer(network_values(nbt))),
        STRESSOMETER => Some(stressometer(network_values(nbt))),
        _ => None,
    }
}

fn speedometer([rpm, capacity, stress]: [f32; 3]) -> Vec<Text> {
    let rpm = rpm.abs();
    let (level, key, color) = if rpm >= 100.0 {
        (3, "create.tooltip.speedRequirement.fast", LIGHT_PURPLE)
    } else if rpm >= 30.0 {
        (2, "create.tooltip.speedRequirement.medium", AQUA)
    } else if rpm >= 1.0 {
        (1, "create.tooltip.speedRequirement.slow", GREEN)
    } else {
        (0, "create.tooltip.speedRequirement.none", DARK_GRAY)
    };
    let overloaded = stress > capacity;
    let style = Style {
        color: Some(if overloaded { DARK_GRAY } else { color }),
        strikethrough: overloaded.then_some(true),
        ..Style::default()
    };
    let reading = progress(level)
        .append(label(key))
        .append(Text::literal(format!(" ({} ", number(f64::from(rpm)))))
        .append(label("create.generic.unit.rpm"))
        .append(Text::literal(") "))
        .with_style(&style);
    vec![
        indented(label("create.gui.gauge.info_header"), 0),
        indented(label("create.gui.speedometer.title").with_color(GRAY), 0),
        indented(reading, 0),
    ]
}

fn stressometer([rpm, capacity, stress]: [f32; 3]) -> Vec<Text> {
    let capacity = f64::from(capacity);
    let stress = f64::from(stress);
    let mut lines = vec![
        indented(label("create.gui.gauge.info_header"), 0),
        indented(label("create.gui.stressometer.title").with_color(GRAY), 0),
    ];
    if rpm == 0.0 {
        lines.push(indented(
            progress(0)
                .append(label("create.gui.stressometer.no_rotation"))
                .with_color(DARK_GRAY),
            0,
        ));
        return lines;
    }
    let fraction = stress / if capacity == 0.0 { 1.0 } else { capacity };
    let (level, key, color) = if fraction > 1.0 {
        (3, "create.tooltip.stressImpact.overstressed", RED)
    } else if fraction > 0.75 {
        (3, "create.tooltip.stressImpact.high", GOLD)
    } else if fraction > 0.5 {
        (2, "create.tooltip.stressImpact.medium", YELLOW)
    } else {
        (1, "create.tooltip.stressImpact.low", GREEN)
    };
    lines.push(indented(
        progress(level)
            .append(label(key))
            .append(Text::literal(format!(" ({}%) ", (fraction * 100.0) as i32)))
            .with_color(color),
        0,
    ));
    lines.push(indented(
        label("create.gui.stressometer.capacity").with_color(GRAY),
        0,
    ));
    let unit = label("create.generic.unit.stress");
    let mut remaining = Text::literal(number(capacity - stress))
        .append(unit.clone())
        .with_color(color);
    if stress != 0.0 {
        remaining = remaining.append(Text::colored(" / ", GRAY)).append(
            Text::literal(number(capacity))
                .append(unit)
                .with_color(DARK_GRAY),
        );
    }
    lines.push(indented(remaining, 1));
    lines
}

fn indented(line: Text, depth: usize) -> Text {
    Text::literal(" ".repeat(4 + depth)).append(line)
}

fn label(key: &str) -> Text {
    Text::translate(key, &[])
}

fn progress(filled: usize) -> Text {
    Text::literal(format!(
        " {}{} ",
        "█".repeat(filled),
        "▒".repeat(3 - filled)
    ))
}

fn number(value: f64) -> String {
    let decimal = format!("{:.2}", value.abs());
    let (whole, fractional) = decimal.split_once('.').unwrap_or((&decimal, ""));
    let mut result = String::with_capacity(decimal.len() + whole.len() / 3 + 1);
    if value < 0.0 {
        result.push('-');
    }
    for (index, digit) in whole.chars().enumerate() {
        if index != 0 && (whole.len() - index) % 3 == 0 {
            result.push(',');
        }
        result.push(digit);
    }
    let digits = fractional.trim_end_matches('0');
    if !digits.is_empty() {
        result.push('.');
        result.push_str(digits);
    }
    result
}

fn trace(tick: i64, lines: &[Text]) {
    static TRACE: OnceLock<bool> = OnceLock::new();
    if !TRACE.get_or_init(|| std::env::var_os("CREATE_GOGGLES_TRACE").is_some()) {
        return;
    }
    let output: Vec<_> = lines
        .iter()
        .map(|line| {
            line.spans
                .iter()
                .map(|span| {
                    serde_json::json!([
                        span.text,
                        span.style.color,
                        span.style.strikethrough.unwrap_or(false)
                    ])
                })
                .collect::<Vec<_>>()
        })
        .collect();
    eprintln!("CREATE_GOGGLES {tick} {}", serde_json::json!(output));
}
