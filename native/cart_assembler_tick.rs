fn cart_assembler_tick(game: &mut Game<'_>, id: u32, kind: &str) {
    if matches!(
        kind,
        "minecraft:minecart" | "minecraft:chest_minecart" | "minecraft:furnace_minecart"
    ) {
        crate::game::create_cart_assembler::tick(game, id);
    }
}
