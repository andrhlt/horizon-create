fn toolbox_link_clear(phase: horizon_client::mod_api::WorldPhase) {
    if matches!(
        phase,
        horizon_client::mod_api::WorldPhase::WorldCloseFinal
            | horizon_client::mod_api::WorldPhase::WorldCloseFailed
    ) {
        crate::game::create_toolbox_links::clear();
    }
}
