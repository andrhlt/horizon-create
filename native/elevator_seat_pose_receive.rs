fn elevator_seat_pose_receive(channel: &str, data: &[u8]) {
    crate::game::create_elevator_seats::receive_rider_pose(channel, data);
}
