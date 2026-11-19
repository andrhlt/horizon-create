use super::Game;
use super::create_station::LARGE_BOGEY;
use super::native_block_entity_draw::BlockEntityDraw;
use horizon_world::registry::BlockStateId;

pub(super) const ENTITY: &str = "create:bogey";
pub(super) const Y_OFFSET: f32 = 0.5 - 1.5 - 1.0 / 128.0;
const FRAME: &str = "bogey_frame";
const SMALL_WHEEL: &str = "bogey_wheel";
const PIN: &str = "bogey_drive_wheel_pin";
const PISTON: &str = "bogey_drive_piston";
const DRIVE: &str = "bogey_drive";
const LARGE_WHEEL: &str = "bogey_drive_wheel";
const DRIVE_BELT: &str = "bogey_drive_belt";

pub(super) struct Part {
    pub model: &'static str,
    pub at: [f32; 3],
    pub axis: usize,
    pub angle: f32,
    pub pivot: [f32; 3],
}

fn static_part(model: &'static str, at: [f32; 3]) -> Part {
    Part {
        model,
        at,
        axis: 0,
        angle: 0.0,
        pivot: [0.0; 3],
    }
}

fn model_path(name: &str) -> String {
    match name {
        "shaft_x" | "shaft_z" => "create:block/shaft".into(),
        _ => format!("create:block/track/bogey/{name}"),
    }
}

pub(super) fn models(models: &mut Vec<String>) {
    models.extend(
        [
            FRAME,
            SMALL_WHEEL,
            PIN,
            PISTON,
            DRIVE,
            LARGE_WHEEL,
            DRIVE_BELT,
            "shaft_x",
        ]
        .map(model_path),
    );
}

pub(super) fn parts(large: bool, angle: f32) -> Vec<Part> {
    let mut parts = Vec::with_capacity(if large { 9 } else { 5 });
    for z in [0.0, -1.0] {
        parts.push(Part {
            model: "shaft_z",
            at: [-0.5, 0.25, z],
            axis: 2,
            angle,
            pivot: [0.5; 3],
        });
    }
    if large {
        for z in [0.5, -1.5] {
            parts.push(Part {
                model: "shaft_x",
                at: [-0.5, 0.25, z],
                axis: 0,
                angle,
                pivot: [0.5; 3],
            });
        }
        let (sine, cosine) = angle.to_radians().sin_cos();
        parts.extend([
            static_part(DRIVE, [0.0; 3]),
            static_part(DRIVE_BELT, [0.0; 3]),
            static_part(PISTON, [0.0, 0.0, 0.25 * sine]),
            static_part(PIN, [0.0, 1.0 + 0.25 * cosine, 0.25 * sine]),
            Part {
                angle,
                ..static_part(LARGE_WHEEL, [0.0, 1.0, 0.0])
            },
        ]);
    } else {
        parts.push(static_part(FRAME, [0.0; 3]));
        for z in [-1.0, 1.0] {
            parts.push(Part {
                angle,
                ..static_part(SMALL_WHEEL, [0.0, 0.75, z])
            });
        }
    }
    parts
}

pub(super) fn render(
    game: &Game<'_>,
    state: BlockStateId,
    block: &str,
    draw: &mut BlockEntityDraw,
) {
    draw.push();
    draw.translate([0.5, Y_OFFSET, 0.5]);
    if game.native_block_state_property(state, "axis") == Some("x") {
        draw.rotate_about([0.0, 1.0, 0.0], 90.0, [0.0; 3]);
    }
    for part in parts(block == LARGE_BOGEY, 0.0) {
        draw.push();
        draw.translate(part.at);
        match part.model {
            "shaft_x" => draw.rotate_about([0.0, 0.0, 1.0], -90.0, [0.5; 3]),
            "shaft_z" => draw.rotate_about([1.0, 0.0, 0.0], 90.0, [0.5; 3]),
            _ => (),
        }
        game.native_draw_model(draw, &model_path(part.model), 0xFFFFFF);
        draw.pop();
    }
    draw.pop();
    draw.keep();
}
