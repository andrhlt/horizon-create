fn minecart_coupling_interact(game: &mut crate::game::Game<'_>, entity: i32, kind: &str, stack: Option<&crate::items::ItemStack>, claimed: &mut bool) {
    if !*claimed && matches!(kind, "minecraft:minecart" | "minecraft:chest_minecart" | "minecraft:furnace_minecart" | "minecraft:hopper_minecart" | "minecraft:tnt_minecart") && crate::game::create_minecart_coupling::interact(game, entity as u32, stack) {
        *claimed = true;
    }
}
