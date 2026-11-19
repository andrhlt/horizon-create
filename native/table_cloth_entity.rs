fn table_cloth_entity(
    block: &str,
    properties: &horizon_world::block_state_properties::BlockProperties,
    entity: &mut Option<(String, horizon_world::nbt::Compound)>,
) {
    crate::game::create_table_cloth::entity_from_state(block, properties, entity);
}
