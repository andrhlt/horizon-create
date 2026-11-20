use horizon_client::hud::{HudBatch, rgba};
use horizon_client::{keybinds, text::Text};

use super::Game;
use super::create_speed_controller_controls::Selection;

pub(super) const TITLE: &str = "Rotation Direction";
const TIP: &str = "Release Use Item to Confirm";
const WINDMILL_OPTIONS: [(&str, &str, [f32; 2]); 2] = [
    ("", "Clockwise", [48.0, 16.0]),
    ("", "Counter-Clockwise", [64.0, 80.0]),
];
const CLOCKWORK_OPTIONS: [(&str, &str, [f32; 2]); 3] = [
    (
        "create.contraptions.clockwork.hour_first",
        "Hour hand first",
        [80.0, 80.0],
    ),
    (
        "create.contraptions.clockwork.minute_first",
        "Minute hand first",
        [96.0, 80.0],
    ),
    (
        "create.contraptions.clockwork.hour_first_24",
        "24-Hour hand first",
        [112.0, 80.0],
    ),
];
const PISTON_OPTIONS: [(&str, &str, [f32; 2]); 3] = [
    ("create.contraptions.movement_mode.move_place", "Always Place when Stopped", [144.0, 16.0]),
    ("create.contraptions.movement_mode.move_place_returned", "Place only in Starting Position", [160.0, 16.0]),
    ("create.contraptions.movement_mode.move_never_place", "Place only when Anchor Destroyed", [176.0, 16.0]),
];
const ROLLER_OPTIONS: [(&str, &str, [f32; 2]); 3] = [
    ("", "Tunnel Pave", [144.0, 64.0]),
    ("", "Straight Fill", [160.0, 64.0]),
    ("", "Wide Fill", [176.0, 64.0]),
];
const SPRITES: &str = "create:gui/value_settings";

#[derive(Clone, Copy)]
pub(super) enum IconBoard {
    Windmill,
    Clockwork,
    Piston,
    Roller,
}

impl IconBoard {
    fn options(self) -> &'static [(&'static str, &'static str, [f32; 2])] {
        match self {
            Self::Windmill => &WINDMILL_OPTIONS,
            Self::Clockwork => &CLOCKWORK_OPTIONS,
            Self::Piston => &PISTON_OPTIONS,
            Self::Roller => &ROLLER_OPTIONS,
        }
    }

    pub(super) fn maximum(self) -> i32 {
        self.options().len() as i32 - 1
    }

    fn position(self, [left, top, width, height]: [f32; 4]) -> [f32; 2] {
        let [x, y] = match self {
            Self::Windmill => [(width / 2.0).floor() - 13.0, (height / 2.0).floor() - 5.0],
            Self::Clockwork | Self::Piston | Self::Roller => [
                ((width - 37.0) / 2.0).floor(),
                ((height - 11.0) / 2.0).floor(),
            ],
        };
        [left + x, top + y]
    }

    pub(super) fn coordinate(self, rect: [f32; 4], value: i32) -> [f32; 2] {
        let [x, y] = self.position(rect);
        [x + 5.5 + value as f32 * 10.0, y + 5.0]
    }

    pub(super) fn selection_at(self, rect: [f32; 4], mouse: [f32; 2]) -> Selection {
        let [x, _] = self.coordinate(rect, 0);
        Selection {
            row: 0,
            value: (((mouse[0] - x) / 10.0 + 0.5).floor() as i32).clamp(0, self.maximum()),
        }
    }

    pub(super) fn draw(
        self,
        game: &Game<'_>,
        selected: Selection,
        batch: &mut HudBatch,
        rect: [f32; 4],
    ) {
        let [x, y] = self.position(rect);
        let (title, tip) = match self {
            Self::Windmill => (TITLE.to_owned(), TIP.to_owned()),
            Self::Piston => (
                game.translate("create.contraptions.movement_mode", "Movement Mode"),
                Text::translate_with_fallback("create.gui.value_settings.release_to_confirm", "Release %1$s to Confirm", &[keybinds::display_name(game.settings.keys.get("key.use"))]).plain(),
            ),
            Self::Roller => (
                "Rolling Mode".to_owned(),
                Text::translate_with_fallback("create.gui.value_settings.release_to_confirm", "Release %1$s to Confirm", &[keybinds::display_name(game.settings.keys.get("key.use"))]).plain(),
            ),
            Self::Clockwork => (
                game.translate(
                    "create.contraptions.clockwork.clock_hands",
                    "Clock Hand Arrangement",
                ),
                Text::translate_with_fallback(
                    "create.gui.value_settings.release_to_confirm",
                    "Release %1$s to Confirm",
                    &[keybinds::display_name(game.settings.keys.get("key.use"))],
                )
                .plain(),
            ),
        };
        let labels: Vec<_> = self
            .options()
            .iter()
            .map(|(key, label, _)| {
                if key.is_empty() {
                    (*label).to_owned()
                } else {
                    game.translate(key, label)
                }
            })
            .collect();
        let extra_width = self.maximum() as f32 * 10.0 - 10.0;
        let background_width = std::iter::once(title.as_str())
            .chain(std::iter::once(tip.as_str()))
            .chain(labels.iter().map(String::as_str))
            .map(|text| game.native_text_width(text) + 10.0)
            .fold(40.0 + extra_width, f32::max);
        let center = x + 9.0 + extra_width / 2.0;
        let sprite = |batch: &mut HudBatch, source: [f32; 4], target: [f32; 4]| {
            game.native_sprite(batch, SPRITES, source, target);
        };
        sprite(
            batch,
            [80.0, 9.0, 1.0, 1.0],
            [
                center - background_width / 2.0,
                y - 17.0,
                background_width,
                57.0,
            ],
        );

        for (text, offset, color) in [
            (title.as_str(), -14.0, 0xDDDDDD),
            (tip.as_str(), 30.0, 0xDDDDDD),
            (labels[selected.value as usize].as_str(), 17.0, 0xFBDC7D),
        ] {
            game.native_text(
                batch,
                text,
                [center - game.native_text_width(text) / 2.0, y + offset],
                color,
                false,
            );
        }

        // Original brass frame around the icon milestones.
        for (source, [dx, dy, width, height]) in [
            ([65.0, 9.0, 4.0, 4.0], [-4.0, -3.0, 4.0, 4.0]),
            ([70.0, 9.0, 4.0, 4.0], [21.0 + extra_width, -3.0, 4.0, 4.0]),
            ([65.0, 19.0, 4.0, 4.0], [-4.0, 9.0, 4.0, 4.0]),
            ([70.0, 19.0, 4.0, 4.0], [21.0 + extra_width, 9.0, 4.0, 4.0]),
            ([65.0, 14.0, 3.0, 4.0], [-4.0, 1.0, 3.0, 8.0]),
            ([71.0, 14.0, 3.0, 4.0], [22.0 + extra_width, 1.0, 3.0, 8.0]),
            (
                [0.0, 24.0, 21.0 + extra_width, 3.0],
                [0.0, -3.0, 21.0 + extra_width, 3.0],
            ),
            (
                [0.0, 27.0, 21.0 + extra_width, 3.0],
                [0.0, 10.0, 21.0 + extra_width, 3.0],
            ),
            ([75.0, 9.0, 1.0, 1.0], [-1.0, 0.0, 23.0 + extra_width, 10.0]),
        ] {
            sprite(batch, source, [x + dx, y + dy, width, height]);
        }
        for (value, label) in labels.iter().enumerate() {
            sprite(
                batch,
                [75.0, 14.0, 13.0, 8.0],
                [x + value as f32 * 10.0, y + 1.0, 13.0, 8.0],
            );
            let [left, top] = self.coordinate(rect, value as i32);
            horizon_client::widgets::record(label, [left - 4.5, top - 5.0, 9.0, 11.0], true);
        }
        let [left, top] = self.coordinate(rect, selected.value);
        let left = left.floor();
        sprite(
            batch,
            [0.0, 44.0, 22.0, 20.0],
            [left - 11.0, top - 10.0, 22.0, 20.0],
        );
        if let Some(mut icon) = game.gui.atlas.sprites.get("create:gui/icons").copied() {
            let [iu, iv] = self.options()[selected.value as usize].2;
            let du = (icon.u1 - icon.u0) / icon.w as f32;
            let dv = (icon.v1 - icon.v0) / icon.h as f32;
            icon.u0 += iu * du;
            icon.v0 += iv * dv;
            icon.u1 = icon.u0 + 16.0 * du;
            icon.v1 = icon.v0 + 16.0 * dv;
            batch.rect_uv(
                left - 8.0,
                top - 8.0,
                16.0,
                16.0,
                icon,
                rgba(68, 32, 0, 255),
            );
        }
    }
}
