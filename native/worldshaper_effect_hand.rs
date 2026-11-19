fn worldshaper_effect_hand(hand: horizon_client::first_person::Hand, stack: Option<&crate::items::ItemStack>, partial: f32, z: &mut f32) {
    crate::game::create_worldshaper_effect::hand_pose(hand, stack, partial, z);
}
