use horizon_world::{nbt::Tag, player_inventory::EquipmentSlot};
use super::{Game, Hand};

pub(super) const GRIP: &str = "create:extendo_grip";
const AIR: &str = "create:banktank_air";

pub(super) fn wear(game: &mut Game<'_>) {
    if game.creative {
        return;
    }
    let held = |slot| game.native_equipment(slot).is_some_and(|stack| stack.item.as_ref() == GRIP);
    let (hand, slot) = if held(EquipmentSlot::MainHand) {
        (Hand::Main, EquipmentSlot::MainHand)
    } else if held(EquipmentSlot::OffHand) {
        (Hand::Off, EquipmentSlot::OffHand)
    } else {
        return;
    };
    if let Some(mut tank) = game.native_equipment(EquipmentSlot::Chest)
        && matches!(tank.item.as_ref(), "create:copper_backtank" | "create:netherite_backtank")
    {
        let air = match game.native_component(&tank, AIR) {
            Ok(Some(Tag::Int(air))) => *air,
            _ => 0,
        };
        if air > 0 {
            let capacity = 900 + 300 * tank.enchantment_level("create:capacity") as i32;
            if game.native_set_component(&mut tank, AIR, Tag::Int((air.min(capacity) - 1).max(0))).is_ok() {
                game.armor[1] = Some(tank);
                return;
            }
        }
    }
    game.with_hand(hand, |game| game.damage_held_in_slot(1, slot));
}
