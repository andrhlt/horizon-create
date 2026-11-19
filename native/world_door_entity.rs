fn world_door_entity(
    block: &str,
    properties: &horizon_world::block_state_properties::BlockProperties,
    entity: &mut Option<(String, horizon_world::nbt::Compound)>,
) {
    if crate::game::create_elevator_doors::sliding(block)
        && properties.get("half").is_some_and(|half| half == "lower")
        && entity.is_none()
    {
        let open = properties.get("open").is_some_and(|open| open == "true");
        *entity = Some((
            block.to_owned(),
            crate::game::create_elevator_doors::new_world_door(open),
        ));
    }
}
