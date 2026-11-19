fn elevator_collision_append(game: &Game<'_>, boxes: &mut Vec<Aabb>) {
    crate::game::create_elevator_collision::append(game, boxes);
}
