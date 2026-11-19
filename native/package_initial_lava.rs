fn package_initial_lava(mob: &Mob) -> std::ops::ControlFlow<bool> {
    use std::ops::ControlFlow::{Break, Continue};

    if mob.kind.id == crate::mobs::create_package_style::ENTITY {
        Break(true)
    } else {
        Continue(())
    }
}
