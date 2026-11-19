use horizon_core::random::RandomSource;

pub(super) fn rope_particles(anchor: [f64; 3], random: &mut impl RandomSource) -> [[f64; 3]; 5] {
    std::array::from_fn(|_| {
        let [x, y, z] = anchor;
        [x, y - f64::from(random.next_float() * 0.25), z]
    })
}
