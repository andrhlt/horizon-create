fn world_door_stateful(block: &str, stateful: &mut bool) {
    *stateful |= crate::game::create_elevator_doors::sliding(block);
}
