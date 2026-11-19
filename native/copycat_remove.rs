fn copycat_remove(
    level: &mut crate::game::GameLevel<'_>,
    pos: horizon_core::position::BlockPos,
    old: horizon_world::registry::BlockStateId,
    side_effects: bool,
) {
    crate::game::create_factory_gauge::remove(level, pos, side_effects);
    crate::game::create_lectern_controller::remove(level, pos, old, side_effects);
    crate::game::create_table_cloth::remove(level, pos, side_effects);
    crate::game::create_placard::remove(level, pos, side_effects);
    crate::game::create_crafter::drop_cover(level, pos, side_effects);
    crate::game::create_copycat::remove(level, pos, side_effects);
}
