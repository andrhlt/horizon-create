//! Run with rustc --test tools/test-elevator-contact-motion.rs.

mod solver {
    include!("../native/elevator_contact_motion.rs");

    #[cfg(test)]
    mod tests {
        use super::{FOOT_CLEARANCE, ray_corrected_feet, resolve};
        use std::collections::HashMap;

        const JAVA_TRACE: &str = include_str!("../fixtures/elevator-standing-java.csv");

        fn near(actual: f64, expected: f64, role: &str, tick: &str) {
            assert!(
                (actual - expected).abs() < 2e-12,
                "{role} tick {tick}: actual {actual:.17}, Java {expected:.17}"
            );
        }

        #[test]
        fn replays_grounded_java_collision() {
            let mut previous = HashMap::new();
            let mut observations = 0;
            for line in JAVA_TRACE.lines().skip(1) {
                let columns: Vec<_> = line.split(',').collect();
                let [
                    role,
                    tick,
                    cabin,
                    collision_previous,
                    input_feet,
                    input_velocity,
                    output_feet,
                    output_velocity,
                    hard,
                ] = columns[..]
                else {
                    panic!("Unexpected Java trace row {line}");
                };
                let [
                    cabin,
                    collision_previous,
                    input_feet,
                    input_velocity,
                    output_feet,
                    output_velocity,
                ] = [
                    cabin,
                    collision_previous,
                    input_feet,
                    input_velocity,
                    output_feet,
                    output_velocity,
                ]
                .map(|field| field.parse::<f64>().unwrap());
                let Some(&(previous_cabin, feet, velocity)) = previous.get(role) else {
                    previous.insert(role, (cabin, output_feet, output_velocity));
                    continue;
                };
                // Vanilla cuts sub-threshold motion before travel and applies
                // gravity and drag after moving.
                let movement: f64 = if velocity.abs() >= 0.003 {
                    velocity
                } else {
                    0.0
                };
                let travel_feet = feet + movement;
                let travel_velocity = (movement - 0.08) * f64::from(0.98_f32);
                let previous_offset = Some(feet - (previous_cabin + 1.0));
                let deck = cabin + 1.0;
                let motion = cabin - collision_previous;
                let ray_feet =
                    ray_corrected_feet(travel_feet, travel_velocity, deck, motion, previous_offset);
                near(ray_feet, input_feet, role, tick);
                near(travel_velocity, input_velocity, role, tick);
                assert_eq!(ray_feet - deck <= super::BOUNDS_INFLATION, hard == "true");
                let contact = resolve(travel_feet, travel_velocity, deck, motion, previous_offset)
                    .unwrap_or_else(|| panic!("{role} tick {tick} lost deck contact"));
                near(contact.feet_y, output_feet, role, tick);
                near(contact.velocity_y, output_velocity, role, tick);
                previous.insert(role, (cabin, contact.feet_y, contact.velocity_y));
                observations += 1;
            }
            assert_eq!(previous.len(), 2);
            assert_eq!(observations, 390);
        }

        #[test]
        fn player_leaving_the_deck_keeps_their_jump() {
            assert!(resolve(2.3, 0.42, 2.0, 0.25, Some(FOOT_CLEARANCE)).is_none());
        }
    }
}
