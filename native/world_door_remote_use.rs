fn world_door_remote_use(
    game: &Game<'_>,
    hit: &super::Hit,
) -> std::ops::ControlFlow<(InteractionResult, DryUse)> {
    let hands_full = game.stack_in(game.selected).is_some() || game.offhand.is_some();
    if !(game.remote_shift_down() && hands_full)
        && crate::game::create_elevator_doors::sliding(&game.native_block(hit.pos))
    {
        // The vanilla predictor only toggles the clicked leaf and uses a
        // different motion. Let the paired state arrive from the authority.
        std::ops::ControlFlow::Break((InteractionResult::Success, DryUse::default()))
    } else {
        std::ops::ControlFlow::Continue(())
    }
}
