fn copycat_click(game: &mut Game<'_>, hit: Option<&Hit>) -> std::ops::ControlFlow<Result<bool>> {
    if hit.is_some_and(|hit| {
        game.native_block(hit.pos) == "create:copycat_bars"
            && game
                .held()
                .is_some_and(|stack| stack.item.as_ref() == "create:wrench")
            && crate::game::create_wrench::apply(game, hit.pos, hit.face)
    }) {
        return std::ops::ControlFlow::Break(Ok(true));
    }
    if hit.is_some_and(|hit| crate::game::create_copycat::use_material(game, hit)) {
        game.swing_arm();
        std::ops::ControlFlow::Break(Ok(true))
    } else {
        std::ops::ControlFlow::Continue(())
    }
}
