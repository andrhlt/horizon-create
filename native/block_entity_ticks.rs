fn block_entity_ticks(block: &str, ticks: &mut bool) {
    crate::game::create_machines::block_entity_ticks(block, ticks);
    *ticks |= crate::game::create_elevator_doors::sliding(block);
    *ticks |= crate::game::create_packager::is_packager(block);
    *ticks |= block == crate::game::create_stock_link::LINK;
    *ticks |= block == crate::game::create_analog_lever::LEVER;
    *ticks |= block == crate::game::create_desk_bell::BELL;
    *ticks |= block == crate::game::create_steam_whistle::WHISTLE;
    *ticks |= crate::game::create_latches::is_pulse(block);
}
