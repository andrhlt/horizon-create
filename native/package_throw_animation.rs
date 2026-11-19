fn package_throw_animation(
    stack: &crate::items::ItemStack,
    animation: &mut horizon_world::consumable::UseAnimation,
) {
    crate::game::create_package_throw::animation(stack, animation);
}
