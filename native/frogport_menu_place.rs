fn frogport_menu_place(
    menu: &Menu,
    env: &Env<'_>,
    slot: usize,
    stack: &ItemStack,
) -> std::ops::ControlFlow<bool> {
    if matches!(menu.kind, Kind::Mod(kind) if kind.id == "create:package_frogport" && slot < kind.slots)
        && !env
            .items
            .item_tags
            .get("create:packages")
            .is_some_and(|packages| packages.contains(stack.item.as_ref()))
    {
        return std::ops::ControlFlow::Break(false);
    }
    std::ops::ControlFlow::Continue(())
}
