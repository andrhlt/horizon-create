fn stock_link_use(game: &mut Game<'_>, hit: Option<&Hit>) -> std::ops::ControlFlow<Result<bool>> {
    if hit.is_some_and(|hit| crate::game::create_factory_gauge::connect_link(game, hit.pos)) {
        return std::ops::ControlFlow::Break(Ok(true));
    }
    if hit.is_some_and(|hit| crate::game::create_linked_controller::use_link(game, hit.pos)) {
        game.swing_arm();
        return std::ops::ControlFlow::Break(Ok(true));
    }
    if hit.is_some_and(|hit| {
        crate::game::create_lectern_controller::detach(game, hit.pos)
            || game.held().cloned().is_some_and(|stack|
                crate::game::create_lectern_controller::attach(game, hit.pos, &stack))
    }) {
        game.swing_arm();
        return std::ops::ControlFlow::Break(Ok(true));
    }
    if hit.is_some_and(|hit| crate::game::create_linked_controller::use_mount(game, hit.pos)) {
        return std::ops::ControlFlow::Break(Ok(true));
    }
    if hit.is_some_and(|hit| crate::game::create_factory_gauge::open_config(game, hit.pos, hit.point)) {
        return std::ops::ControlFlow::Break(Ok(true));
    }
    if hit.is_some_and(|hit| {
        crate::game::create_item_hatch::click(game, hit.pos, hit.point)
            || crate::game::create_backtank::equip(game, hit.pos)
    }) {
        return std::ops::ControlFlow::Break(Ok(true));
    }
    if hit.is_none() && crate::game::create_linked_controller::use_air(game) {
        return std::ops::ControlFlow::Break(Ok(true));
    }
    if crate::game::create_stock_link::use_item(game, hit.map(|hit| hit.pos))
        || hit.is_some_and(|hit| {
            crate::game::create_requester_editor::open(game, hit.pos)
                || crate::game::create_stock_keeper_screen::use_burner(game, hit.pos)
                || crate::game::create_stock_ticker::missing_keeper(game, hit.pos)
        })
    {
        game.swing_arm();
        std::ops::ControlFlow::Break(Ok(true))
    } else {
        std::ops::ControlFlow::Continue(())
    }
}
