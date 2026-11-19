fn world_door_survival(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    survives: &mut Option<bool>,
) {
    if survives.is_none() {
        *survives = crate::game::create_elevator_doors::world_door_survives(level, state);
    }
}
