fn linked_controller_control_release(game: &mut Game<'_>, key: winit::keyboard::KeyCode) -> std::ops::ControlFlow<()> {
    if crate::game::create_linked_controller::key(game, key, false, false) {
        std::ops::ControlFlow::Break(())
    } else {
        std::ops::ControlFlow::Continue(())
    }
}
