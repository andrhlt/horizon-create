fn block_entity_tick(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
    entity: &mut crate::containers::ModBlockEntity,
) {
    if entity.id == crate::game::create_placard::ITEM {
        crate::game::create_placard::tick(game, pos, entity);
    } else if crate::game::create_elevator_doors::sliding(&entity.id) {
        crate::game::create_elevator_doors::tick_world_door(game, pos, entity);
    } else if crate::game::create_packager::is_packager(&entity.id) {
        crate::game::create_packager::tick(game, pos, entity);
    } else if entity.id == crate::game::create_stock_link::LINK {
        crate::game::create_stock_link::tick(game, pos, entity);
    } else if entity.id == crate::game::create_steam_whistle::WHISTLE {
        crate::game::create_steam_whistle_audio::server_tick(game, pos, entity);
    } else if entity.id == crate::game::create_desk_bell::BELL {
        crate::game::create_desk_bell::tick(game, pos, entity);
    } else if crate::game::create_latches::is_pulse(&entity.id) {
        crate::game::create_latches::pulse_tick(game, pos, entity);
    } else {
        crate::game::create_machines::block_entity_tick(game, pos, entity);
    }
}
