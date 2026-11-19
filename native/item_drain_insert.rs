fn item_drain_insert(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
    stack: &crate::items::ItemStack,
    face: Option<horizon_core::geometry::Direction>,
    result: &mut Option<(Option<crate::items::ItemStack>, bool)>,
) {
    use crate::game::create_item_drain::{DRAIN, accept};
    if game.native_block(pos) != DRAIN {
        return;
    }
    let count = face.map_or(0, |face| accept(game, pos, stack, face.opposite()));
    let remaining = stack.count - count;
    *result = Some(((remaining != 0).then(|| {
        crate::items::ItemStack { count: remaining, ..stack.clone() }
    }), count != 0));
}
