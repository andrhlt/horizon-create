fn elevator_seat_interact(game: &mut Game<'_>, entity: i32, kind: &str, cancel: &mut bool) {
    if !*cancel
        && kind == "minecraft:interaction"
        && crate::game::create_elevator_seats::board_moving(game, entity as u32)
    {
        *cancel = true;
    }
}
