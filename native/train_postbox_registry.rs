// Dimension-local, saved station/Postbox links. Delivery is handled separately.
use horizon_world::attachments::{AttachmentCodec, AttachmentError, AttachmentType, Attachments};
use horizon_world::nbt::{Compound, Tag};

const PORTS: &str = "Ports";
const REGISTRY: AttachmentType<Compound> = AttachmentType {
    namespace: "create",
    name: "train_postbox_ports",
    default: Compound::new,
    codec: Some(AttachmentCodec {
        encode: |tag| Ok(tag.clone()),
        decode: |tag| Ok(tag.clone()),
    }),
    copy_on_death: false,
    sync: false,
};

fn pos(tag: &Compound, key: &str) -> Option<[i32; 3]> {
    let Tag::IntArray(values) = tag.get(&key.into())? else {
        return None;
    };
    values.as_slice().try_into().ok()
}

fn entries(tag: &Compound) -> Vec<Compound> {
    match tag.get(&PORTS.into()) {
        Some(Tag::List(values)) => values
            .iter()
            .filter_map(|value| match value {
                Tag::Compound(value) => Some(value.clone()),
                _ => None,
            })
            .collect(),
        _ => Vec::new(),
    }
}

fn save(
    attachments: &mut Attachments,
    mut registry: Compound,
    ports: Vec<Compound>,
) -> Result<(), AttachmentError> {
    registry.insert(
        PORTS.into(),
        Tag::List(ports.into_iter().map(Tag::Compound).collect()),
    );
    attachments.set(&REGISTRY, registry)
}

/// Register an absolute Postbox position under its station in this dimension.
/// A changed address has Java's deregister/re-register semantics: a fresh buffer.
pub(super) fn register(
    attachments: &mut Attachments,
    station: [i32; 3],
    port: [i32; 3],
    address: &str,
) -> Result<bool, AttachmentError> {
    let mut registry = attachments.get(&REGISTRY)?;
    let mut ports = entries(&registry);
    let existing = ports.iter().position(|entry| {
        pos(entry, "Station") == Some(station) && pos(entry, "Pos") == Some(port)
    });
    if let Some(index) = existing {
        if matches!(ports[index].get(&"Address".into()), Some(Tag::String(value)) if value.to_string_lossy() == address)
        {
            return Ok(false);
        }
        ports.remove(index);
    }
    ports.push(Compound::from([
        ("Station".into(), Tag::IntArray(station.to_vec())),
        ("Pos".into(), Tag::IntArray(port.to_vec())),
        ("Address".into(), Tag::String(address.into())),
        (
            "OfflineBuffer".into(),
            Tag::Compound(Compound::from([
                ("Size".into(), Tag::Int(18)),
                ("Items".into(), Tag::List(Vec::new())),
            ])),
        ),
        ("Primed".into(), Tag::Byte(0)),
    ]));
    save(attachments, std::mem::take(&mut registry), ports)?;
    Ok(true)
}

/// Forget an explicitly removed Postbox; chunk unload must not call this.
pub(super) fn remove_port(
    attachments: &mut Attachments,
    port: [i32; 3],
) -> Result<bool, AttachmentError> {
    let Some(registry) = attachments.get_existing(&REGISTRY)? else {
        return Ok(false);
    };
    let mut ports = entries(&registry);
    let before = ports.len();
    ports.retain(|entry| pos(entry, "Pos") != Some(port));
    if ports.len() == before {
        return Ok(false);
    }
    save(attachments, registry, ports)?;
    Ok(true)
}

/// A removed station loses its graph edge and the ports attached to that edge.
pub(super) fn remove_station(
    attachments: &mut Attachments,
    station: [i32; 3],
) -> Result<bool, AttachmentError> {
    let Some(registry) = attachments.get_existing(&REGISTRY)? else {
        return Ok(false);
    };
    let mut ports = entries(&registry);
    let before = ports.len();
    ports.retain(|entry| pos(entry, "Station") != Some(station));
    if ports.len() == before {
        return Ok(false);
    }
    save(attachments, registry, ports)?;
    Ok(true)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn registration_survives_save_and_explicit_removal() {
        let station = [9, 112, -6];
        let port = [11, 112, -5];
        let mut level = Attachments::default();
        assert_eq!(register(&mut level, station, port, "Depot"), Ok(true));
        assert_eq!(register(&mut level, station, port, "Depot"), Ok(false));
        let saved = level.to_nbt();
        let mut reloaded = Attachments::from_nbt(saved);
        let registry = reloaded.get_existing(&REGISTRY).unwrap().unwrap();
        let ports = entries(&registry);
        assert_eq!(ports.len(), 1);
        assert_eq!(pos(&ports[0], "Station"), Some(station));
        assert_eq!(pos(&ports[0], "Pos"), Some(port));
        assert_eq!(remove_port(&mut reloaded, port), Ok(true));
        assert_eq!(remove_port(&mut reloaded, port), Ok(false));
        assert_eq!(entries(&reloaded.get(&REGISTRY).unwrap()).len(), 0);
    }
}

/// Registration follows the bound Postbox while both it and the station are loaded.
pub(super) fn tick(
    game: &mut super::Game<'_>,
    port: [i32; 3],
    entity: &mut crate::containers::ModBlockEntity,
) {
    if !game.native_authoritative() || entity.id != super::create_postbox::ENTITY {
        return;
    }
    let Some(Tag::Compound(target)) = entity.nbt.get(&"Target".into()) else {
        return;
    };
    if !matches!(target.get(&"type".into()), Some(Tag::String(kind)) if kind.to_string_lossy() == "create:train_station")
    {
        return;
    }
    let Some(relative) = pos(target, "relative_pos") else {
        return;
    };
    let station = std::array::from_fn(|i| port[i] + relative[i]);
    if !game.world.loaded(station[0], station[2])
        || game.native_block(station) != super::create_station::STATION
    {
        return;
    }
    let Some(station_entity) = super::create_machines::mod_entity(game, station) else {
        return;
    };
    let Some((track, _)) = super::create_station::targeting_position(&station_entity.nbt, station)
    else {
        return;
    };
    if !game.world.loaded(track[0], track[2]) || game.native_block(track) != "create:track" {
        return;
    }
    let address = super::create_machines::string(&entity.nbt, "AddressFilter").unwrap_or_default();
    if let Err(error) = register(&mut game.world.attachments, station, port, &address) {
        log::warn!("Could not register Postbox at {port:?}: {error:?}");
        return;
    }
    match restore_primed(&mut game.world.attachments, station, port) {
        Ok(Some(items)) => {
            entity.items = items;
            game.native_block_entity_sync(port);
        }
        Ok(None) => {}
        Err(error) => log::warn!("Could not restore Postbox buffer at {port:?}: {error:?}"),
    }
}

/// An offline transfer marks its buffer Primed; registration restores it once.
fn restore_primed(
    attachments: &mut Attachments,
    station: [i32; 3],
    port: [i32; 3],
) -> Result<Option<Vec<Option<crate::items::ItemStack>>>, AttachmentError> {
    let Some(registry) = attachments.get_existing(&REGISTRY)? else { return Ok(None) };
    let mut ports = entries(&registry);
    let Some(entry) = ports.iter_mut().find(|entry| pos(entry, "Station") == Some(station) && pos(entry, "Pos") == Some(port)) else { return Ok(None) };
    if !matches!(entry.get(&"Primed".into()), Some(Tag::Byte(value)) if *value != 0) {
        return Ok(None);
    }
    let Some(Tag::Compound(buffer)) = entry.get(&"OfflineBuffer".into()) else { return Err(AttachmentError::Decode) };
    let Some(items @ Tag::List(_)) = buffer.get(&"Items".into()) else { return Err(AttachmentError::Decode) };
    let restored = horizon_client::save::decode_items(Some(items), 18);
    entry.insert("Primed".into(), Tag::Byte(0));
    save(attachments, registry, ports)?;
    Ok(Some(restored))
}

/// A live inventory mutation mirrors Java's PostboxBlockEntity.setChanged.
pub(super) fn inventory_changed(game: &mut super::Game<'_>, port: [i32; 3]) {
    if !game.native_authoritative() {
        return;
    }
    let Some(entity) = super::create_machines::mod_entity(game, port)
        .filter(|entity| entity.id == super::create_postbox::ENTITY)
    else {
        return;
    };
    let Some(Tag::Compound(target)) = entity.nbt.get(&"Target".into()) else { return };
    if !matches!(target.get(&"type".into()), Some(Tag::String(kind)) if kind.to_string_lossy() == "create:train_station") {
        return;
    }
    let Some(relative) = pos(target, "relative_pos") else { return };
    let station = std::array::from_fn(|i| port[i] + relative[i]);
    let mut items = horizon_client::save::encode_items(&entity.items[..entity.items.len().min(18)]);
    if let Tag::List(stacks) = &mut items {
        for stack in stacks {
            if let Tag::Compound(stack) = stack
                && let Some(Tag::Byte(slot)) = stack.get(&"Slot".into()).cloned()
            {
                stack.insert("Slot".into(), Tag::Int(i32::from(slot)));
            }
        }
    }
    let attachments = &mut game.world.attachments;
    let Ok(Some(registry)) = attachments.get_existing(&REGISTRY) else { return };
    let mut ports = entries(&registry);
    let Some(entry) = ports.iter_mut().find(|entry| pos(entry, "Station") == Some(station) && pos(entry, "Pos") == Some(port)) else { return };
    // An offline mutation must be restored before live changes can replace it.
    if matches!(entry.get(&"Primed".into()), Some(Tag::Byte(value)) if *value != 0) {
        return;
    }
    let buffer = Tag::Compound(Compound::from([
        ("Size".into(), Tag::Int(18)),
        ("Items".into(), items),
    ]));
    if entry.get(&"OfflineBuffer".into()) == Some(&buffer) {
        return;
    }
    entry.insert("OfflineBuffer".into(), buffer);
    if let Err(error) = save(attachments, registry, ports) {
        log::warn!("Could not save Postbox buffer at {port:?}: {error:?}");
    }
}

/// Block replacement/removal invalidates the stationary graph edge or port.
pub(super) fn removed(
    level: &mut super::GameLevel<'_>,
    pos: [i32; 3],
    old: horizon_world::registry::BlockStateId,
) {
    if !level.native_authoritative {
        return;
    }
    let name = level.native_state_block(old).unwrap_or_default();
    let result = if super::create_postbox::block(&name) {
        remove_port(&mut level.world.attachments, pos)
    } else if name == super::create_station::STATION {
        remove_station(&mut level.world.attachments, pos)
    } else {
        return;
    };
    if let Err(error) = result {
        log::warn!("Could not remove Postbox registry entry at {pos:?}: {error:?}");
    }
}

/// On arrival, deliver matching mounted packages to registered Postboxes.
pub(super) fn deliver_on_arrival(game: &mut super::Game<'_>, data: &mut Compound, station: [i32; 3]) {
    let Ok(Some(registry)) = game.world.attachments.get_existing(&REGISTRY) else { return };
    let mut ports = entries(&registry);
    let mut live = std::collections::HashMap::new();
    for port in &ports {
        if pos(port, "Station") != Some(station) { continue }
        let Some(at) = pos(port, "Pos") else { continue };
        if game.world.loaded(at[0], at[2])
            && let Some(entity) = super::create_machines::mod_entity(game, at)
                .filter(|entity| entity.id == super::create_postbox::ENTITY)
        {
            let mut slots = entity.items.clone();
            slots.resize(18, None);
            slots.truncate(18);
            live.insert(at, slots);
        }
    }
    let mut changed_live = std::collections::HashSet::new();
    let mut next = data.clone();
    let Some(Tag::List(blocks)) = next.get_mut(&"Blocks".into()) else { return };
    let mut delivered = false;
    // Java imports outgoing mail before exporting packages for this station.
    for port in &mut ports {
        if pos(port, "Station") != Some(station) { continue }
        let Some(at) = pos(port, "Pos") else { continue };
        let Some(Tag::String(filter)) = port.get(&"Address".into()) else { continue };
        let filter = filter.to_string_lossy();
        let Some(Tag::Compound(buffer)) = port.get_mut(&"OfflineBuffer".into()) else { continue };
        let mut slots = live.get(&at).cloned().unwrap_or_else(||
            horizon_client::save::decode_items(buffer.get(&"Items".into()), 18));
        let mut imported = false;
        for slot in &mut slots {
            let Some(package) = slot.as_ref() else { continue };
            if !super::create_chain_conveyor_packages::package(game, package) { continue }
            let address = match game.native_component(package, "create:package_address") {
                Ok(Some(Tag::String(value))) => value.to_string_lossy(),
                _ => String::new(),
            };
            if super::create_package_address::matches(&address, &filter) { continue }
            let mut inserted = false;
            for index in super::create_train_portable_items::cargo_blocks(blocks) {
                let Tag::Compound(block) = &mut blocks[index] else { continue };
                let Some((items, capacity)) = super::create_bearing::cargo_items(block) else { continue };
                let empty = (0..capacity).find(|slot| !items.iter().any(|entry|
                    matches!(entry, Tag::Compound(item) if super::create_machines::int(item, "Slot") == Some(*slot as i32))));
                let Some(empty) = empty else { continue };
                let Tag::List(mut encoded) = horizon_client::save::encode_items(&[Some(package.clone())]) else { continue };
                let Some(Tag::Compound(mut item)) = encoded.pop() else { continue };
                item.insert("Slot".into(), Tag::Byte(empty as i8));
                items.push(Tag::Compound(item));
                inserted = true;
                break;
            }
            if inserted { *slot = None; imported = true; }
        }
        if imported {
            let mut encoded = horizon_client::save::encode_items(&slots);
            if let Tag::List(stacks) = &mut encoded {
                for stack in stacks {
                    if let Tag::Compound(stack) = stack
                        && let Some(Tag::Byte(slot)) = stack.get(&"Slot".into()).cloned()
                    {
                        stack.insert("Slot".into(), Tag::Int(i32::from(slot)));
                    }
                }
            }
            buffer.insert("Items".into(), encoded);
            if live.contains_key(&at) {
                live.insert(at, slots);
                changed_live.insert(at);
            } else {
                port.insert("Primed".into(), Tag::Byte(1));
            }
            delivered = true;
        }
    }
    for index in super::create_train_portable_items::cargo_blocks(blocks) {
        let Tag::Compound(block) = &mut blocks[index] else { continue };
        let Some((items, _)) = super::create_bearing::cargo_items(block) else { continue };
        let mut index = 0;
        while index < items.len() {
            let Tag::Compound(item) = &items[index] else { index += 1; continue };
            let Some(package) = crate::items::ItemStack::from_nbt(item) else { index += 1; continue };
            if !super::create_chain_conveyor_packages::package(game, &package) {
                index += 1;
                continue;
            }
            let address = match game.native_component(&package, "create:package_address") {
                Ok(Some(Tag::String(value))) => value.to_string_lossy(),
                _ => String::new(),
            };
            let mut accepted = false;
            for port in &mut ports {
                if pos(port, "Station") != Some(station) { continue }
                let Some(at) = pos(port, "Pos") else { continue };
                let Some(Tag::String(filter)) = port.get(&"Address".into()) else { continue };
                if !super::create_package_address::matches(&address, &filter.to_string_lossy()) { continue }
                let Some(Tag::Compound(buffer)) = port.get_mut(&"OfflineBuffer".into()) else { continue };
                let mut slots = live.get(&at).cloned().unwrap_or_else(||
                    horizon_client::save::decode_items(buffer.get(&"Items".into()), 18));
                let Some(empty) = slots.iter().position(Option::is_none) else { continue };
                slots[empty] = Some(package.clone());
                let mut encoded = horizon_client::save::encode_items(&slots);
                if let Tag::List(stacks) = &mut encoded {
                    for stack in stacks {
                        if let Tag::Compound(stack) = stack
                            && let Some(Tag::Byte(slot)) = stack.get(&"Slot".into()).cloned()
                        {
                            stack.insert("Slot".into(), Tag::Int(i32::from(slot)));
                        }
                    }
                }
                buffer.insert("Items".into(), encoded);
                if live.contains_key(&at) {
                    live.insert(at, slots);
                    changed_live.insert(at);
                } else {
                    port.insert("Primed".into(), Tag::Byte(1));
                }
                accepted = true;
                break;
            }
            if accepted {
                items.remove(index);
                delivered = true;
            } else {
                index += 1;
            }
        }
    }
    if delivered {
        if let Err(error) = save(&mut game.world.attachments, registry, ports) {
            log::warn!("Could not save offline Postbox delivery at {station:?}: {error:?}");
        } else {
            next.insert("CargoIdleTicks".into(), Tag::Int(0));
            *data = next;
            for at in changed_live {
                if let Some(slots) = live.remove(&at) {
                    game.native_with_mod_block_entity(at, |entity| entity.items = slots);
                    game.native_block_entity_sync(at);
                }
            }
        }
    }
}
