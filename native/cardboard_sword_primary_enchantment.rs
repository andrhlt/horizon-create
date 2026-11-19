fn cardboard_sword_primary_enchantment(e: &Enchantment, item: &str) -> std::ops::ControlFlow<bool> {
    use std::ops::ControlFlow::{Break, Continue};
    if item == "create:cardboard_sword" {
        Break(e.id.as_ref() == "minecraft:knockback")
    } else {
        Continue(())
    }
}
