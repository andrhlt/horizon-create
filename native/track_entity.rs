fn track_entity(
    block: &str,
    properties: &horizon_world::block_state_properties::BlockProperties,
    entity: &mut Option<(String, horizon_world::nbt::Compound)>,
) {
    if block == crate::game::create_track::TRACK
        && properties.get("turn").is_some_and(|value| value == "true")
        && entity.is_none()
    {
        *entity = Some((block.into(), Default::default()));
    }
}
