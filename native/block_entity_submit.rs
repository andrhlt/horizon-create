fn block_entity_submit(
    game: &crate::game::Game<'_>,
    pos: [i32; 3],
    block: &str,
    state: horizon_world::registry::BlockStateId,
    entity: &crate::containers::ModBlockEntity,
    draw: &mut crate::game::native_block_entity_draw::BlockEntityDraw,
) {
    if crate::game::create_elevator_doors::sliding(block) {
        crate::game::create_elevator_doors::render_world_door(game, pos, block, state, entity, draw);
        return;
    }
    if entity.id == crate::game::create_lectern_controller::BLOCK {
        crate::game::create_lectern_controller::render(game, state, draw);
        return;
    }
    if entity.id == crate::game::create_table_cloth::ENTITY {
        if game.native_block_state_property(state, "entity") == Some("true") {
            crate::game::create_table_cloth::render(game, pos, entity, draw);
        }
        return;
    }
    if entity.id == crate::game::create_placard::ITEM {
        crate::game::create_placard::render(game, state, entity, draw);
        return;
    }
    if entity.id == crate::game::create_copycat::ENTITY {
        if let Some(material) = crate::game::create_copycat::material(game, &entity.nbt)
            .or_else(|| game.native_default_state(crate::game::create_copycat::BASE))
        {
            crate::game::create_copycat_model::render(game, state, material, draw, pos);
        }
        return;
    }
    if crate::game::create_toolbox::block(block) {
        crate::game::create_toolbox_animation::render(game, pos, block, state, draw);
        return;
    }
    crate::game::create_bracket::render(game, entity, draw);
    if crate::game::create_packager::is_packager(block) {
        crate::game::create_packager_visual::render(game, state, entity, draw);
    } else if block == crate::game::create_schematicannon::CANNON {
        crate::game::create_schematicannon::render(game, pos, entity, draw);
    } else if block == crate::game::create_analog_lever::LEVER {
        crate::game::create_analog_lever::render(game, state, entity, draw);
    } else if block == crate::game::create_desk_bell::BELL {
        crate::game::create_desk_bell::render(game, state, entity, draw);
    } else if block == crate::game::create_encased_fluid_pipe::BLOCK {
        crate::game::create_encased_pipe_visual::submit(game, pos, draw);
    } else if block == crate::game::create_item_drain::DRAIN {
        crate::game::create_item_drain::render(game, pos, entity, draw);
    } else if matches!(block,
        crate::game::create_threshold_switch::THRESHOLD_SWITCH | crate::game::create_smart_observer::OBSERVER
    ) {
        crate::game::create_threshold_switch::render_filter(game, pos, state, entity, draw);
    } else if block == crate::game::create_drill::DRILL {
        crate::game::create_drill::render(game, state, entity, draw);
    } else if block == crate::game::create_saw::SAW {
        crate::game::create_saw::render(game, state, entity, draw);
    } else {
        crate::game::create_visuals::submit(game, pos, block, state, entity, draw);
    }
}
