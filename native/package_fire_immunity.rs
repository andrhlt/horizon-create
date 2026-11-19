fn package_fire_immunity(mob: &crate::mobs::Mob, immune: &mut bool) {
    use horizon_world::nbt::Tag;

    *immune |= mob.kind.id == crate::mobs::create_package_style::ENTITY
        && mob
            .extra
            .main_hand_stack()
            .and_then(|stack| stack.data())
            .and_then(|data| {
                data.other.iter().find_map(|(name, value)| {
                    (name == "minecraft:damage_resistant").then_some(value)
                })
            })
            .and_then(|value| value.get("types"))
            .is_some_and(|types| match types {
                Tag::String(id) => id.to_string().is_ok_and(|tag| tag == "#minecraft:is_fire"),
                Tag::List(ids) => ids.iter().any(|id| {
                    matches!(id, Tag::String(tag) if tag.to_string().is_ok_and(|tag| tag == "#minecraft:is_fire"))
                }),
                _ => false,
            });
}
