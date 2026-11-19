use horizon_core::geometry::Direction;
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;

use crate::containers::ModBlockEntity;

use super::Game;
use super::create_depot::compound;
use super::create_machines::{float, int, mod_entity, offset, set_float};
use super::create_threshold_switch::delta;
use super::native_block_entity_draw::BlockEntityDraw;

pub(super) const BOARD: &str = "create:display_board";
pub(super) const ENTITY: &str = "create:flap_display";
const MEDIUM_RPM: f32 = 30.0;

fn left(game: &Game<'_>, pos: [i32; 3]) -> Option<Direction> {
    Some(match game.native_block_property(pos, "facing")?.as_str() {
        "north" => Direction::East,
        "east" => Direction::South,
        "south" => Direction::West,
        "west" => Direction::North,
        _ => return None,
    })
}

fn matches(game: &Game<'_>, pos: [i32; 3], state: BlockStateId) -> bool {
    game.world.block(pos[0], pos[1], pos[2]) == state
}

fn controller(game: &Game<'_>, mut pos: [i32; 3]) -> Option<[i32; 3]> {
    if game.native_block(pos) != BOARD {
        return None;
    }
    let direction = left(game, pos)?;
    while game.native_block_property(pos, "up").as_deref() == Some("true") {
        let above = offset(pos, [0, 1, 0]);
        if game.native_block(above) != BOARD || left(game, above) != Some(direction) {
            break;
        }
        pos = above;
    }
    let state = game.world.block(pos[0], pos[1], pos[2]);
    while matches(game, offset(pos, delta(direction)), state) {
        pos = offset(pos, delta(direction));
    }
    Some(pos)
}

fn width(game: &Game<'_>, pos: [i32; 3]) -> i32 {
    let Some(direction) = left(game, pos) else {
        return 1;
    };
    let state = game.world.block(pos[0], pos[1], pos[2]);
    (1..32)
        .take_while(|&i| {
            matches(
                game,
                offset(pos, delta(direction.opposite()).map(|v| v * i)),
                state,
            )
        })
        .count() as i32
        + 1
}

fn height(game: &Game<'_>, pos: [i32; 3]) -> i32 {
    let Some(direction) = left(game, pos) else {
        return 1;
    };
    let mut height = 1;
    while height < 32
        && game
            .native_block_property(offset(pos, [0, 1 - height, 0]), "down")
            .as_deref()
            == Some("true")
    {
        let below = offset(pos, [0, -height, 0]);
        if game.native_block(below) != BOARD || left(game, below) != Some(direction) {
            break;
        }
        height += 1;
    }
    height
}

pub(super) fn rows(game: &Game<'_>, target: [i32; 3]) -> Option<i32> {
    Some(height(game, controller(game, target)?) * 2)
}

pub(super) fn tick(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
    rpm: f32,
    changed_speed: bool,
) {
    let is_controller = controller(game, pos) == Some(pos);
    let size_x = if is_controller { width(game, pos) } else { 1 };
    let size_y = if is_controller { height(game, pos) } else { 1 };
    let updates = [
        ("Controller", i32::from(is_controller)),
        ("XSize", size_x),
        ("YSize", size_y),
    ];
    let changed = float(&entity.nbt, "Speed") != Some(rpm)
        || updates
            .iter()
            .any(|&(key, value)| int(&entity.nbt, key) != Some(value));
    set_float(&mut entity.nbt, "Speed", rpm);
    entity
        .nbt
        .insert("Controller".into(), Tag::Byte(i8::from(is_controller)));
    for (key, value) in [("XSize", size_x), ("YSize", size_y)] {
        entity.nbt.insert(key.into(), Tag::Int(value));
    }
    if changed {
        game.native_block_entity_sync(pos);
    }
}

fn row(data: &Compound, index: i32) -> String {
    let Some(line) = compound(data, &format!("Display{index}")) else {
        return String::new();
    };
    let Some(Tag::List(sections)) = line.get(&"Sections".into()) else {
        return String::new();
    };
    sections
        .iter()
        .filter_map(|section| {
            let Tag::String(text) = section.get("Text")? else {
                return None;
            };
            let parse = serde_json::from_str::<serde_json::Value>(&text.to_string_lossy()).ok()?;
            Some(
                parse
                    .as_str()
                    .or_else(|| parse.get("text")?.as_str())?
                    .to_owned(),
            )
        })
        .collect()
}

pub(super) fn publish(game: &mut Game<'_>, target: [i32; 3], line: i32, value: &str) {
    let Some(pos) = controller(game, target) else {
        return;
    };
    let Some(entity) = mod_entity(game, pos) else {
        return;
    };
    if float(&entity.nbt, "Speed").unwrap_or_default().abs() < MEDIUM_RPM
        || !(0..height(game, pos) * 2).contains(&line)
        || row(&entity.nbt, line) == value
    {
        return;
    }
    let section_width = width(game, pos) as f32 * 28.0;
    let text = serde_json::json!({ "text": value }).to_string();
    game.native_with_mod_block_entity(pos, |entity| {
        let section = Compound::from([
            ("Text".into(), Tag::String(text.as_str().into())),
            ("Width".into(), Tag::Float(section_width.to_bits())),
            ("Cycle".into(), Tag::String("alphabet".into())),
        ]);
        let layout = Compound::from([
            ("Sections".into(), Tag::List(vec![Tag::Compound(section)])),
            ("Key".into(), Tag::String("Number".into())),
        ]);
        entity.nbt.insert(
            format!("Display{line}").as_str().into(),
            Tag::Compound(layout),
        );
    });
    game.native_block_entity_sync(pos);
}

pub(super) fn render(
    game: &Game<'_>,
    state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    if int(&entity.nbt, "Controller") != Some(1)
        || float(&entity.nbt, "Speed").unwrap_or_default().abs() < MEDIUM_RPM
    {
        return;
    }
    let yaw = match game.native_block_state_property(state, "facing") {
        Some("north") => 180.0,
        Some("east") => 90.0,
        Some("west") => -90.0,
        _ => 0.0,
    };
    let width = int(&entity.nbt, "XSize").unwrap_or(1) as f32;
    let rows = int(&entity.nbt, "YSize").unwrap_or(1) * 2;
    for i in 0..rows {
        let value = row(&entity.nbt, i).to_uppercase();
        if value.is_empty() {
            continue;
        }
        let width_px = game.native_text_width(&value);
        let scale = 0.045_f32.min((width - 0.12) / width_px.max(1.0));
        draw.push();
        draw.rotate_about([0.0, 1.0, 0.0], yaw, [0.5; 3]);
        draw.translate([width * 0.5, 0.93 - i as f32 * 0.5, 1.002]);
        draw.scale([scale, -scale, scale]);
        game.native_draw_text(
            draw,
            &horizon_client::text::Text::from(value),
            [-width_px * 0.5, 0.0],
            0xdddddd,
            false,
            0,
        );
        draw.pop();
    }
}
