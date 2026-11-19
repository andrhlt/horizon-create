fn transmission_placed(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
    stack: &crate::items::ItemStack,
) {
    if !game.native_authoritative() {
        return;
    }
    match game.native_block(pos).as_str() {
        crate::game::create_sticker::STICKER => {
            game.with_level(|_, level, ticks| {
                let pos = horizon_core::position::BlockPos::new(pos[0], pos[1], pos[2]);
                let state = horizon_world::level::LevelAccess::block_state(level, pos);
                crate::game::create_sticker::placed(level, ticks, pos, state);
            });
        }
        crate::game::create_steam_whistle::WHISTLE => {
            game.with_level(|_, level, ticks| {
                let pos = horizon_core::position::BlockPos::new(pos[0], pos[1], pos[2]);
                let state = horizon_world::level::LevelAccess::block_state(level, pos);
                crate::game::create_steam_whistle::neighbor(level, ticks, pos, state);
            });
        }
        "create:clutch" | "create:gearshift" => {
            crate::game::create_machines::update_clutch(game, pos);
        }
        crate::game::create_factory_gauge::BLOCK => {
            crate::game::create_factory_gauge::placed(game, pos, stack);
        }
        crate::game::create_stock_link::LINK => {
            game.with_level(|_, level, ticks| {
                let pos = horizon_core::position::BlockPos::new(pos[0], pos[1], pos[2]);
                let state = horizon_world::level::LevelAccess::block_state(level, pos);
                crate::game::create_stock_link::update_power(level, ticks, pos, state);
            });
            crate::game::create_stock_link::placed(game, pos, stack);
        }
        crate::game::create_redstone_requester::REQUESTER => {
            game.with_level(|_, level, ticks| {
                let pos = horizon_core::position::BlockPos::new(pos[0], pos[1], pos[2]);
                let state = horizon_world::level::LevelAccess::block_state(level, pos);
                crate::game::create_redstone_requester::neighbor(level, ticks, pos, state);
            });
            crate::game::create_stock_link::placed_message(game, stack);
        }
        crate::game::create_stock_ticker::TICKER => {
            crate::game::create_stock_link::placed(game, pos, stack);
        }
        _ => {}
    }
}
