fn elevator_collision_finish(game: &mut Game<'_>, jump: bool) {
    crate::game::create_elevator_collision::finish_motion(game, jump);
}
