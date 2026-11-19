fn funnel_keep_block_entity(old: &str, new: &str) -> std::ops::ControlFlow<bool> {
    use crate::game::{create_belt_funnel as mounted, create_funnel as plain};
    use std::ops::ControlFlow;

    if crate::game::create_toolbox::block(old) && crate::game::create_toolbox::block(new) {
        return ControlFlow::Break(true);
    }
    if matches!(
        (old, new),
        (plain::ANDESITE, mounted::ANDESITE)
            | (mounted::ANDESITE, plain::ANDESITE)
            | (plain::BRASS, mounted::BRASS)
            | (mounted::BRASS, plain::BRASS)
    ) {
        ControlFlow::Break(true)
    } else {
        ControlFlow::Continue(())
    }
}
