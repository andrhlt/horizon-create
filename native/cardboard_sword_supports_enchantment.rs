fn cardboard_sword_supports_enchantment(id: &str, item: &str) -> std::ops::ControlFlow<bool> {
    use std::ops::ControlFlow::{Break, Continue};
    if item == "create:cardboard_sword" {
        Break(id == "minecraft:knockback")
    } else {
        Continue(())
    }
}
