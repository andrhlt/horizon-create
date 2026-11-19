fn rose_lamp_signal_options(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    options: &mut (bool, bool),
) {
    if crate::game::create_rose_lamp::is_lamp(level, state) {
        *options = (false, true);
    }
}
