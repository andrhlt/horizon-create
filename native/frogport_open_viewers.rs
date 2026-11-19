fn frogport_open_viewers(game: &mut Game<'_>, pos: [i32; 3], viewers: u32) {
    crate::game::create_frogport_open::viewers(game, pos, viewers);
    crate::game::create_postbox::viewers(game, pos, viewers);
    crate::game::create_toolbox_animation::viewers(game, pos, viewers);
}
