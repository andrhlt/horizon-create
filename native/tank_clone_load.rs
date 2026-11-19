fn tank_clone_load(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
    entity: &mut crate::containers::BlockEntity,
) {
    use horizon_world::nbt::Tag;
    let crate::containers::BlockEntity::Mod(incoming) = entity else { return };
    if !matches!(incoming.id.as_str(), "create:fluid_tank" | "create:creative_fluid_tank") { return; }
    let Some((_, group)) = crate::game::create_fluid_tank::parts(game, pos) else { return };
    let Some(root) = group.first() else { return };
    incoming.runtime.insert("CreateTankCapability".into(), Tag::IntArray(root.to_vec()));
}
