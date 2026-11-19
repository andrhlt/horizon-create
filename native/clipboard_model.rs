fn clipboard_model(property: &str, stack: &crate::mod_api::StackView, value: &mut bool) {
    if let Some(selected) = crate::game::create_clipboard::model(property, stack) {
        *value = selected;
    }
}
