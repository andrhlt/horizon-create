fn stock_link_foil(stack: &ItemStack) -> std::ops::ControlFlow<bool> {
    if matches!(
        stack.item.as_ref(),
        "create:stock_link" | "create:redstone_requester" | "create:stock_ticker" | "create:factory_gauge"
    ) {
        std::ops::ControlFlow::Break(
            stack
                .data()
                .and_then(|data| data.other("minecraft:block_entity_data"))
                .is_some(),
        )
    } else {
        std::ops::ControlFlow::Continue(())
    }
}
