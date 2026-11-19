fn controller_rail_signal(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    output: &mut i32,
) {
    if let Some(power) = crate::game::create_controller_rail::output(level, state) {
        *output = power;
    }
}
