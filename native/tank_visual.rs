use std::sync::OnceLock;

use crate::containers::ModBlockEntity;

use super::native_block_entity_draw::BlockEntityDraw;
use super::{Game, create_machines};

pub(super) fn render(
    game: &Game<'_>,
    pos: [i32; 3],
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    let Some((root, capacity, Some(fluid))) = super::create_fluid_tank::storage(game, pos) else {
        return;
    };
    if root != pos || capacity <= 0 || !super::create_tank_windows::window_enabled(entity) {
        return;
    }

    let width = create_machines::int(&entity.nbt, "Size")
        .unwrap_or(1)
        .max(1) as f32;
    let height = create_machines::int(&entity.nbt, "Height")
        .unwrap_or(1)
        .max(1) as f32;
    let border = 1.125_f32 / 16.0;
    let cap_height = 0.25_f32;
    let puddle_height = 1.0_f32 / 16.0;
    let fluid_height = height - 2.0 * cap_height - puddle_height;
    let fill = (fluid.amount as f32 / capacity as f32).clamp(0.0, 1.0);
    let filled_height = (fill * fluid_height).clamp(0.0, fluid_height);
    if filled_height < fluid_height / 512.0 {
        return;
    }

    let min = [
        border * 16.0,
        (cap_height + puddle_height) * 16.0,
        border * 16.0,
    ];
    let size = [
        (width - 2.0 * border) * 16.0,
        filled_height * 16.0,
        (width - 2.0 * border) * 16.0,
    ];
    let drawn = super::create_spout::draw_still_fluid(game, draw, &fluid, min, size);

    static TRACE: OnceLock<bool> = OnceLock::new();
    if *TRACE.get_or_init(|| std::env::var_os("CREATE_TANK_RENDER").is_some()) {
        eprintln!(
            "CREATE_TANK_RENDER {} {} {} {} {} {} {} {} {:.6} {}",
            pos[0],
            pos[1],
            pos[2],
            width as i32,
            height as i32,
            fluid.id,
            fluid.amount,
            capacity,
            filled_height / fluid_height,
            drawn
        );
    }
}
