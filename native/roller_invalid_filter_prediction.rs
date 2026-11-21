fn roller_invalid_filter_prediction(
    game: &mut Game<'_>,
    hand: Hand,
) -> std::ops::ControlFlow<bool> {
    let Some(hit) = game.pick() else {
        return std::ops::ControlFlow::Continue(());
    };
    if hand != Hand::Main || !crate::game::create_roller::claims_filter_box(game, hit.pos) {
        return std::ops::ControlFlow::Continue(());
    }
    let Some(stack) = game.held().cloned() else {
        return std::ops::ControlFlow::Continue(());
    };
    if crate::game::create_roller::invalid_filter_item(game, &stack, hit.pos) {
        return std::ops::ControlFlow::Break(true);
    }
    // Java stores ordinary block materials without consuming them. Horizon's
    // generic BlockItem prediction consumes once, so pre-credit that prediction
    // while still allowing the authoritative UseItemOn packet through.
    if !game.creative
        && crate::game::create_roller::valid_filter_item(game, &stack, hit.pos)
        && let Some(held) = game.held_mut().as_mut()
    {
        held.count += 1;
    }
    std::ops::ControlFlow::Continue(())
}
