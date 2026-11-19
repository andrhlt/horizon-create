fn stockpile_right_click_prediction(
    game: &Game<'_>,
    hit: &super::Hit,
    held: Option<&ItemStack>,
) -> std::ops::ControlFlow<(InteractionResult, DryUse)> {
    use crate::game::create_chain_conveyor_connect::CHAIN;
    use crate::game::create_machines::{CONVEYOR, FROGPORT};
    use crate::game::create_smart_observer::OBSERVER;
    use crate::game::create_threshold_switch::{THRESHOLD_SWITCH, filter_hit};

    let block = game.native_block(hit.pos);
    if game.may_build()
        && held
            .is_some_and(|stack| crate::game::create_chain_conveyor_span::selects_span(game, stack))
    {
        return std::ops::ControlFlow::Break((InteractionResult::Success, DryUse::default()));
    }
    if block == CONVEYOR
        && game.may_build()
        && held.is_some_and(|stack| {
            matches!(stack.item.as_ref(), CHAIN | FROGPORT)
                || crate::game::create_chain_conveyor_target::selects_loop(game, hit.pos, stack)
        })
    {
        return std::ops::ControlFlow::Break((InteractionResult::Success, DryUse::default()));
    }
    if block == FROGPORT
        && !game.remote_shift_down()
        && held.is_some_and(|stack| {
            matches!(stack.item.as_ref(), "create:goggles" | "create:clipboard")
        })
    {
        return std::ops::ControlFlow::Break((InteractionResult::Success, DryUse::default()));
    }
    if block == OBSERVER && held.is_some_and(|stack| stack.item.as_ref() == "create:wrench") {
        return std::ops::ControlFlow::Break((InteractionResult::Success, DryUse::default()));
    }
    if block == OBSERVER
        && game.may_build()
        && !game.remote_shift_down()
        && held.is_none_or(|stack| {
            !matches!(
                stack.item.as_ref(),
                "create:wrench" | "create:mechanical_arm" | "create:clipboard"
            )
        })
        && filter_hit(game, hit, false)
    {
        return std::ops::ControlFlow::Break((InteractionResult::Success, DryUse::default()));
    }
    if block == THRESHOLD_SWITCH
        && (held.is_some_and(|stack| stack.item.as_ref() == "create:wrench")
            || !(game.remote_shift_down()
                && (game.stack_in(game.selected).is_some() || game.offhand.is_some())))
    {
        std::ops::ControlFlow::Break((InteractionResult::Success, DryUse::default()))
    } else {
        std::ops::ControlFlow::Continue(())
    }
}
