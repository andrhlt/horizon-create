fn shopping_list_tooltip(game: &Game<'_>, stack: &ItemStack, lines: &mut Vec<(Text, u32)>) {
    crate::game::create_shopping_list::tooltip(game, stack, lines);
}
