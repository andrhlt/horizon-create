fn ponder_tooltip(game: &Game<'_>, stack: &ItemStack, lines: &mut Vec<(Text, u32)>) {
    crate::game::create_ponder::tooltip(game, stack, lines);
}
