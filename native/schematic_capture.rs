// Schematic and Quill world capture. The caller supplies the selected corners.
use super::*;
use std::path::{Path, PathBuf};

fn bounds(first: [i32; 3], second: [i32; 3]) -> Option<([i32; 3], [i32; 3])> {
    let origin = std::array::from_fn(|i| first[i].min(second[i]));
    let mut size = [0; 3];
    for i in 0..3 {
        size[i] = first[i]
            .max(second[i])
            .checked_sub(origin[i])?
            .checked_add(1)?;
    }
    Some((origin, size))
}

impl Game<'_> {
    /// Capture the inclusive selection as a compressed vanilla structure NBT file.
    /// The caller chooses a filename and handles any existing-file policy.
    pub(in crate::game) fn capture_schematic(
        &mut self,
        first: [i32; 3],
        second: [i32; 3],
        file: &Path,
    ) -> std::io::Result<PathBuf> {
        let (origin, size) = bounds(first, second).ok_or_else(|| {
            std::io::Error::new(std::io::ErrorKind::InvalidInput, "selection is too large")
        })?;
        let registry = self.pack.assets.registry;
        let air = registry
            .default_state("minecraft:air")
            .ok_or_else(|| std::io::Error::other("air state is missing"))?;
        let void = registry.default_state("minecraft:structure_void");
        let mut blocks = Vec::new();
        for y in 0..size[1] {
            for z in 0..size[2] {
                for x in 0..size[0] {
                    let at = (origin[0] + x, origin[1] + y, origin[2] + z);
                    let state = self.world.block(at.0, at.1, at.2);
                    if state == air {
                        continue;
                    }
                    let nbt = match self.block_entity_nbt([at.0, at.1, at.2]) {
                        Some(Tag::Compound(mut data)) => {
                            for key in ["x", "y", "z", "keepPacked"] {
                                data.remove(&key.into());
                            }
                            Some(Box::new(data))
                        }
                        _ => None,
                    };
                    blocks.push(BlockInfo {
                        pos: [x, y, z],
                        state: if Some(state) == void { air } else { state },
                        nbt,
                    });
                }
            }
        }
        let entities = self.template_entities(origin, size);
        let transforms = self
            .state_transforms()
            .ok_or_else(|| std::io::Error::other("structure block table is missing"))?;
        let tag = save_nbt(
            registry,
            transforms,
            size,
            blocks,
            &entities,
            horizon_core::version::DATA_VERSION,
        );
        let raw = nbt::write_named(
            &NamedTag {
                name: "".into(),
                tag,
            },
            Limits::templates(),
        )
        .map_err(|e| std::io::Error::other(format!("{e:?}")))?;
        let compressed = Compression::Gzip
            .encode(&raw)
            .map_err(|e| std::io::Error::other(format!("{e:?}")))?;
        if let Some(parent) = file.parent() {
            std::fs::create_dir_all(parent)?;
        }
        std::fs::write(file, compressed)?;
        Ok(file.to_path_buf())
    }
}

#[cfg(test)]
mod tests {
    use super::bounds;

    #[test]
    fn corners_are_inclusive_and_order_independent() {
        assert_eq!(bounds([7, -2, 4], [5, 1, 4]), Some(([5, -2, 4], [3, 4, 1])));
        assert_eq!(bounds([5, 1, 4], [7, -2, 4]), Some(([5, -2, 4], [3, 4, 1])));
        assert_eq!(bounds([2, 2, 2], [2, 2, 2]), Some(([2, 2, 2], [1, 1, 1])));
        assert_eq!(bounds([i32::MIN, 0, 0], [i32::MAX, 0, 0]), None);
    }
}
