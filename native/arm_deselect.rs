fn arm_deselect(game: &mut crate::game::Game<'_>, pos: [i32; 3], canceled: &mut bool) {
    if !*canceled
        && (crate::game::create_clipboard_copy::interact(game, pos, true)
            || crate::game::create_arm::choose_point(game, pos, true)
            || crate::game::create_ejector_target::deselect(game, pos))
    {
        *canceled = true;
    }
}
