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
    let Some((pos, entity)) = target(game) else {
        HOVER_FRAMES.set(0);
        return;
    };
    let Some(lines) = readout(game, pos, &entity.id, &entity.nbt, entity) else {
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

fn target<'a>(game: &'a Game<'_>) -> Option<([i32; 3], &'a ModBlockEntity)> {
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
    .then_some((hit.pos, entity))
}

fn readout(
    game: &Game<'_>,
    pos: [i32; 3],
    id: &str,
    nbt: &horizon_world::nbt::Compound,
    entity: &ModBlockEntity,
) -> Option<Vec<Text>> {
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
        "create:chute" | "create:smart_chute" => Some(chute(game, nbt, entity)),
        "create:fluid_tank" | "create:creative_fluid_tank" => tank(game, pos, nbt),
        _ => None,
    }
}

fn chute(
    game: &Game<'_>,
    nbt: &horizon_world::nbt::Compound,
    entity: &ModBlockEntity,
) -> Vec<Text> {
    let mut lines = vec![indented(label("create.tooltip.chute.header"), 0)];
    let pull = super::create_machines::float(nbt, "Pull").unwrap_or(0.0);
    let push = super::create_machines::float(nbt, "Push").unwrap_or(0.0);
    if pull == 0.0 && push == 0.0 {
        lines.push(indented(
            label("create.tooltip.chute.no_fans_attached").with_color(GRAY),
            0,
        ));
    }
    for (value, positive, negative) in [
        (
            pull,
            "create.tooltip.chute.fans_pull_up",
            "create.tooltip.chute.fans_push_down",
        ),
        (
            push,
            "create.tooltip.chute.fans_push_up",
            "create.tooltip.chute.fans_pull_down",
        ),
    ] {
        if value != 0.0 {
            lines.push(indented(
                label(if value > 0.0 { positive } else { negative }).with_color(GRAY),
                0,
            ));
        }
    }
    let motion = (pull + push) / 64.0;
    let upward = (motion.clamp(-20.0, 20.0) + if motion <= 0.0 { -4.0 } else { 0.0 }) >= 0.0;
    lines.push(indented(
        Text::literal("-> ").with_color(YELLOW).append(label(if upward {
            "create.tooltip.chute.items_move_up"
        } else {
            "create.tooltip.chute.items_move_down"
        })),
        0,
    ));
    if let Some(item) = entity.items.iter().flatten().next() {
        lines.push(indented(
            Text::translate(
                "create.tooltip.chute.contains",
                &[game.stack_display_name(item), Text::literal(item.count.to_string())],
            )
            .with_color(GREEN),
            0,
        ));
    }
    lines
}

fn tank(
    game: &Game<'_>,
    pos: [i32; 3],
    nbt: &horizon_world::nbt::Compound,
) -> Option<Vec<Text>> {
    use super::create_depot::compound;
    use super::create_fluids::read_fluid;
    let stored_fluid = compound(nbt, "TankContent")
        .and_then(|tank| compound(tank, "Fluid"))
        .and_then(read_fluid);
    let (capacity, fluid) = super::create_fluid_tank::storage(game, pos)
        .map(|(_, capacity, fluid)| (capacity, fluid))
        .unwrap_or_else(|| {
            let size = int(nbt, "Size").unwrap_or(1);
            let height = int(nbt, "Height").unwrap_or(1);
            (8000 * size * size * height, stored_fluid)
        });
    let mut lines = vec![indented(label("create.gui.goggles.fluid_container"), 0)];
    if let Some(fluid) = fluid {
        let name = if let Some((namespace, path)) = fluid.id.split_once(':') {
            if namespace == "minecraft" {
                Text::translate(&format!("block.minecraft.{path}"), &[])
            } else {
                Text::translate(&format!("fluid.{namespace}.{path}"), &[])
            }
        } else {
            Text::literal(fluid.id.clone())
        };
        lines.push(indented(name.with_color(GRAY), 1));
        lines.push(indented(
            Text::literal(format!("{} mB / {} mB", fluid.amount, capacity)).with_color(GOLD),
            1,
        ));
    } else {
        lines.push(indented(
            Text::literal(format!("Capacity: {capacity} mB")).with_color(GRAY),
            1,
        ));
    }
    Some(lines)
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
