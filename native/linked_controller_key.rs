fn linked_controller_key(game: &mut Game<'_>, key: winit::keyboard::KeyCode, pressed: bool, repeat: bool) -> std::ops::ControlFlow<Result<()>> {
    if crate::game::create_linked_controller::key(game, key, pressed, repeat) {
        std::ops::ControlFlow::Break(Ok(()))
    } else {
        std::ops::ControlFlow::Continue(())
    }
}
