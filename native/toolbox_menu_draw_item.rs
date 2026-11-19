fn toolbox_menu_draw_item(
    game: &crate::game::Game<'_>,
    batch: &mut horizon_client::hud::HudBatch,
    slot: usize,
    stack: &Option<crate::items::ItemStack>,
    x: f32,
    y: f32,
) -> std::ops::ControlFlow<()> {
    if crate::game::create_toolbox_menu::draw_compartment_item(game, batch, slot, stack, x, y) {
        std::ops::ControlFlow::Break(())
    } else {
        std::ops::ControlFlow::Continue(())
    }
}
