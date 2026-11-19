fn sticker_signal_options(level: &crate::game::GameLevel<'_>, state: horizon_world::registry::BlockStateId, options: &mut (bool,bool)) {
    if level.native_state_block(state)==Some("create:sticker") {options.0=false;}
}
