fn extendo_grip_reach(
    game: &mut crate::game::Game<'_>,
    attribute: &str,
    range: f64,
) -> f64 {
    use horizon_world::player_inventory::EquipmentSlot;
    if attribute != "minecraft:block_interaction_range" {
        return range;
    }
    let held = [EquipmentSlot::MainHand, EquipmentSlot::OffHand]
        .into_iter()
        .filter(|slot| game.native_equipment(*slot).is_some_and(|stack| stack.item.as_ref() == "create:extendo_grip"))
        .count();
    range + match held {
        1 => 3.0,
        2 => 5.0,
        _ => 0.0,
    }
}
