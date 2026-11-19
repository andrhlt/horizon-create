fn package_filter_component(types: &mut Vec<String>) {
    crate::game::create_linked_controller::register(types);
    crate::game::create_worldshaper::register(types);
    crate::game::create_package_filter_editor::register(types);
    crate::game::create_list_filter_editor::register(types);
    crate::game::create_package_open::register(types);
}
