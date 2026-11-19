fn sandpaper_animation(
    stack: &crate::items::ItemStack,
    animation: &mut horizon_world::consumable::UseAnimation,
) {
    crate::game::create_sandpaper::animation(stack, animation);
}
