fn controller_rail_cart_move(game: &Game<'_>, cart: &mut Minecart, pos: [i32; 3]) {
    crate::game::create_controller_rail::move_cart(game, cart, pos, game.max_speed(cart));
}
