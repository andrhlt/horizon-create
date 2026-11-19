fn chain_conveyor_wrench(
    game: &mut crate::game::Game<'_>,
) -> std::ops::ControlFlow<Result<Option<Hand>>> {
    match crate::game::create_chain_conveyor_span::use_target(game) {
        Some(hand) => std::ops::ControlFlow::Break(Ok(Some(hand))),
        None => std::ops::ControlFlow::Continue(()),
    }
}
