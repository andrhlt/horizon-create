fn portable_item_changed(game: &mut Game<'_>, view: &View) {
    let [(key, _), (station, 0)] = view.parts.as_slice() else {
        return;
    };
    if crate::game::create_train_portable_items::changed(game, *key, *station) {
        return;
    }
    crate::game::create_portable_interface::renew(game, [station.0, station.1, station.2]);
}
