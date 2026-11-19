use super::create_chain_conveyor::{Span, crosses_loop_angle};
use horizon_core::geometry::trig::sine_table;

type Block = [i32; 3];

pub(super) struct Wheel {
    pub rpm: f32,
    pub reversed: bool,
    pub links: Vec<Block>,
}

pub(super) struct Rider {
    pub wheel: Option<Block>,
    pub connection: Option<Block>,
    pub position: f32,
    pub flipped: bool,
    pub catching_up: u8,
}

pub(super) struct Motion {
    pub feet: [f64; 3],
    pub look: [f64; 3],
    pub velocity: [f64; 3],
    pub height: f64,
    pub scale: f32,
    pub holding_tool: bool,
    pub sneaking: bool,
}

pub(super) struct Step {
    pub target: Option<[f64; 3]>,
    pub velocity: [f64; 3],
    pub stopped: bool,
}

impl Rider {
    pub fn embark(at: Block, connection: Option<Block>, position: f32, rpm: f32) -> Self {
        Self {
            wheel: Some(at),
            connection,
            position,
            flipped: rpm < 0.0,
            catching_up: 20,
        }
    }

    fn stop(&mut self, mut step: Step) -> Step {
        self.wheel = None;
        self.connection = None;
        step.stopped = true;
        step
    }

    pub fn step(
        &mut self,
        motion: Motion,
        server_speed: f32,
        wheel_at: impl Fn(Block) -> Option<Wheel>,
    ) -> Step {
        let mut step = Step {
            target: None,
            velocity: motion.velocity,
            stopped: false,
        };
        let Some(at) = self.wheel else { return step };
        if !motion.holding_tool || motion.sneaking {
            return self.stop(step);
        }
        let Some(wheel) = wheel_at(at) else {
            return self.stop(step);
        };
        if let Some(edge) = self.connection {
            if !wheel.links.contains(&edge) {
                return self.stop(step);
            }
            let span = Span::new(at, edge, wheel.reversed);
            let destination = offset(at, edge);
            let reversed = wheel.rpm < 0.0;
            if self.flipped != reversed {
                self.flipped = reversed;
                self.wheel = Some(destination);
                self.position = span.length - self.position;
                self.connection = Some(edge.map(|axis| -axis));
            } else {
                self.position =
                    (self.position + server_speed * (wheel.rpm / 360.0).abs()).min(span.length);
                if self.position == span.length && wheel_at(destination).is_some() {
                    self.wheel = Some(destination);
                    self.position = span.arrival;
                    self.connection = None;
                }
            }
        } else {
            let previous = self.position;
            let degrees = (wheel.rpm / 360.0) / (std::f32::consts::PI * 1.5) * 360.0;
            self.position = (self.position + server_speed * degrees).rem_euclid(360.0);
            let direction = normalized(motion.look);
            if let Some(&edge) = wheel.links.iter().rev().min_by(|a, b| {
                // Java keeps the last of equally aligned links.
                let error = |edge: Block| {
                    let edge = normalized(edge.map(f64::from));
                    edge.into_iter()
                        .zip(direction)
                        .map(|(a, b)| (a - b).powi(2))
                        .sum::<f64>()
                };
                error(**a).total_cmp(&error(**b))
            }) {
                let span = Span::new(at, edge, wheel.reversed);
                if crosses_loop_angle(previous, self.position, span.departure, wheel.reversed) {
                    self.position = 0.0;
                    self.connection = Some(edge);
                }
            }
        }
        let owner = self.wheel.unwrap_or(at);
        let Some(wheel) = wheel_at(owner) else {
            return step;
        };
        let target = target_at(owner, self.connection, self.position, wheel.reversed);
        step.target = Some(target);
        let mut head = motion.feet;
        head[1] += motion.height + f64::from(0.5 * motion.scale);
        let delta = std::array::from_fn(|axis| target[axis] - head[axis]);
        self.catching_up = self.catching_up.saturating_sub(1);
        if self.catching_up == 0 && (delta[1] < -1.0 || length(delta) > 3.0) {
            return self.stop(step);
        }
        step.velocity =
            std::array::from_fn(|axis| motion.velocity[axis] * 0.75 + delta[axis] * 0.25);
        step
    }
}

pub(super) fn target_at(
    at: Block,
    connection: Option<Block>,
    position: f32,
    reversed: bool,
) -> [f64; 3] {
    connection.map_or_else(
        || loop_position(at, position),
        |edge| Span::new(at, edge, reversed).position(position),
    )
}

fn offset(at: Block, delta: Block) -> Block {
    std::array::from_fn(|axis| at[axis] + delta[axis])
}

fn length([x, y, z]: [f64; 3]) -> f64 {
    (x * x + y * y + z * z).sqrt()
}

fn normalized(vector: [f64; 3]) -> [f64; 3] {
    let distance = length(vector);
    if distance < 1e-4 {
        [0.0; 3]
    } else {
        vector.map(|axis| axis / distance)
    }
}

fn loop_position(at: Block, angle: f32) -> [f64; 3] {
    let phase = (f64::from(angle) / 180.0 * std::f64::consts::PI) as f32 * 10430.378_f32;
    let table = sine_table();
    [
        f64::from(at[0]) + 0.5 + f64::from(table[(phase as i32 & 65535) as usize]),
        f64::from(at[1]) + 0.25,
        f64::from(at[2]) + 0.5 + f64::from(table[((phase + 16384.0) as i32 & 65535) as usize]),
    ]
}
