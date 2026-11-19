// Compare the production Rust math to measurements of the original Java methods.
#[path = "../native/turntable_player_math.rs"]
mod turntable_player_math;

use horizon_core::geometry::Vec3;
use turntable_player_math::{camera_turn, edge_velocity};

fn fixture(path: &str) -> impl Iterator<Item = Vec<&str>> {
    path.lines().skip(1).map(|line| line.split(',').collect())
}

#[test]
fn original_client_frame_yaw() {
    for row in fixture(include_str!("../fixtures/turntable-player-frame-java.csv")) {
        let number = |index: usize| row[index].parse::<f32>().unwrap();
        let offset = Vec3::new(f64::from(number(3)), 0.0, f64::from(number(4)));
        let turn = if row[7] == "true" {
            camera_turn(number(1), number(2), number(5), number(6), offset)
        } else {
            0.0
        };
        assert_eq!(90.0 - turn, number(8), "view yaw, case {}", row[0]);
        assert_eq!(50.0 - turn, number(9), "body yaw, case {}", row[0]);
    }
}

#[test]
fn original_client_edge_velocity() {
    let origin = Vec3::new(8.5, 171.5, 24.5);
    for row in fixture(include_str!("../fixtures/turntable-player-edge-java.csv")) {
        let input = |index: usize| row[index].parse::<f32>().unwrap();
        let expected = |index: usize| row[index].parse::<f64>().unwrap();
        let offset = Vec3::new(f64::from(input(2)), 0.0, f64::from(input(3)));
        let initial = Vec3::new(0.025, f64::from(input(4)), -0.025);
        let grounded = row[5] == "true";
        let pushed = grounded && input(4) <= 0.0 && offset.x >= 0.5 && input(1) != 0.0;
        assert_eq!(pushed, row[9] == "true", "applies, case {}", row[0]);
        let got = if pushed {
            initial.add_vector(edge_velocity(input(1), origin, origin.add_vector(offset)))
        } else {
            initial
        };
        for (axis, value) in got.components().into_iter().enumerate() {
            let want = expected(axis + 6);
            assert!(
                (value - want).abs() < 1e-12,
                "case {}, axis {axis}: got {value:.12}, Java {want:.12}",
                row[0]
            );
        }
    }
}
