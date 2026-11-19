use std::collections::{BTreeSet, VecDeque};

use super::create_machines::{DIRECTIONS, offset};

struct Group {
    size: usize,
    parts: Vec<[i32; 3]>,
}

pub(super) fn parts(
    pos: [i32; 3],
    axis_at: impl Fn([i32; 3]) -> Option<char>,
    length_limit: impl Fn(i32) -> i32,
) -> Option<(usize, Vec<[i32; 3]>)> {
    parts_matching(pos, axis_at, length_limit, |_| true)
}

pub(super) fn parts_matching(
    pos: [i32; 3],
    axis_at: impl Fn([i32; 3]) -> Option<char>,
    length_limit: impl Fn(i32) -> i32,
    compatible: impl Fn(&[[i32; 3]]) -> bool,
) -> Option<(usize, Vec<[i32; 3]>)> {
    let axis = axis_at(pos)?;
    let mut remaining = BTreeSet::from([pos]);
    let mut frontier = VecDeque::from([pos]);
    while let Some(part) = frontier.pop_front() {
        for direction in DIRECTIONS {
            let next = offset(part, direction);
            if axis_at(next) == Some(axis) && remaining.insert(next) {
                frontier.push_back(next);
            }
        }
    }

    while !remaining.is_empty() {
        let largest = remaining
            .iter()
            .rev()
            .map(|&origin| largest_at(&remaining, axis, origin, &length_limit, &compatible))
            .max_by_key(|group| (group.parts.len(), group.size))?;
        if largest.parts.contains(&pos) {
            return Some((largest.size, largest.parts));
        }
        for part in largest.parts {
            remaining.remove(&part);
        }
    }
    None
}

fn largest_at(
    blocks: &BTreeSet<[i32; 3]>,
    axis: char,
    origin: [i32; 3],
    length_limit: impl Fn(i32) -> i32,
    compatible: impl Fn(&[[i32; 3]]) -> bool,
) -> Group {
    (1..=3)
        .map(|size| {
            let mut parts = Vec::new();
            for length in 0..length_limit(size) {
                let layer: Vec<_> = (0..size)
                    .flat_map(|a| {
                        (0..size).map(move |b| {
                            let step = match axis {
                                'y' => [a, length, b],
                                'z' => [a, b, length],
                                _ => [length, a, b],
                            };
                            offset(origin, step)
                        })
                    })
                    .collect();
                if layer.iter().any(|at| !blocks.contains(at)) {
                    break;
                }
                let previous_len = parts.len();
                parts.extend(layer);
                if !compatible(&parts) {
                    parts.truncate(previous_len);
                    break;
                }
            }
            Group {
                size: size as usize,
                parts,
            }
        })
        .max_by_key(|group| (group.parts.len(), group.size))
        .expect("multiblock supports at least one width")
}
