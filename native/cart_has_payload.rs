fn cart_has_payload(game: &Game<'_>, id: u32) -> std::ops::ControlFlow<bool> {
    if crate::game::create_cart_assembler::has_payload(game, id) {
        std::ops::ControlFlow::Break(true)
    } else {
        std::ops::ControlFlow::Continue(())
    }
}
