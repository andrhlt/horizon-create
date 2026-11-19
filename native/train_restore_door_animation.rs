fn train_restore_door_animation(
    game: &mut crate::game::Game<'_>,
    tag: &mut horizon_world::nbt::Tag,
    kind: &str,
) {
    crate::game::create_train::restore_door_animation(game, tag, kind);
}
