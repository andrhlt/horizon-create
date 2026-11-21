fn block_entity_update_tag(
    entity: &crate::containers::ModBlockEntity,
    tag: &mut Option<horizon_world::nbt::Compound>,
) {
    if matches!(
        entity.id.as_str(),
        crate::game::create_fluid_tank::TANK | crate::game::create_fluid_tank::CREATIVE
    ) {
        // Tank fluid and controller dimensions drive the client-side tank
        // renderer. Keep the update tag in step with the authoritative entity
        // so both chunk loads and later fill/drain changes reach clients.
        tag.get_or_insert_with(Default::default)
            .extend(entity.nbt.clone());
    }
    if entity.id == crate::game::create_sticker::STICKER { tag.get_or_insert_with(Default::default); }
    if crate::game::create_elevator_doors::sliding(&entity.id) {
        crate::game::create_elevator_doors::world_door_update(entity, tag);
    }
    if entity.id == crate::game::create_table_cloth::ENTITY {
        tag.get_or_insert_with(Default::default).extend(entity.nbt.clone());
    }
    if entity.id == crate::game::create_placard::ITEM {
        use horizon_world::nbt::{Compound, Tag};
        let item = entity.nbt.get(&"Item".into()).cloned().unwrap_or_else(|| Tag::Compound(Compound::new()));
        tag.get_or_insert_with(Default::default).insert("Item".into(), item);
    }
    crate::game::create_bracket::update_tag(entity, tag);
    crate::game::create_toolbox_menu::update_tag(entity, tag);
    if crate::game::create_packager::is_packager(&entity.id) {
        use horizon_world::nbt::{Compound, Tag};

        let update = tag.get_or_insert_with(Default::default);
        update.extend(entity.nbt.clone());
        for key in ["HeldBox", "InsertedBox"] {
            update
                .entry(key.into())
                .or_insert_with(|| Tag::Compound(Compound::new()));
        }
    }
    crate::game::create_chain_conveyor_visual::update_tag(entity, tag);
    crate::game::create_funnel_flap::update_tag(entity, tag);
    if entity.id == crate::game::create_chassis_range::ENTITY
        && let Some(range) = entity.nbt.get(&"ScrollValue".into())
    {
        tag.get_or_insert_with(Default::default)
            .insert("ScrollValue".into(), range.clone());
    }
    if entity.id == crate::game::create_redstone_link::LINK {
        tag.get_or_insert_with(Default::default)
            .extend(crate::game::create_redstone_link::update_tag(entity));
    }
    if entity.id == crate::game::create_train_signal::SIGNAL {
        let target = tag.get_or_insert_with(Default::default);
        for key in [
            "State",
            "Overlay",
            "TargetTrack",
            "TargetDirection",
            "Power",
        ] {
            if let Some(value) = entity.nbt.get(&key.into()) {
                target.insert(key.into(), value.clone());
            }
        }
    }
    if entity.id == crate::game::create_factory_gauge::ENTITY
        || entity.id == crate::game::create_display_board::ENTITY
        || entity.id == crate::game::create_analog_lever::LEVER
        || entity.id == crate::game::create_item_drain::DRAIN
        || entity.id == crate::game::create_copycat::ENTITY
    {
        tag.get_or_insert_with(Default::default)
            .extend(entity.nbt.clone());
    }
    if matches!(
        entity.id.as_str(),
        crate::game::create_saw::ENTITY | crate::game::create_drill::ENTITY
    ) && let Some(speed) = entity.nbt.get(&"Speed".into())
    {
        tag.get_or_insert_with(Default::default)
            .insert("Speed".into(), speed.clone());
    }
    if matches!(
        entity.id.as_str(),
        crate::game::create_threshold_switch::THRESHOLD_SWITCH
            | crate::game::create_smart_observer::OBSERVER
            | crate::game::create_track_observer::OBSERVER
    ) && let Some(filter) = entity.nbt.get(&"Filter".into())
    {
        tag.get_or_insert_with(Default::default)
            .insert("Filter".into(), filter.clone());
    }
    if let Some(visual) = crate::game::create_visuals::update_tag(entity) {
        tag.get_or_insert_with(Default::default).extend(visual);
    }
    if crate::game::create_latches::is_pulse(&entity.id)
        && let Some(interval) = entity.nbt.get(&"ScrollValue".into())
    {
        tag.get_or_insert_with(Default::default)
            .insert("ScrollValue".into(), interval.clone());
    }
    if entity.id == crate::game::create_steam_whistle::WHISTLE {
        tag.get_or_insert_with(Default::default).extend(entity.nbt.clone());
    }
    if entity.id == crate::game::create_desk_bell::BELL {
        tag.get_or_insert_with(Default::default)
            .extend(entity.take_client_update_fields());
    }
}
