fn bracket_remove(
    level: &mut crate::game::GameLevel<'_>,
    pos: horizon_core::position::BlockPos,
    side_effects: bool,
) {
    crate::game::create_bracket::on_remove(level, pos, side_effects);
}
