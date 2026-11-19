fn create_structure_load(
    level: &mut crate::game::GameLevel<'_>,
    pos: horizon_core::position::BlockPos,
    nbt: &mut horizon_world::nbt::Compound,
) {
    if let Some(name) = nbt
        .get(&"CustomName".into())
        .and_then(horizon_client::block_entity_nbt::component)
    {
        level.world.block_names.insert((pos.x, pos.y, pos.z), name);
    }
    crate::game::create_crushing::load_structure(nbt);
    crate::game::create_fluids::load_structure(nbt);
    if matches!(nbt.get(&"id".into()), Some(Tag::String(id)) if id.to_string_lossy() == crate::game::create_hose::HOSE)
    {
        crate::game::create_hose::load_structure(nbt);
    }
    use horizon_world::nbt::Tag;
    if matches!(nbt.get(&"id".into()), Some(Tag::String(id)) if matches!(id.to_string_lossy().as_str(), crate::game::create_belt::BELT | crate::game::create_arm::ARM | crate::game::create_press::PRESS | crate::game::create_crafter::CRAFTER | crate::game::create_sequencer::SEQUENCER | "create:deployer"))
    {
        crate::game::create_machines::set_float(nbt, "Speed", 0.0);
    }
    if matches!(nbt.get(&"id".into()), Some(Tag::String(id)) if id.to_string_lossy() == "create:deployer")
    {
        nbt.insert("AttachOnFirstTick".into(), Tag::Byte(1));
    }
    if matches!(nbt.get(&"id".into()), Some(Tag::String(id)) if id.to_string_lossy() == crate::game::create_mixer::MIXER)
    {
        crate::game::create_machines::set_float(nbt, "Speed", 0.0);
        crate::game::create_machines::set_float(nbt, "HeadOffset", 7.0 / 16.0);
    }
}
