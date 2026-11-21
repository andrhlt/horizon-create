fn extendo_grip_reach(
    game: &mut crate::game::Game<'_>,
    attribute: &str,
    range: f64,
) -> f64 {
    use horizon_world::player_inventory::EquipmentSlot;
    if !matches!(
        attribute,
        "minecraft:block_interaction_range" | "minecraft:entity_interaction_range"
    ) {
        return range;
    }
    let held = [EquipmentSlot::MainHand, EquipmentSlot::OffHand]
        .into_iter()
        .filter(|slot| game.native_equipment(*slot).is_some_and(|stack| stack.item.as_ref() == "create:extendo_grip"))
        .count();
    let extra = match (attribute, game.creative, held) {
        (_, _, 0) => 0.0,
        ("minecraft:block_interaction_range", _, 1) => 3.0,
        ("minecraft:block_interaction_range", _, 2) => 5.0,
        // Java 1.21.1 uses block reach for entity raycasts. Horizon exposes
        // the entity attribute separately, whose survival base is one block
        // shorter; compensate so the effective ray ends at the same point.
        ("minecraft:entity_interaction_range", false, 1) => 4.0,
        ("minecraft:entity_interaction_range", false, 2) => 6.0,
        ("minecraft:entity_interaction_range", true, 1) => 3.0,
        ("minecraft:entity_interaction_range", true, 2) => 5.0,
        _ => 0.0,
    };
    range + extra
}
