fn chain_pickup_client(
    game: &mut Game<'_>,
    hand: horizon_client::first_person::Hand,
) -> std::ops::ControlFlow<bool> {
    if hand == horizon_client::first_person::Hand::Main
        && crate::game::create_chain_conveyor_packages::send_air_pickup(game)
    {
        std::ops::ControlFlow::Break(true)
    } else {
        std::ops::ControlFlow::Continue(())
    }
}
