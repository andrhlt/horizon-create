fn create_item_on_prediction(game: &mut Game<'_>, hand: Hand, used: bool) -> bool {
    if used || game.remote_shift_down() {
        return used;
    }
    let Some(hit) = game.pick() else {
        return false;
    };
    game.with_hand(hand, |game| {
        game.held().is_some_and(|stack| {
            ((game.native_block(hit.pos) == "create:creative_fluid_tank"
                || (game.creative && game.native_block(hit.pos) == "create:fluid_tank"))
                && (matches!(stack.item.as_ref(), "minecraft:bucket" | "minecraft:glass_bottle")
                    || crate::game::create_item_drain::operation(game, stack).is_some()))
                || stack.item.as_ref() == "create:wand_of_symmetry"
                || crate::game::create_package_world::predicts_placement(game, stack, &hit)
        }) || crate::game::create_creative_crate::targets(game, &hit)
    })
}
