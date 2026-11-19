fn ejector_container_insert(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
    stack: &crate::items::ItemStack,
    result: &mut Option<(Option<crate::items::ItemStack>, bool)>,
) {
    use crate::game::create_ejector::{EJECTOR, insert};
    if result.is_some() || game.native_block(pos) != EJECTOR {
        return;
    }
    let inserted = insert(game, pos, stack);
    let remaining = stack.count - inserted;
    *result = Some((
        (remaining > 0).then(|| crate::items::ItemStack {
            count: remaining,
            ..stack.clone()
        }),
        inserted > 0,
    ));
}
