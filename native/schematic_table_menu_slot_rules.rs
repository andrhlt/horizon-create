fn schematic_table_menu_slot_rules(
    menu: &str,
    slot: usize,
    stack: &crate::items::ItemStack,
    may_place: &mut bool,
) {
    if menu != "create:schematic_table" {
        return;
    }
    *may_place &= slot == 0
        && matches!(
            stack.item.as_ref(),
            "create:empty_schematic" | "create:schematic_and_quill" | "create:schematic"
        );
}
