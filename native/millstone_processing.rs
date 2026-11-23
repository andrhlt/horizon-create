//! Pure Millstone processing state shared by legacy and typed-Part adapters.
//!
//! This module deliberately has no Horizon host access. The caller supplies
//! the saved timer, connected speed, recipe duration and input availability;
//! inventory, recipe conversion, chance rolls and sync stay at the adapter
//! boundary.

pub const DEFAULT_PROCESSING_TIME: i32 = 100;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Tick {
    Idle,
    Started { timer: i32 },
    Progressed { timer: i32, finished: bool },
}

pub fn tick(timer: i32, rpm: f32, recipe_time: Option<i32>, has_input: bool) -> Tick {
    if rpm == 0.0 {
        return Tick::Idle;
    }
    if timer <= 0 {
        return recipe_time
            .filter(|_| has_input)
            .map_or(Tick::Idle, |time| Tick::Started { timer: time });
    }
    let step = ((rpm / 16.0).abs() as i32).clamp(1, 512);
    let next = timer - step;
    Tick::Progressed {
        timer: next,
        finished: next <= 0,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn speed_controls_progress_without_skipping_a_started_cycle() {
        assert_eq!(tick(0, 0.0, Some(100), true), Tick::Idle);
        assert_eq!(tick(0, 16.0, Some(100), true), Tick::Started { timer: 100 });
        assert_eq!(
            tick(100, 16.0, Some(100), true),
            Tick::Progressed {
                timer: 99,
                finished: false
            }
        );
        assert_eq!(
            tick(3, 64.0, Some(100), true),
            Tick::Progressed {
                timer: -1,
                finished: true
            }
        );
    }

    #[test]
    fn invalid_or_empty_inputs_do_not_start_or_consume() {
        assert_eq!(tick(0, 16.0, None, true), Tick::Idle);
        assert_eq!(tick(0, 16.0, Some(100), false), Tick::Idle);
        assert_eq!(
            tick(100, -256.0, Some(100), true),
            Tick::Progressed {
                timer: 84,
                finished: false
            }
        );
    }
}
