fn block_entity(block: &str, entity: &mut Option<(String, horizon_world::nbt::Compound)>) {
    crate::game::create_machines::block_entity(block, entity);
    if block == crate::game::create_sticker::STICKER { *entity = Some((block.to_owned(), Default::default())); }
    if block == crate::game::create_lectern_controller::BLOCK {
        *entity = Some((block.to_owned(), Default::default()));
    }
    if block == crate::game::create_fake_track::FAKE_TRACK {
        *entity = Some((block.to_owned(), Default::default()));
    }
    if crate::game::create_packager::is_packager(block) {
        *entity = Some((
            block.to_owned(),
            crate::game::create_packager_state::initialize(),
        ));
    }
    if block == crate::game::create_analog_lever::LEVER {
        *entity = Some((
            block.to_owned(),
            crate::game::create_analog_lever::new_tag(),
        ));
    }
    if crate::game::create_latches::is_pulse(block) {
        *entity = Some((
            block.to_owned(),
            crate::game::create_latches::pulse_nbt(block),
        ));
    }
    if block == crate::game::create_redstone_requester::REQUESTER {
        *entity = Some((
            block.to_owned(),
            crate::game::create_redstone_requester::new_tag(),
        ));
    }
    if block == crate::game::create_stock_ticker::TICKER {
        *entity = Some((
            block.to_owned(),
            crate::game::create_stock_ticker::new_tag(),
        ));
    }
    if block == crate::game::create_factory_gauge::BLOCK {
        *entity = Some((crate::game::create_factory_gauge::ENTITY.to_owned(), Default::default()));
    }
    if block == crate::game::create_stock_link::LINK {
        *entity = Some((block.to_owned(), crate::game::create_stock_link::new_tag()));
    }
    if block == crate::game::create_steam_whistle::WHISTLE {
        *entity = Some((block.to_owned(), Default::default()));
    }
    if block == crate::game::create_desk_bell::BELL {
        *entity = Some((block.to_owned(), Default::default()));
    }
}
