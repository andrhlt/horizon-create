fn funnel_item_placement_priority(game: &crate::game::Game<'_>) -> std::ops::ControlFlow<bool> {
    if game.held().is_some_and(|stack| crate::game::create_funnel::is_funnel_item(&stack.item)) {
        std::ops::ControlFlow::Break(true)
    } else {
        std::ops::ControlFlow::Continue(())
    }
}
