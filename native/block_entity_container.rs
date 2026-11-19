fn block_entity_container(block: &str, container: &mut Option<crate::containers::ModContainer>) {
    crate::game::create_machines::block_entity_container(block, container);
    crate::game::create_factory_gauge::container(block, container);
}
