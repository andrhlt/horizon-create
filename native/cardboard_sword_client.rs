fn cardboard_sword_client(game: &mut crate::game::Game<'_>, target: u32, player: bool) {
    crate::game::create_cardboard_sword::client_attack(game, target, player);
}
