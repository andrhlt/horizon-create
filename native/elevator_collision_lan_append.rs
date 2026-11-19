fn elevator_collision_lan_append(game: &Game<'_>, boxes: &mut Vec<horizon_core::geometry::Aabb>) {
    crate::game::create_elevator_collision::append_server(game, boxes);
}
