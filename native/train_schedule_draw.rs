fn train_schedule_draw(game: &Game<'_>, screen: &NativeScreenView<'_>, batch: &mut HudBatch) {
    crate::game::create_train_schedule::render(game, screen, batch);
}
