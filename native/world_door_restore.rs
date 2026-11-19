fn world_door_restore(game: &mut crate::game::Game<'_>, chunk: [i32; 2], new: bool) {
    if !new {
        crate::game::create_elevator_doors::restore_world_doors(game, chunk);
    }
}
