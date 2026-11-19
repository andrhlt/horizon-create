fn speed_controller_placement_redirect(
    game: &mut crate::game::Game<'_>,
    context: &mut horizon_world::level::PlaceContext,
) {
    crate::game::create_cogwheel::redirect_placement(game, context);
    crate::game::create_shaft::redirect_placement(game, context);
    crate::game::create_sail::redirect_placement(game, context);
    crate::game::create_table_cloth::redirect_placement(game, context);
    crate::game::create_copycat::redirect_placement(game, context);
    crate::game::create_metal_ladder::redirect_placement(game, context);
    crate::game::create_speed_controller::redirect_cog_placement(game, context);
    crate::game::create_press::redirect_placement(game, context);
}
