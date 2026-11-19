use horizon_assets::item_model::DisplayContext;
use horizon_world::{nbt::Tag, registry::BlockStateId};

use crate::{containers::ModBlockEntity, items::ItemStack};

use super::{
    Game, create_depot::compound, create_machines::int, native_block_entity_draw::BlockEntityDraw,
};

const OPEN_HATCH: &str = "create:block/packager/hatch_open";
const CLOSED_HATCH: &str = "create:block/packager/hatch_closed";
const TRAY: &str = "create:block/packager/tray";

pub(super) fn models(models: &mut Vec<String>) {
    models.extend([OPEN_HATCH, CLOSED_HATCH, TRAY].map(str::to_owned));
}

pub(super) fn render(
    game: &Game<'_>,
    state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    let Some(facing) = game
        .pack
        .assets
        .registry
        .state(state)
        .and_then(|state| state.properties.get("facing"))
        .map(String::as_str)
    else {
        return;
    };
    let (normal, yaw, pitch) = match facing {
        "north" => ([0.0, 0.0, 1.0], 0.0, 0.0),
        "south" => ([0.0, 0.0, -1.0], 180.0, 0.0),
        "east" => ([-1.0, 0.0, 0.0], 90.0, 0.0),
        "west" => ([1.0, 0.0, 0.0], 270.0, 0.0),
        "up" => ([0.0, -1.0, 0.0], 0.0, 90.0),
        "down" => ([0.0, 1.0, 0.0], 0.0, -90.0),
        _ => return,
    };
    let inward = int(&entity.nbt, "AnimationInward").unwrap_or(1) != 0;
    let clock_animation = match entity.nbt.get(&"AnimationStart".into()) {
        Some(Tag::Long(start)) => (20 - draw.game_time.saturating_sub(*start)).clamp(0, 20) as i32,
        _ => 0,
    };
    let animation = clock_animation.min(int(&entity.nbt, "AnimationTicks").unwrap_or_default());
    let open = if inward {
        (2..15).contains(&animation)
    } else {
        (6..19).contains(&animation)
    };
    let cycle = animation as f32 - if inward { 0.0 } else { 5.0 } - draw.partial;
    let progress = (cycle / 15.0 * 2.0 - 1.0).clamp(-1.0, 1.0);
    let offset = (1.0 - progress * progress).powi(2);
    let y = [0.0, 1.0, 0.0];
    let pivot = [0.5; 3];

    draw.push();
    draw.translate(normal.map(|axis| axis * 0.49999));
    draw.rotate_about(y, yaw, pivot);
    draw.rotate_about([1.0, 0.0, 0.0], pitch, pivot);
    let hatch_drawn =
        game.native_draw_model(draw, if open { OPEN_HATCH } else { CLOSED_HATCH }, 0xffffff);
    draw.pop();

    draw.push();
    draw.translate(normal.map(|axis| axis * offset));
    draw.rotate_about(y, yaw, pivot);
    let tray_drawn = game.native_draw_model(draw, TRAY, 0xffffff);
    let visible = if inward && animation > 10 {
        compound(&entity.nbt, "InsertedBox").and_then(ItemStack::from_nbt)
    } else if !inward && animation < 10 {
        compound(&entity.nbt, "HeldBox").and_then(ItemStack::from_nbt)
    } else {
        None
    };
    let box_drawn = if let Some(stack) = visible {
        draw.translate([0.5, 0.625, 0.5]);
        draw.scale([1.49; 3]);
        game.native_draw_item(draw, &stack, DisplayContext::Fixed, None, 0)
    } else {
        false
    };
    draw.pop();
    if std::env::var_os("CREATE_PACKAGER_RENDER_TRACE").is_some() {
        eprintln!(
            "CREATE_PACKAGER_POSE {} {animation} {inward} {open} {offset:.8} {:.6} {hatch_drawn} {tray_drawn} {box_drawn}",
            draw.game_time, draw.partial
        );
    }
}
