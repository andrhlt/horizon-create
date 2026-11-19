fn cardboard_sword_anvil(
    input: Option<&ItemStack>,
    addition: Option<&ItemStack>,
) -> std::ops::ControlFlow<AnvilResult> {
    use std::ops::ControlFlow::{Break, Continue};
    if input.is_some_and(|stack| stack.item.as_ref() == "create:cardboard_sword")
        && addition.is_some_and(|stack| {
            has_stored_enchantments(stack)
                && stack
                    .crafting_enchantments()
                    .iter()
                    .any(|(id, _)| id.as_ref() != "minecraft:knockback")
        })
    {
        Break(AnvilResult::default())
    } else {
        Continue(())
    }
}
