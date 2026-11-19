fn elevator_floors_editor_char(game: &Game<'_>, c: char, canceled: &mut bool) {
    crate::game::create_elevator_floors::editor_char(game, c, canceled);
}
