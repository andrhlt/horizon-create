fn click_elevator_controls(
    game: &mut Game<'_>,
    hand: horizon_client::first_person::Hand,
) -> std::ops::ControlFlow<bool> {
    if hand == horizon_client::first_person::Hand::Main
        && crate::game::create_elevator_floors::click_controls(game)
    {
        std::ops::ControlFlow::Break(true)
    } else {
        std::ops::ControlFlow::Continue(())
    }
}
