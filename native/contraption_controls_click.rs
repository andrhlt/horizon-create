fn contraption_controls_click(game: &mut Game<'_>, entity: i32, kind: &str, cancel: &mut bool) {
    if kind == "minecraft:interaction"
        && crate::game::create_contraption_controls::click(game, entity as u32)
    {
        *cancel = true;
    }
}
