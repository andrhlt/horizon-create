fn linked_controller_control_key(game: &mut Game<'_>, key: winit::keyboard::KeyCode) -> std::ops::ControlFlow<Result<()>> {
    if crate::game::create_linked_controller::key(game, key, true, false) {
        std::ops::ControlFlow::Break(Ok(()))
    } else {
        std::ops::ControlFlow::Continue(())
    }
}
