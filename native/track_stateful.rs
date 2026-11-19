fn track_stateful(block: &str, stateful: &mut bool) {
    *stateful |= block == crate::game::create_track::TRACK;
}
