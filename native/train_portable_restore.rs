fn train_portable_restore(
    game: &mut crate::game::Game<'_>,
    chunk: [i32; 2],
    new: bool,
) {
    if new {
        return;
    }
    let [x, z] = chunk.map(|coord| f64::from(coord) * 16.0 + 8.0);
    let receivers: Vec<_> = game
        .world
        .block_entities
        .mods_near(x, z, 0.0)
        .filter(|pos| {
            matches!(
                game.world.block_entities.get(pos),
                Some(crate::containers::BlockEntity::Mod(entity))
                    if matches!(
                        entity.id.as_str(),
                        "create:portable_storage_interface" | "create:portable_fluid_interface"
                    )
                    && entity.nbt.contains_key(&"TrainPort".into())
                    && !entity.nbt.contains_key(&"Bearing".into())
            )
        })
        .copied()
        .collect();
    for (x, y, z) in receivers {
        game.native_with_mod_block_entity([x, y, z], |entity| {
            // The saved numeric owner belongs to the previous carriage instance.
            entity.nbt.remove(&"TrainPort".into());
            entity.nbt.remove(&"LastContact".into());
        });
    }
}
