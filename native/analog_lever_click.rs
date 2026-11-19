fn analog_lever_click(game: &mut crate::game::Game<'_>, pos: [i32; 3], canceled: &mut bool) {
    if !*canceled && crate::game::create_clipboard_copy::interact(game, pos, false) {
        *canceled = true;
        return;
    }
    crate::game::create_analog_lever::click(game, pos, canceled);
    crate::game::create_latches::manual(game, pos, canceled);
    crate::game::create_desk_bell::click(game, pos, canceled);
}
