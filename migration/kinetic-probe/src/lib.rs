pub(crate) mod gauge_logic;
pub(crate) mod gauge_readout;
pub(crate) mod kinetic_adapter;
pub(crate) mod kinetic_slice;
pub(crate) mod millstone_adapter;
pub(crate) mod millstone_processing;
pub(crate) mod motor_board;
pub(crate) mod moving_probe;
pub(crate) mod turntable_motion;

#[derive(Default)]
struct Mod;

#[mod_api::horizon_mod]
impl mod_api::Hooks for Mod {
    fn register(&self, registrar: &mut dyn mod_api::Registrar, _: &mod_api::RegistrationContext) {
        registrar.register_recipe_type("create:milling");
        registrar.register_raw_recipe_serializer("create:milling", "create:milling");
        kinetic_adapter::register(registrar);
        gauge_readout::register(registrar);
        motor_board::register(registrar);
        millstone_adapter::register(registrar);
        if let Some(container) = millstone_adapter::container("create:millstone") {
            let block = registrar.block_key("create:millstone");
            registrar.block_container(&block, container);
        }
        moving_probe::register(registrar);
    }

    fn scheduled_task(
        &self,
        host: &mut dyn mod_api::ServerHost,
        event: &mut mod_api::ScheduledTaskEvent<'_>,
    ) {
        motor_board::scheduled_task(host, event);
    }

    fn gui_render_post(
        &self,
        host: &dyn mod_api::ClientHost,
        event: &mut mod_api::GuiRenderPostEvent<'_>,
    ) {
        gauge_readout::draw(host, event);
    }
}
