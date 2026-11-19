fn extendo_grip_block_break(game: &mut crate::game::Game<'_>, canceled: &bool) {
    if !*canceled {
        crate::game::create_extendo_grip_wear::wear(game);
    }
}
