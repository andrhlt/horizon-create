use std::collections::HashMap;

#[path = "../native/chain_conveyor.rs"]
mod conveyor;
use conveyor::{
    Span, advance_loop, chain_cost, crosses_loop_angle, loop_position, reverse_progress,
};

use conveyor as create_chain_conveyor;
#[path = "../native/chain_conveyor_ride_motion.rs"]
mod rider;

#[path = "../native/chain_conveyor_hanging_math.rs"]
mod hanging;

fn offset(value: &str) -> [i32; 3] {
    let values: Vec<_> = value.split(':').map(|n| n.parse().unwrap()).collect();
    values.try_into().unwrap()
}

fn close(actual: f64, wanted: &str, tolerance: f64, row: &str) {
    let expected: f64 = wanted.parse().unwrap();
    assert!(
        (actual - expected).abs() <= tolerance,
        "{row}\nexpected {expected}, got {actual}"
    );
}

const CONNECTION: &str = include_str!("../fixtures/chain-conveyor-connection-java.csv");
const WORLD: &str = include_str!("../fixtures/chain-conveyor-world-java.csv");
const PACKAGE: &str = include_str!("../fixtures/chain-conveyor-package-java.csv");

#[test]
fn chain_cost_and_connection_geometry() {
    for row in CONNECTION.lines().skip(1) {
        let cols: Vec<_> = row.split(',').collect();
        let edge = offset(cols[2]);
        assert_eq!(chain_cost(edge), cols[3].parse().unwrap(), "{row}");
        if cols[1] == "connected" {
            let span = Span::new([0; 3], edge, false);
            close(span.departure.into(), cols[7], 0.00000001, row);
            close(span.length.into(), cols[8], 0.00000001, row);
            for (axis, actual) in span.start.into_iter().chain(span.end).enumerate() {
                close(actual, cols[9 + axis], 0.00000001, row);
            }
        }
    }
}

#[test]
fn package_positions_and_movement() {
    let mut edges = HashMap::new();
    for row in CONNECTION.lines().skip(1) {
        let cols: Vec<_> = row.split(',').collect();
        edges.insert(cols[0], offset(cols[2]));
    }

    let mut wheel_states = HashMap::new();
    for row in WORLD.lines().skip(1) {
        let cols: Vec<_> = row.split(',').collect();
        let tick: u32 = cols[1].parse().unwrap();
        for (wheel, speed, reversed) in [("A", cols[2], cols[6]), ("B", cols[3], cols[7])] {
            wheel_states.insert(
                (cols[0], tick, wheel),
                (speed.parse().unwrap(), reversed == "true"),
            );
        }
    }

    let mut previous = HashMap::new();
    let mut samples = 0;
    let mut movement_steps = 0;
    for row in PACKAGE.lines().skip(1) {
        let c: Vec<_> = row.split(',').collect();
        let (scenario, tick, wheel, path, payload) =
            (c[0], c[1].parse::<u32>().unwrap(), c[2], c[3], c[5]);
        let position: f32 = c[6].parse().unwrap();
        let (_, reversed) = wheel_states[&(scenario, tick, wheel)];
        let origin = if wheel == "A" {
            [0; 3]
        } else {
            edges[scenario]
        };
        let span = (path == "travel").then(|| Span::new(origin, offset(c[4]), reversed));
        let anchor = match &span {
            Some(span) => span.position(position),
            None => loop_position(origin, position),
        };
        for (axis, actual) in anchor.into_iter().enumerate() {
            close(actual, c[7 + axis], 0.00000001, row);
        }
        samples += 1;

        if let Some((last_tick, last_wheel, last_path, last_edge, last_position)) =
            previous.insert((scenario, payload), (tick, wheel, path, c[4], position))
        {
            if tick != last_tick + 1 {
                continue;
            }
            // The world trace samples after the motor's update. Conveyor movement uses
            // the speed present at the beginning of that tick in these fixtures.
            let (rpm, _) = wheel_states[&(scenario, last_tick, wheel)];
            let (_, last_reversed) = wheel_states[&(scenario, last_tick, last_wheel)];
            let expected = match (last_path, &span) {
                ("travel", Some(span)) if wheel == last_wheel => span.advance(last_position, rpm),
                ("travel", Some(span)) if reversed != last_reversed => {
                    span.advance(reverse_progress(offset(last_edge), last_position), rpm)
                }
                ("loop", None) if wheel == last_wheel => advance_loop(last_position, rpm),
                ("travel", None) => {
                    let other_origin = if last_wheel == "A" {
                        [0; 3]
                    } else {
                        edges[scenario]
                    };
                    let span = Span::new(other_origin, offset(last_edge), reversed);
                    assert_eq!(span.advance(last_position, rpm), span.length, "{row}");
                    // The captured fixture ticks wheel A before wheel B.
                    if wheel == "B" {
                        advance_loop(span.arrival, rpm)
                    } else {
                        span.arrival
                    }
                }
                ("loop", Some(span)) => {
                    assert!(
                        crosses_loop_angle(
                            last_position,
                            advance_loop(last_position, rpm),
                            span.departure,
                            reversed,
                        ),
                        "{row}"
                    );
                    0.0
                }
                _ => panic!("unhandled movement: {row}"),
            };
            assert_eq!(expected, position, "{row}");
            movement_steps += 1;
        }
    }
    println!("{samples} package anchors and {movement_steps} consecutive movement steps");
}

#[test]
fn rider_control_matches_java() {
    use rider::{Motion, Rider, Wheel};
    const RIDING: &str = include_str!("../fixtures/chain-conveyor-riding-java.csv");
    let a = [0; 3];
    let c = [0, 0, 7];
    let mut rider = Rider::embark(a, None, 0.0, 0.0);
    let mut reversed = false;
    let mut keepalives = 0;
    let mut stops = 0;
    for line in RIDING.lines().skip(1) {
        let row: Vec<_> = line.split(',').collect();
        let scenario = row[0];
        let tick: u32 = row[1].parse().unwrap();
        let rpm: f32 = row[2].parse().unwrap();
        let b = if scenario.starts_with("rising") {
            [6, 2, 3]
        } else {
            [7, 0, 0]
        };
        if tick == 1 {
            let (edge, position) = match scenario {
                "disconnect" => (Some(b), 1.0),
                "junction" => (None, 315.0),
                _ if scenario.starts_with("rising") => (Some(b), 2.0),
                _ => (None, 40.0),
            };
            rider = Rider::embark(a, edge, position, rpm);
            reversed = false;
            keepalives = 0;
            stops = 0;
        }
        if rpm != 0.0 {
            reversed = rpm < 0.0;
        }
        let a_edges = [b, c];
        let b_edges = [b.map(|axis| -axis)];
        let c_edges = [c.map(|axis| -axis)];
        let links = if scenario == "disconnect" && tick == 5 {
            &a_edges[..0]
        } else if scenario == "junction" {
            &a_edges[..]
        } else {
            &a_edges[..1]
        };
        let v = |n: usize| std::array::from_fn(|axis| row[n + axis].parse::<f64>().unwrap());
        let step = rider.step(
            Motion {
                feet: v(11),
                look: if scenario == "junction" { c } else { b }.map(f64::from),
                velocity: v(14),
                height: 1.8,
                scale: 1.0,
                holding_tool: scenario != "release_tool" || tick != 4,
                sneaking: scenario == "straight" && tick == 32,
            },
            row[3].parse().unwrap(),
            |at| {
                let links = if at == a {
                    links
                } else if at == b {
                    &b_edges
                } else if at == c && scenario == "junction" {
                    &c_edges
                } else {
                    return None;
                };
                Some(Wheel {
                    rpm,
                    reversed,
                    links: links.to_vec(),
                })
            },
        );
        stops += u32::from(step.stopped);
        keepalives += u32::from(!step.stopped && step.target.is_some() && tick % 10 == 0);
        let owner = match rider.wheel {
            None => "-",
            Some(owner) if owner == b => "B",
            Some(owner) if owner == c => "C",
            _ => "A",
        };
        assert_eq!(owner, row[4], "{line}");
        let edge = rider
            .connection
            .map_or("-".to_string(), |[x, y, z]| format!("{x}:{y}:{z}"));
        assert_eq!(edge, row[5], "{line}");
        assert_eq!(rider.position, row[6].parse::<f32>().unwrap(), "{line}");
        assert_eq!(rider.catching_up, row[7].parse::<u8>().unwrap(), "{line}");
        assert_eq!(rider.flipped, row[8].parse::<bool>().unwrap(), "{line}");
        assert_eq!(keepalives, row[9].parse::<u32>().unwrap(), "{line}");
        assert_eq!(stops, row[10].parse::<u32>().unwrap(), "{line}");
        let close = |actual: [f64; 3], expected: [f64; 3]| {
            for (a, e) in actual.into_iter().zip(expected) {
                assert!((a - e).abs() < 1e-8, "{line}\n{actual:?} != {expected:?}");
            }
        };
        if let Some(target) = step.target {
            close(target, v(17));
        } else {
            assert_eq!(&row[17..20], &["-"; 3], "{line}");
        }
        close(step.velocity, v(20));
    }
    println!("149 Java rider steps match in the Rust rider controller");
}

#[test]
fn player_hanging_pose_matches_java() {
    let identity = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0];
    let mut samples = 0;
    for row in include_str!("../fixtures/chain-conveyor-skyhook-java.csv")
        .lines()
        .skip(1)
    {
        let cols: Vec<_> = row.split(',').collect();
        let slim = cols[0] == "true";
        let left = cols[1] == "true";
        let time: f32 = cols[2].parse().unwrap();
        let part: usize = cols[3].parse().unwrap();
        let mut rest = [identity; 6];
        assert_eq!(hanging::PARTS[0], "head");
        rest[2][0] = -5.0;
        rest[3][0] = 5.0;
        rest[2][1] = if slim { 2.5 } else { 2.0 };
        rest[3][1] = rest[2][1];
        rest[4][0] = -1.9;
        rest[5][0] = 1.9;
        rest[4][1] = 12.0;
        rest[5][1] = 12.0;
        let mut head = identity;
        head[3] = 0.24;
        head[4] = -0.38;
        let hanging = hanging::pose(time, left, rest, head);
        // Horizon's hat is a child of the head and inherits its pose.
        let actual = hanging[if part == 6 { 0 } else { part }];
        for (value, expected) in actual.into_iter().zip(&cols[4..]) {
            close(f64::from(value), expected, 0.000002, row);
        }
        samples += 1;
    }
    assert_eq!(samples, 168);
    println!("{samples} Java hanging model-part poses");
}
