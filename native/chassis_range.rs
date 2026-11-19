use horizon_client::hud::HudBatch;
use horizon_world::nbt::Tag;

use crate::containers::{BlockEntity, ModBlockEntity, ModBlockEntityFields};

use super::Game;
use super::create_machines::{int, mod_entity};
use super::create_speed_controller_controls::Selection;

pub(super) const ENTITY: &str = "create:chassis";
pub(super) const DEFAULT: i32 = 8;
pub(super) const MAX: i32 = 16;

pub(super) fn value(game: &Game<'_>, pos: [i32; 3]) -> i32 {
    mod_entity(game, pos)
        .and_then(|entity| int(&entity.nbt, "ScrollValue"))
        .unwrap_or(DEFAULT)
        .clamp(1, MAX)
}

pub(super) fn has_wrench(game: &Game<'_>) -> bool {
    game.held().is_some_and(|stack| {
        stack.item.as_ref() == "create:wrench"
            || game
                .items()
                .item_tags
                .get("c:tools/wrench")
                .is_some_and(|tag| tag.contains(stack.item.as_ref()))
    })
}

pub(super) fn set(game: &mut Game<'_>, pos: [i32; 3], column: i32, bulk: bool) {
    let desired = column.saturating_add(1).clamp(1, MAX);
    let targets = if bulk {
        super::create_linear_chassis::group(game, pos)
    } else {
        vec![pos]
    };
    let mut changed = false;
    for member in targets {
        if value(game, member) == desired {
            continue;
        }
        let [x, y, z] = member;
        let key = (x, y, z);
        // Blocks placed in an earlier Horizon version may lack their
        // chassis entity. Create it on the first range edit.
        if game.world.block_entities.get(&key).is_none() {
            game.world.block_entities.insert(
                key,
                BlockEntity::Mod(Box::new(ModBlockEntity::new(ModBlockEntityFields {
                    id: ENTITY.into(),
                    ..Default::default()
                }))),
            );
        }
        if game.native_with_mod_block_entity(member, |entity| {
            if entity.id != ENTITY {
                return false;
            }
            entity.nbt.insert("ScrollValue".into(), Tag::Int(desired));
            true
        }) == Some(true)
        {
            game.native_block_entity_sync(member);
            changed = true;
        }
    }
    if changed {
        let at = pos.map(|coordinate| f64::from(coordinate) + 0.5);
        game.native_play_sound_in_place("minecraft:entity.item_frame.add_item", at, 4, 0.25, 2.0);
        game.native_play_sound_in_place(
            "minecraft:block.note_block.iron_xylophone",
            at,
            4,
            0.03,
            1.125,
        );
    }
}

const LABEL: &str = "Distance";
const TEXTURE: &str = "create:gui/value_settings";
const BAR_WIDTH: f32 = 97.0;

fn panel(game: &Game<'_>, [left, top, width, height]: [f32; 4]) -> [f32; 4] {
    let label = game.native_text_width(LABEL);
    let panel_width = label + 14.0 + BAR_WIDTH + 10.0;
    [
        left + (width - panel_width) / 2.0,
        top + (height - 11.0) / 2.0,
        panel_width,
        label,
    ]
}

pub(super) fn coordinate(game: &Game<'_>, rect: [f32; 4], column: i32) -> [f32; 2] {
    let [left, top, _, label] = panel(game, rect);
    [left + label + 21.5 + column as f32 * 6.0, top + 5.0]
}

pub(super) fn selection_at(game: &Game<'_>, rect: [f32; 4], mouse: [f32; 2]) -> Selection {
    let [start, _] = coordinate(game, rect, 0);
    let value = ((mouse[0] - start) / 6.0).round() as i32;
    Selection {
        row: 0,
        value: value.clamp(0, MAX - 1),
    }
}

pub(super) fn draw(
    game: &Game<'_>,
    title: &str,
    selected: Selection,
    batch: &mut HudBatch,
    rect: [f32; 4],
) {
    let [x, y, width, label] = panel(game, rect);
    let bar = label + 18.0;
    let sprite = |batch: &mut HudBatch, source: [f32; 4], [left, top, width, height]: [f32; 4]| {
        game.native_sprite(batch, TEXTURE, source, [x + left, y + top, width, height]);
    };
    sprite(
        batch,
        [80.0, 9.0, 1.0, 1.0],
        [-11.0, -17.0, width + 13.0, 44.0],
    );
    for (text, dy) in [(title, -14.0), ("Release Use Item to Confirm", 17.0)] {
        let centered = x + (width - 9.0 - game.native_text_width(text)) / 2.0;
        game.native_text(batch, text, [centered, y + dy], 0xDDDDDD, false);
    }
    horizon_client::widgets::record(LABEL, [x + bar, y, BAR_WIDTH, 11.0], true);
    sprite(
        batch,
        [0.0, 31.0, 16.0, 11.0],
        [-4.0, 0.0, label + 8.0, 11.0],
    );
    game.native_text(batch, LABEL, [x, y + 1.0], 0x442000, false);
    sprite(
        batch,
        [75.0, 9.0, 1.0, 1.0],
        [bar - 1.0, 0.0, BAR_WIDTH + 2.0, 10.0],
    );
    sprite(
        batch,
        [7.0, 0.0, BAR_WIDTH, 8.0],
        [bar, 1.0, BAR_WIDTH, 8.0],
    );
    for column in 0..MAX {
        sprite(
            batch,
            [0.0, 0.0, 4.0, 8.0],
            [bar + column as f32 * 6.0, 1.0, 4.0, 8.0],
        );
    }
    let text = (selected.value + 1).to_string();
    let text_width = game.native_text_width(&text) + 4.0;
    let cursor = coordinate(game, rect, selected.value)[0] - x - text_width / 2.0;
    sprite(
        batch,
        [0.0, 9.0, 3.0, 14.0],
        [cursor - 3.0, -2.0, 3.0, 14.0],
    );
    sprite(
        batch,
        [4.0, 9.0, 56.0, 14.0],
        [cursor, -2.0, text_width, 14.0],
    );
    sprite(
        batch,
        [61.0, 9.0, 3.0, 14.0],
        [cursor + text_width, -2.0, 3.0, 14.0],
    );
    game.native_text(batch, &text, [x + cursor + 2.0, y + 1.0], 0x442000, false);
}
