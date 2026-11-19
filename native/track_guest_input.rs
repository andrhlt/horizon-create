fn track_guest_input(
    game: &mut crate::game::Game<'_>,
    host: &crate::game::lan::LanHost,
    conn: u32,
) {
    if game.lan_acting == Some(conn) {
        return;
    }
    if let Some(guest) = host.hub.guest(conn) {
        crate::game::create_track::guest_input(game, guest.uuid, guest.input);
    }
}
