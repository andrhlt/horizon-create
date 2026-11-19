fn minecart_coupling_tick(game: &mut crate::game::Game<'_>, result: ()) -> () {
    let mut move_cart = |game: &mut crate::game::Game<'_>, id: u32, delta: [f64; 3]| {
        let Some(index) = game.carts.iter().position(|cart| cart.id == id) else { return; };
        let mut cart = game.carts[index].clone();
        game.move_cart(&mut cart, horizon_core::geometry::Vec3::new(delta[0], delta[1], delta[2]));
        cart.velocity = cart.velocity.scale(0.95);
        game.carts[index] = cart;
    };
    crate::game::create_minecart_coupling::tick_straight_pairs(game, &mut move_cart);
    crate::game::create_minecart_coupling::tick_hard_straight_pairs(game, &mut move_cart);
    crate::game::create_minecart_coupling::tick_hard_cardinal_slope_pairs(game, &mut move_cart);
    result
}
