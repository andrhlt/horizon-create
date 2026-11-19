fn linked_controller_remote(game: &mut Game<'_>) {
    if !game.remote.as_ref().is_some_and(|remote| remote.is_destroying) {
        crate::game::create_linked_controller::remote_use(game);
    }
}
