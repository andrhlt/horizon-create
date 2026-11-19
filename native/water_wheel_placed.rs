fn water_wheel_placed(game: &mut crate::game::Game<'_>, pos: [i32; 3]) {
    use crate::game::create_machines::{LARGE_WHEEL, WHEEL};
    use crate::game::create_portable_interface;
    let block = game.native_block(pos);
    if create_portable_interface::is_port(&block) {
        create_portable_interface::remember_placer(game, pos);
        return;
    }
    if !matches!(
        block.as_str(),
        WHEEL | LARGE_WHEEL | crate::game::create_press::PRESS,
    ) {
        return;
    }
    let player = game.native_acting_id();
    let owner = horizon_client::lan::playerdata::uuid_ints(player);
    game.native_with_mod_block_entity(pos, |wheel| {
        wheel.nbt.insert(
            "Owner".into(),
            horizon_world::nbt::Tag::IntArray(owner.to_vec()),
        );
    });
}
