//! Core game engine module.

use std::collections::HashMap;
use std::time::Instant;

pub trait Component: Send + Sync {
    fn update(&mut self, dt: f32);
    fn name(&self) -> &'static str;
}

pub trait System: Send + Sync {
    fn run(&mut self, entities: &mut EntityStore, dt: f32);
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct EntityId(u64);

pub struct EntityStore {
    next_id: u64,
    components: HashMap<EntityId, Vec<Box<dyn Component>>>,
}

impl EntityStore {
    pub fn new() -> Self {
        EntityStore {
            next_id: 0,
            components: HashMap::new(),
        }
    }

    pub fn create_entity(&mut self) -> EntityId {
        let id = EntityId(self.next_id);
        self.next_id += 1;
        self.components.insert(id, Vec::new());
        id
    }

    pub fn add_component(&mut self, id: EntityId, component: Box<dyn Component>) {
        if let Some(comps) = self.components.get_mut(&id) {
            comps.push(component);
        }
    }

    pub fn remove_entity(&mut self, id: EntityId) {
        self.components.remove(&id);
    }
}

impl Default for EntityStore {
    fn default() -> Self {
        Self::new()
    }
}

pub struct Engine {
    entities: EntityStore,
    systems: Vec<Box<dyn System>>,
    last_tick: Instant,
}

impl Engine {
    pub fn new() -> Self {
        Engine {
            entities: EntityStore::new(),
            systems: Vec::new(),
            last_tick: Instant::now(),
        }
    }

    pub fn add_system(&mut self, system: Box<dyn System>) {
        self.systems.push(system);
    }

    pub fn tick(&mut self) {
        let now = Instant::now();
        let dt = now.duration_since(self.last_tick).as_secs_f32();
        self.last_tick = now;
        for system in &mut self.systems {
            system.run(&mut self.entities, dt);
        }
    }
}

#[derive(Debug, Clone)]
pub struct Health {
    pub current: f32,
    pub maximum: f32,
}

impl Health {
    pub fn new(maximum: f32) -> Self {
        Health { current: maximum, maximum }
    }

    pub fn apply_damage(&mut self, amount: f32) {
        self.current = (self.current - amount).max(0.0);
    }

    pub fn is_alive(&self) -> bool {
        self.current > 0.0
    }
}

impl Component for Health {
    fn update(&mut self, _dt: f32) {}

    fn name(&self) -> &'static str {
        "Health"
    }
}

macro_rules! assert_alive {
    ($entity:expr) => {
        assert!($entity.is_alive(), "entity should be alive");
    };
}
