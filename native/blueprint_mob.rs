pub fn size(mob: &crate::mobs::Mob) -> std::ops::ControlFlow<(f64, f64, f64)> {
    if mob.kind.id.as_str() != "create:blueprint" {
        return std::ops::ControlFlow::Continue(());
    }
    let side = f64::from((mob.health.round() as i32).clamp(1, 3)) / 2.0;
    std::ops::ControlFlow::Break((side, side, side * 0.85))
}
