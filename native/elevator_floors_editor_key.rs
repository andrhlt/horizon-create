fn elevator_floors_editor_key(game: &Game<'_>, key: &str, modifiers: u32, canceled: &mut bool) {
    crate::game::create_elevator_floors::editor_key(game, key, modifiers, canceled);
}
