fn cardboard_sword_player_attack(
    game: &mut crate::game::Game<'_>,
    host: &mut crate::game::lan::LanHost,
    conn: u32,
    victim: crate::game::lan_pvp::Victim,
    handled: &mut bool,
) {
    *handled = crate::game::create_cardboard_sword::attack_player(game, host, conn, victim);
}
