pub(crate) mod create_kinetic_slice;
pub(crate) mod gauge_logic;
pub(crate) mod gauge_readout;
pub(crate) mod kinetic_adapter;
pub(crate) mod kinetic_controls;
pub(crate) mod create_millstone_processing;
pub(crate) mod millstone_adapter;
pub(crate) mod press_processing;
pub(crate) mod press_adapter;
pub(crate) mod crushing_adapter;
pub(crate) mod basin_adapter;
pub(crate) mod burner_adapter;
pub(crate) mod turntable_motion;
pub(crate) mod fan_airflow_math;
pub(crate) mod create_fan_nozzle_adapter;
pub(crate) use create_kinetic_slice as kinetic_slice;

#[derive(Default)]
struct Create;

#[mod_api::horizon_mod]
impl mod_api::Hooks for Create {
    fn register(
        &self,
        registrar: &mut dyn mod_api::Registrar,
        _: &mod_api::RegistrationContext,
    ) {
        for recipe_type in [
            "create:compacting",
            "create:cutting",
            "create:crushing",
            "create:deploying",
            "create:emptying",
            "create:filling",
            "create:haunting",
            "create:item_application",
            "create:item_copying",
            "create:mechanical_crafting",
            "create:milling",
            "create:mixing",
            "create:pressing",
            "create:sandpaper_polishing",
            "create:sequenced_assembly",
            "create:splashing",
            "create:toolbox_dyeing",
        ] {
            registrar.register_recipe_type(recipe_type);
            registrar.register_raw_recipe_serializer(recipe_type, recipe_type);
        }
        kinetic_adapter::register(registrar);
        kinetic_controls::register(registrar);
        millstone_adapter::register(registrar);
        press_adapter::register(registrar);
        crushing_adapter::register(registrar);
        basin_adapter::register(registrar);
        burner_adapter::register(registrar);
        gauge_readout::register(registrar);
        create_fan_nozzle_adapter::register(registrar);
        if let Some(container) = millstone_adapter::container("create:millstone") {
            let block = registrar.block_key("create:millstone");
            registrar.block_container(&block, container);
        }
    }

    fn gui_render_post(
        &self,
        host: &dyn mod_api::ClientHost,
        event: &mut mod_api::GuiRenderPostEvent<'_>,
    ) {
        gauge_readout::draw(host, event);
    }

    fn scheduled_task(
        &self,
        host: &mut dyn mod_api::ServerHost,
        event: &mut mod_api::ScheduledTaskEvent<'_>,
    ) {
        press_adapter::scheduled_task(host, event);
    }
}
