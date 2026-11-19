use std::collections::HashSet;

use horizon_client::hud::{HudBatch, rgba};
use horizon_world::nbt::Tag;

use super::Game;
use super::create_machines::mod_entity;
use super::create_station::{target, valid_track};
use super::create_train_schedule_runtime::matching_name;
use super::create_train_track::station_networks;

const VISIBLE: usize = 7;

struct Station {
    name: String,
    network: i32,
    distance: i32,
}

#[derive(Default)]
pub(super) struct Catalog(Vec<Station>);

impl Catalog {
    pub(super) fn capture(game: &Game<'_>, player: [f64; 3]) -> Self {
        let mut positions: Vec<_> = game
            .world
            .block_entities
            .keys()
            .filter_map(|&(x, y, z)| {
                let pos = [x, y, z];
                let (track, _) = target(game, pos)?;
                let axis = valid_track(game, track)?;
                let name = match mod_entity(game, pos)?.nbt.get(&"Name".into()) {
                    Some(Tag::String(name)) => name.to_string().ok()?,
                    _ => "Track Station".to_owned(),
                };
                Some((pos, track, axis, name))
            })
            .collect();
        positions.sort_by_key(|(pos, _, _, _)| *pos);
        let tracks: Vec<_> = positions
            .iter()
            .map(|(_, track, axis, _)| (*track, *axis))
            .collect();
        let networks = station_networks(game, &tracks);
        Self(
            positions
                .into_iter()
                .zip(networks)
                .map(|(([x, y, z], _, _, name), network)| {
                    let distance = [f64::from(x) + 0.5, f64::from(y), f64::from(z) + 0.5]
                        .into_iter()
                        .zip(player)
                        .map(|(position, player)| (position - player).powi(2))
                        .sum::<f64>()
                        .sqrt() as i32;
                    Station {
                        name,
                        network,
                        distance,
                    }
                })
                .collect(),
        )
    }

    pub(super) fn tag(&self) -> Tag {
        Tag::List(
            self.0
                .iter()
                .map(|station| {
                    Tag::compound([
                        ("Name", Tag::String(station.name.as_str().into())),
                        ("Network", Tag::Int(station.network)),
                        ("Distance", Tag::Int(station.distance)),
                    ])
                })
                .collect(),
        )
    }

    pub(super) fn read(tag: &Tag) -> Self {
        let Tag::List(stations) = tag else {
            return Self::default();
        };
        Self(
            stations
                .iter()
                .filter_map(|station| {
                    let (Tag::String(name), Tag::Int(network), Tag::Int(distance)) = (
                        station.get("Name")?,
                        station.get("Network")?,
                        station.get("Distance")?,
                    ) else {
                        return None;
                    };
                    Some(Station {
                        name: name.to_string().ok()?,
                        network: *network,
                        distance: *distance,
                    })
                })
                .collect(),
        )
    }

    pub(super) fn suggestions<'a>(
        &'a self,
        filters: impl Iterator<Item = &'a str>,
        prefix: &str,
    ) -> Vec<&'a str> {
        let mut viable: HashSet<_> = self.0.iter().map(|station| station.network).collect();
        for filter in filters.filter(|filter| !filter.trim().is_empty()) {
            let matching: HashSet<_> = self
                .0
                .iter()
                .filter(|station| matching_name(filter, &station.name))
                .map(|station| station.network)
                .collect();
            viable.retain(|network| matching.contains(network));
        }

        let folded = prefix.to_lowercase();
        let mut seen = HashSet::new();
        let mut matches: Vec<_> = self
            .0
            .iter()
            .filter(|station| {
                (viable.is_empty() || viable.contains(&station.network))
                    && station.name != prefix
                    && station.name.to_lowercase().starts_with(&folded)
                    && seen.insert(station.name.as_str())
            })
            .collect();
        matches.sort_by_key(|station| station.distance);
        matches
            .into_iter()
            .map(|station| station.name.as_str())
            .collect()
    }
}

pub(super) struct Dropdown<'a> {
    options: &'a [&'a str],
    start: usize,
    left: f32,
    top: f32,
    width: f32,
    selected: usize,
}

impl<'a> Dropdown<'a> {
    pub(super) fn new(
        game: &Game<'_>,
        options: &'a [&'a str],
        selected: usize,
        origin: [f32; 2],
    ) -> Self {
        let width = options
            .iter()
            .map(|option| game.native_text_width(option))
            .fold(0.0, f32::max);
        let [left, top] = origin;
        let selected = selected.min(options.len().saturating_sub(1));
        let start = (selected + 1).saturating_sub(VISIBLE);
        let left = (left + 82.0).min(left + 198.0 - width).max(0.0);
        Self {
            options,
            start,
            left,
            top: top + 105.0,
            width,
            selected,
        }
    }

    pub(super) fn hit(&self, [x, y]: [f32; 2]) -> Option<&'a str> {
        if x < self.left - 1.0 || x >= self.left + self.width + 1.0 || y < self.top {
            return None;
        }
        let row = ((y - self.top) / 12.0) as usize;
        if row >= VISIBLE {
            return None;
        }
        self.options.get(self.start + row).copied()
    }

    pub(super) fn draw(&self, game: &Game<'_>, batch: &mut HudBatch) {
        for (row, name) in self
            .options
            .iter()
            .skip(self.start)
            .take(VISIBLE)
            .enumerate()
        {
            let y = self.top + row as f32 * 12.0;
            let at = [self.left - 1.0, y, self.width + 2.0, 12.0];
            batch.fill(
                &game.gui.atlas,
                at[0],
                at[1],
                at[2],
                at[3],
                rgba(48, 48, 48, 238),
            );
            game.native_text(
                batch,
                name,
                [self.left, y + 2.0],
                if self.start + row == self.selected {
                    0xFFFF55
                } else {
                    0xAAAAAA
                },
                true,
            );
            horizon_client::widgets::record(name, at, true);
        }
    }
}
