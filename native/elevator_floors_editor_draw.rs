fn elevator_floors_editor_draw(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    batch: &mut HudBatch,
) {
    crate::game::create_elevator_floors::draw_editor(game, screen, batch);
}
