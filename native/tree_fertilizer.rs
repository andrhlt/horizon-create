use crate::game::Game;
use crate::items::ItemStack;
use horizon_core::position::BlockPos;

pub(super) fn use_item(game: &mut Game<'_>, pos: [i32; 3], stack: &ItemStack) -> bool {
    if stack.item.as_ref() != "create:tree_fertilizer" {
        return false;
    }
    let block = game.native_block(pos);
    if !game.block_in_tag("minecraft:saplings", &block)
        || (block == "minecraft:mangrove_propagule"
            && game.native_block_property(pos, "hanging").as_deref() == Some("true"))
    {
        return false;
    }
    let at = BlockPos::new(pos[0], pos[1], pos[2]);
    let used = game.with_level(|b, level, ticks| b.use_tree_fertilizer(level, ticks, at));
    let _ = game.process_level_events();
    if used && !game.creative {
        game.consume_held();
    }
    used
}
