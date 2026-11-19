#[path = "../native/frogport_effects_math.rs"]
mod frogport_effects_math;

use horizon_core::random::LegacyRandom;

#[test]
fn seeded_rope_particles_match_java() {
    for scenario in ["catch_near", "catch_remote"] {
        let mut random = LegacyRandom::new(410723);
        let points = frogport_effects_math::rope_particles([13.125, 102.375, -8.75], &mut random);
        let rows: Vec<_> = include_str!("../fixtures/frogport-package-effects-java.csv")
            .lines()
            .filter(|line| line.starts_with(scenario))
            .map(|line| line.split(',').collect::<Vec<_>>())
            .filter(|fields| fields[1] == "particle")
            .collect();
        assert_eq!(points.len(), rows.len());
        for (point, row) in points.into_iter().zip(rows) {
            for (actual, expected) in point.into_iter().zip(&row[3..6]) {
                assert!(
                    (actual - expected.parse::<f64>().unwrap()).abs() < 1e-9,
                    "{row:?}"
                );
            }
        }
    }
}
