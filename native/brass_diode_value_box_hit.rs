fn brass_diode_value_box_hit(
    game: &crate::game::Game<'_>,
    pos: [i32; 3],
    face: [i32; 3],
    point: [f64; 3],
    claimed: &mut bool,
) {
    if game
        .held()
        .is_some_and(|stack| stack.item.as_ref() == crate::game::create_clipboard::ITEM)
        && !game.native_sneaking()
    {
        return;
    }
    *claimed =
        crate::game::create_speed_controller_controls::claims_diode_hit(game, pos, face, point);
}
