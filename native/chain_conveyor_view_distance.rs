fn chain_conveyor_view_distance(block: &str) -> std::ops::ControlFlow<f64> {
    if block == crate::game::create_machines::CONVEYOR {
        std::ops::ControlFlow::Break(crate::game::create_chain_conveyor_visual::VIEW_DISTANCE)
    } else {
        std::ops::ControlFlow::Continue(())
    }
}
