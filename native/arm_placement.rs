fn arm_placement(game: &mut crate::game::Game<'_>, stack: &crate::items::ItemStack, pos: [i32; 3]) {
    crate::game::create_chain_conveyor_target::placed(game, pos, stack);
    crate::game::create_train::place_controls(game, pos, stack);
    crate::game::create_clipboard_block::placed(game, pos, stack);
    crate::game::create_toolbox::placed(game, pos, stack);
    crate::game::create_backtank::placed(game, pos, stack);
    crate::game::create_arm::setup(game, pos, stack);
    crate::game::create_ejector_target::place(game, pos, stack);
}
