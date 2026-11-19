fn package_mob_size(mob: &crate::mobs::Mob) -> std::ops::ControlFlow<(f64, f64, f64)> {
    use crate::mobs::create_package_style::{ENTITY, dimensions};
    if mob.kind.id != ENTITY {
        return std::ops::ControlFlow::Continue(());
    }
    let (width, height) = mob
        .extra
        .main_hand_stack()
        .and_then(|stack| dimensions(&stack.item))
        .unwrap_or((0.75, 0.75));
    std::ops::ControlFlow::Break((width, height, f64::from(height as f32 * 0.85_f32)))
}
