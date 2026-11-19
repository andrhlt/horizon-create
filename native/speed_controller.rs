use horizon_core::geometry::Direction;
use horizon_core::position::BlockPos;
use horizon_world::level::PlaceContext;
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;

use crate::containers::ModBlockEntity;

use super::create_machines::{LARGE_COG, axis_index, float, int, reading, set_float};
use super::create_speed_controller_controls::{Selection, ValueBlock};
use super::native_block_entity_draw::BlockEntityDraw;
use super::{Game, GameLevel};

pub(super) const CONTROLLER: &str = "create:rotation_speed_controller";
const BRACKET: &str = "create:block/rotation_speed_controller/bracket";
const SHAFT: &str = "create:block/shaft";
const CENTER: [f32; 3] = [0.5; 3];

pub(super) fn target(entity: Option<&ModBlockEntity>) -> f32 {
    entity
        .and_then(|entity| int(&entity.nbt, "ScrollValue"))
        .unwrap_or(16)
        .clamp(-256, 256) as f32
}

pub(super) fn update_tag(entity: &ModBlockEntity) -> Compound {
    let mut tag = Compound::new();
    set_float(&mut tag, "VisualSpeed", reading(entity, 0));
    tag.insert("ScrollValue".into(), Tag::Int(target(Some(entity)) as i32));
    tag
}

pub(super) fn models(out: &mut Vec<String>) {
    out.push(BRACKET.into());
}

pub(super) fn render(
    game: &Game<'_>,
    pos: [i32; 3],
    state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    let Some(axis) = game
        .native_block_state_property(state, "axis")
        .and_then(axis_index)
    else {
        return;
    };
    let rpm = if entity.data.is_empty() {
        float(&entity.nbt, "VisualSpeed").unwrap_or(0.0)
    } else {
        reading(entity, 0)
    };
    let parity = pos[(axis + 1) % 3] + pos[(axis + 2) % 3];
    let phase = if parity % 2 == 0 { 22.5 } else { 0.0 };
    let angle = super::create_visuals::wheel_angle(draw.game_time, draw.partial, rpm, phase);
    super::create_visuals::draw_rotating(game, draw, axis, angle, SHAFT);

    let above = [pos[0], pos[1] + 1, pos[2]];
    if game.native_block(above) == super::create_machines::LARGE_COG
        && game
            .native_block_property(above, "axis")
            .is_some_and(|axis| axis != "y")
    {
        draw.push();
        draw.translate([0.0, 1.0, 0.0]);
        draw.rotate_about(
            [0.0, 1.0, 0.0],
            if axis == 0 { 180.0 } else { 90.0 },
            CENTER,
        );
        game.native_draw_model(draw, BRACKET, 0xffffff);
        draw.pop();
    }
}

pub(super) fn cross_axis(axis: &str) -> &'static str {
    if axis == "x" { "z" } else { "x" }
}

pub(super) fn redirect_cog_placement(game: &mut Game<'_>, context: &mut PlaceContext) {
    let clicked = context.clicked_pos;
    let pos = [clicked.x, clicked.y, clicked.z];
    if context.sneaking
        || context.item != LARGE_COG
        || context.face == Direction::Up
        || game.native_block(pos) != CONTROLLER
    {
        return;
    }

    let top = BlockPos::new(clicked.x, clicked.y + 1, clicked.z);
    let axis = game
        .native_block_property(pos, "axis")
        .unwrap_or_else(|| "x".into());
    let checked = PlaceContext {
        clicked_pos: top,
        face: Direction::Up,
        ..context.clone()
    };
    if game.with_level(|b, level, ticks| {
        b.directional_can_place(level, ticks, &checked)
            && super::create_cogwheel::valid_position(level, top, cross_axis(&axis), true)
    }) {
        context.face = Direction::Up;
    }
}

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    context: &horizon_world::level::PlacementContext,
) -> Option<Option<BlockStateId>> {
    let pos = context.pos;
    if level.native_state_block(state) != Some(CONTROLLER) {
        return None;
    }
    let above = level.world.block(pos.x, pos.y + 1, pos.z);
    if let Some(above) = level.registry.state(above)
        && above.name == LARGE_COG
        && let Some(axis) = above.properties.get("axis")
        && axis != "y"
    {
        return Some(level.native_state_with_property(state, "axis", cross_axis(axis)));
    }
    let preferred = super::create_hand_crank::preferred_in_directions(
        level,
        pos,
        [
            Direction::North,
            Direction::South,
            Direction::West,
            Direction::East,
        ],
    );
    let axis = match preferred {
        Some(Direction::East | Direction::West) => "x",
        Some(Direction::North | Direction::South) => "z",
        _ => {
            let yaw = context.yaw.to_radians();
            if yaw.sin().abs() >= yaw.cos().abs() {
                "z"
            } else {
                "x"
            }
        }
    };
    Some(level.native_state_with_property(state, "axis", axis))
}

const VALUE_SETTINGS: &str = "create:gui/value_settings";
const ROWS: [&str; 2] = ["⟳", "⟲"];
const HEIGHT: f32 = 59.0;
const ROW_TOP: f32 = 19.0;
const BAR_LEFT: f32 = 25.0;
const MAX_SETTING: i32 = 256;

#[derive(Clone, Copy)]
pub(super) enum ValueBoard {
    Speed,
    Angle,
    StackSize,
    Interval,
}

impl ValueBoard {
    pub(super) fn maximum(self) -> i32 {
        match self {
            Self::Speed => MAX_SETTING,
            Self::Angle => 180,
            Self::StackSize => super::create_ejector::STACK_SIZE,
            Self::Interval => 60,
        }
    }

    pub(super) fn milestone(self) -> i32 {
        match self {
            Self::Speed => 32,
            Self::Angle => 45,
            Self::StackSize | Self::Interval => 10,
        }
    }

    fn scale(self) -> i32 {
        if matches!(self, Self::StackSize | Self::Interval) {
            2
        } else {
            1
        }
    }

    fn row_top(self) -> f32 {
        if matches!(self, Self::StackSize) {
            18.0
        } else {
            ROW_TOP
        }
    }

    fn height(self) -> f32 {
        match self {
            Self::StackSize => 46.0,
            Self::Interval => HEIGHT + 11.0,
            _ => HEIGHT,
        }
    }

    fn unit_labels(self, game: &Game<'_>) -> [String; 3] {
        ["Ticks", "Seconds", "Minutes"].map(|fallback| {
            game.translate(
                &format!("create.generic.unit.{}", fallback.to_ascii_lowercase()),
                fallback,
            )
        })
    }

    fn bar_left(self, game: &Game<'_>) -> f32 {
        match self {
            Self::StackSize => game.native_text_width("Value") + 29.0,
            Self::Interval => {
                self.unit_labels(game)
                    .iter()
                    .map(|label| game.native_text_width(label))
                    .fold(0.0, f32::max)
                    + 24.0
            }
            _ => BAR_LEFT,
        }
    }

    fn bar_width(self) -> f32 {
        ((self.maximum() + 1) * self.scale() + 1 + (self.maximum() / self.milestone() + 1) * 4)
            as f32
    }

    fn width(self, game: &Game<'_>) -> f32 {
        if matches!(self, Self::StackSize | Self::Interval) {
            self.bar_width() + self.bar_left(game) + 8.0
        } else {
            self.bar_width() + 40.0
        }
    }

    pub(super) fn panel(self, game: &Game<'_>, [left, top, width, height]: [f32; 4]) -> [f32; 2] {
        [
            left + (width - self.width(game)) / 2.0,
            top + (height - self.height()) / 2.0,
        ]
    }

    fn column_x(self, bar_left: f32, column: i32) -> f32 {
        let milestone = self.milestone();
        bar_left
            + ((column.max(1) - 1) / milestone * 4) as f32
            + (column * self.scale()) as f32
            + 1.5
            + if column % milestone == 0 { 2.0 } else { 0.0 }
            + if column > 0 { 4.0 } else { 0.0 }
    }

    pub(super) fn coordinate(self, game: &Game<'_>, selection: Selection) -> [f32; 2] {
        [
            self.column_x(self.bar_left(game), selection.value),
            self.row_top() + f32::from(selection.row) * 11.0 + 5.0,
        ]
    }

    pub(super) fn selection_at(
        self,
        game: &Game<'_>,
        [x, y]: [f32; 2],
        milestones: bool,
    ) -> Selection {
        let stack_size = matches!(self, Self::StackSize);
        let row = match self {
            Self::Interval => {
                (((y - self.row_top() + 0.5) / 11.0).floor() as i32).clamp(0, 2) as u8
            }
            _ => u8::from(!stack_size && y >= self.row_top() + 10.5),
        };
        let step = if milestones { self.milestone() } else { 1 };
        let maximum = self.maximum();
        let end = if stack_size {
            ((maximum + step - 1) / step) * step
        } else {
            maximum
        };
        let bar_left = self.bar_left(game);
        let value = (0..=end)
            .step_by(step as usize)
            .min_by(|&a, &b| {
                let a_dist = (self.column_x(bar_left, a) - x).abs();
                let b_dist = (self.column_x(bar_left, b) - x).abs();
                a_dist.total_cmp(&b_dist).then_with(|| b.cmp(&a))
            })
            .unwrap_or(0)
            .min(maximum);
        Selection { row, value }
    }
}

pub(super) fn set_value(
    game: &mut Game<'_>,
    pos: [i32; 3],
    block: ValueBlock,
    selection: Selection,
) {
    let speed = selection.value.clamp(1, MAX_SETTING) * if selection.row == 0 { -1 } else { 1 };
    let changed = game.native_with_mod_block_entity(pos, |entity| {
        if block.speed_entity() != Some(entity.id.as_str()) || target(Some(entity)) == speed as f32
        {
            return false;
        }
        entity.nbt.insert("ScrollValue".into(), Tag::Int(speed));
        true
    });
    if changed != Some(true) {
        return;
    }
    setting_feedback(game, pos);
    if matches!(block, ValueBlock::Motor) {
        super::create_machines::motor_setting_changed(game, pos);
    }
    game.native_block_entity_sync(pos);
}

pub(super) fn setting_feedback(game: &mut Game<'_>, pos: [i32; 3]) {
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

impl ValueBoard {
    pub(super) fn draw_screen(
        self,
        game: &Game<'_>,
        title: &str,
        selected: Selection,
        draw: &mut horizon_client::hud::HudBatch,
        rect: [f32; 4],
    ) {
        let [x, y] = self.panel(game, rect);
        let width = self.width(game);
        let height = self.height();
        let row_top = self.row_top();
        let bar_left = self.bar_left(game);
        let bar_width = self.bar_width();
        let stack_size = matches!(self, Self::StackSize);
        let units = self.unit_labels(game);
        let timing_rows = units.each_ref().map(String::as_str);
        let rows: &[&str] = match self {
            Self::StackSize => &["Value"],
            Self::Interval => &timing_rows,
            _ => &ROWS,
        };
        let sprite = |draw: &mut horizon_client::hud::HudBatch,
                      texture: [f32; 4],
                      [left, top, width, height]: [f32; 4]| {
            game.native_sprite(
                draw,
                VALUE_SETTINGS,
                texture,
                [x + left, y + top, width, height],
            );
        };
        let center =
            |draw: &mut horizon_client::hud::HudBatch, text: &str, off_y: f32, color: u32| {
                let text_width = game.native_text_width(text);
                game.native_text(
                    draw,
                    text,
                    [x + (width - text_width) / 2.0, y + off_y],
                    color,
                    false,
                );
            };
        sprite(draw, [80.0, 9.0, 1.0, 1.0], [0.0, 0.0, width, height]);
        center(draw, title, 5.0, 0xDDDDDD);
        center(draw, "Release Use Item to Confirm", height - 12.0, 0xDDDDDD);
        sprite(
            draw,
            [75.0, 9.0, 1.0, 1.0],
            [
                bar_left - 2.0,
                row_top - 1.0,
                bar_width + 4.0,
                rows.len() as f32 * 11.0 + 1.0,
            ],
        );
        for (index, row) in rows.iter().copied().enumerate() {
            let row_y = row_top + index as f32 * 11.0;
            let label = match (self, index) {
                (Self::Speed, 0) => "Counterclockwise RPM",
                (Self::Speed, _) => "Clockwise RPM",
                (Self::Angle, 0) => "Negative rotation angle",
                (Self::Angle, _) => "Positive rotation angle",
                (Self::StackSize, _) => title,
                (Self::Interval, _) => row,
            };
            horizon_client::widgets::record(
                label,
                [x + bar_left, y + row_y, bar_width, 11.0],
                true,
            );
            let label_width = if stack_size || matches!(self, Self::Interval) {
                game.native_text_width(row) + 8.0
            } else {
                16.0
            };
            let label_x = if stack_size { 7.0 } else { 5.0 };
            sprite(
                draw,
                [0.0, 31.0, label_width, 11.0],
                [label_x, row_y, label_width, 11.0],
            );
            game.native_text(
                draw,
                row,
                [x + label_x + 4.0, y + row_y + 1.0],
                0x442000,
                false,
            );
            let first = bar_width.min(248.0);
            sprite(
                draw,
                [7.0, 0.0, first, 8.0],
                [bar_left, row_y + 1.0, first, 8.0],
            );
            if bar_width > first {
                let rest = bar_width - first;
                sprite(
                    draw,
                    [7.0, 0.0, rest, 8.0],
                    [bar_left + first, row_y + 1.0, rest, 8.0],
                );
            }
            let milestone = self.milestone();
            for mark in 0..=self.maximum() / milestone {
                sprite(
                    draw,
                    [0.0, 0.0, 7.0, 8.0],
                    [
                        bar_left + (mark * (milestone * self.scale() + 4)) as f32,
                        row_y + 1.0,
                        7.0,
                        8.0,
                    ],
                );
            }
        }

        let value = if stack_size {
            selected.value
        } else {
            selected.value.max(1)
        };
        let label = match self {
            Self::Speed => format!("{value}{}", ROWS[usize::from(selected.row)]),
            Self::Angle => format!(
                "{value}{}",
                game.translate("create.generic.unit.degrees", "°")
            ),
            Self::StackSize => value.to_string(),
            Self::Interval => match selected.row {
                0 => format!("{}t", value.max(2)),
                1 => format!("0:{value:02}"),
                _ => format!("{value}:00"),
            },
        };
        let label_width = game.native_text_width(&label) + 4.0;
        let [center_x, center_y] = self.coordinate(game, selected);
        let label_left = center_x - label_width / 2.0;
        let label_top = center_y - 7.0;
        sprite(
            draw,
            [0.0, 9.0, 3.0, 14.0],
            [label_left - 3.0, label_top, 3.0, 14.0],
        );
        sprite(
            draw,
            [4.0, 9.0, 56.0, 14.0],
            [label_left, label_top, label_width, 14.0],
        );
        sprite(
            draw,
            [61.0, 9.0, 3.0, 14.0],
            [label_left + label_width, label_top, 3.0, 14.0],
        );
        game.native_text(
            draw,
            &label,
            [x + label_left + 2.0, y + label_top + 3.0],
            0x442000,
            false,
        );
    }
}

pub(super) fn place_motor(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    context: &horizon_world::level::PlacementContext,
) -> Option<Option<horizon_world::registry::BlockStateId>> {
    use horizon_core::geometry::Direction;

    if level.native_state_block(state) != Some("create:creative_motor") {
        return None;
    }
    let look = context.nearest_looking_direction();
    let facing = if context.sneaking {
        look
    } else {
        crate::game::create_hand_crank::preferred_direction(level, context.pos)
            .unwrap_or(look)
            .opposite()
    };
    let property = match facing {
        Direction::Down => "down",
        Direction::Up => "up",
        Direction::North => "north",
        Direction::South => "south",
        Direction::West => "west",
        Direction::East => "east",
    };
    Some(level.native_state_with_property(state, "facing", property))
}
