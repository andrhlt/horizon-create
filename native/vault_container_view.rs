fn vault_container_view(
    containers: &Containers<'_>,
    pos: Pos,
) -> std::ops::ControlFlow<Option<View>> {
    let Some((_, parts)) = crate::game::create_vault::parts(
        containers.world,
        containers.registry,
        [pos.0, pos.1, pos.2],
    ) else {
        return std::ops::ControlFlow::Continue(());
    };
    use crate::game::create_vault::SLOTS;
    let parts = parts
        .into_iter()
        .filter(|&[x, y, z]| {
            matches!(containers.world.block_entities.get(&(x, y, z)),
                Some(BlockEntity::Mod(entity)) if !entity.id.is_empty())
        })
        .map(|[x, y, z]| ((x, y, z), SLOTS))
        .collect::<Vec<_>>();
    std::ops::ControlFlow::Break((!parts.is_empty()).then_some(View {
        parts,
        kind: Kind::Generic,
        container: None,
    }))
}
