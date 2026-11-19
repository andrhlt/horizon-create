fn extendo_grip_server_reach(guest: &mut crate::lan::guest::Guest, pos: [i32; 3], reachable: bool) -> bool {
    if reachable {
        return true;
    }
    let is_grip = |stack: &crate::items::ItemStack| {
        stack.count > 0 && stack.item.as_ref() == "create:extendo_grip"
    };
    let main = guest.inventory.get(guest.selected).and_then(Option::as_ref).is_some_and(is_grip);
    let off = guest.offhand.as_ref().is_some_and(is_grip);
    let extension = match (main, off) {
        (true, true) => 5.0,
        (true, false) | (false, true) => 3.0,
        _ => return false,
    };
    let eye = guest.motion.as_ref().map_or_else(|| guest.eye_height(), |m| f64::from(m.dimensions.eye_height));
    let otherwise = if guest.creative() { 5.0 } else { 4.5 };
    let range = guest.motion.as_mut().and_then(|m| m.attribute("minecraft:block_interaction_range").ok()).unwrap_or(otherwise);
    crate::lan::guest::within_block_range(
        [guest.position[0], guest.position[1] + eye, guest.position[2]], range + extension + 1.0, pos,
    )
}
