fn gearbox_piston_transfer(
    level: &mut crate::game::GameLevel<'_>,
    pos: horizon_core::position::BlockPos,
    state: horizon_world::registry::BlockStateId,
    previous: Option<BlockStateId>,
) -> Option<BlockStateId> {
    use crate::containers::BlockEntity;
    use horizon_world::nbt::Tag;

    if level.native_authoritative
        && previous.and_then(|old| level.registry.state(old))
            .is_some_and(|old| old.name == "minecraft:moving_piston")
        && level.registry.state(state)
            .is_some_and(|new| new.name == crate::game::create_machines::GEARBOX)
    {
        // Java attaches the new kinetic block entity on the next tick.
        let mut definition = None;
        crate::game::create_machines::block_entity(crate::game::create_machines::GEARBOX, &mut definition);
        if let Some((id, mut nbt)) = definition {
            nbt.insert("PistonPlacedTick".into(), Tag::Long(level.world.game_time));
            level.world.block_entities.insert(
                (pos.x, pos.y, pos.z),
                BlockEntity::Mod(Box::new(horizon_client::containers::ModBlockEntityFields {
                    id,
                    nbt,
                    ..Default::default()
                }.into())),
            );
        }
    }
    previous
}
