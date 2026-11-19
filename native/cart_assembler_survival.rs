fn cart_assembler_survival(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    survives: &mut Option<bool>,
) {
    if level.native_state_block(state) == Some(crate::game::create_cart_assembler::ASSEMBLER) {
        *survives = Some(false);
    }
}
