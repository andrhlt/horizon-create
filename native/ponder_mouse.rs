fn ponder_mouse(game: &Game<'_>, screen: &NativeScreenView<'_>, button: i32, canceled: &mut bool) {
    crate::game::create_ponder::mouse(game, screen, button, canceled);
}
