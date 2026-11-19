fn cart_assembler_pickup_interact(
    game: &mut crate::game::Game<'_>,
    entity: i32,
    kind: &str,
    stack: Option<&crate::items::ItemStack>,
    claimed: &mut bool,
) {
    if !*claimed
        && kind == "minecraft:minecart"
        && crate::game::create_cart_assembler_pickup::pickup_portable(game, entity as u32, stack)
    {
        *claimed = true;
    }
}
