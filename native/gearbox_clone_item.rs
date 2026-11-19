fn gearbox_clone_item(
    game: &crate::game::Game<'_>,
    block: &str,
    pos: [i32; 3],
    state: horizon_world::registry::BlockStateId,
    stack: &mut Option<crate::items::ItemStack>,
) {
    if block == crate::game::create_lectern_controller::BLOCK {
        *stack = Some(crate::items::ItemStack::new("minecraft:lectern", 1));
    }
    if block == "create:elevator_contact" {
        *stack = Some(crate::items::ItemStack::new("create:redstone_contact", 1));
    }
    if stack.is_none() && crate::game::create_toolbox::block(block) {
        *stack = crate::game::create_toolbox::packed(game, pos);
    }
    if stack.is_none() && crate::game::create_backtank::block(block) {
        *stack = crate::game::create_backtank::packed(game, pos);
    }
    if stack.is_none() && block == crate::game::create_encased_fluid_pipe::BLOCK {
        *stack = Some(crate::items::ItemStack::new(crate::game::create_fluids::PIPE, 1));
    }
    if block == "create:gearbox" && stack.is_none()
        && crate::game::create_shaft::gearbox_item(game, state) == crate::game::create_shaft::VERTICAL_GEARBOX
    {
        *stack = Some(crate::items::ItemStack::new(crate::game::create_shaft::VERTICAL_GEARBOX, 1));
    }
}
