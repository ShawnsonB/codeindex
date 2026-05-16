"""Combat system for a 2-D action game."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Protocol


class DamageType(Enum):
    PHYSICAL = auto()
    MAGIC = auto()
    FIRE = auto()
    POISON = auto()


@dataclass
class StatusEffect:
    name: str
    duration: int
    damage_per_tick: float = 0.0

    def is_expired(self) -> bool:
        return self.duration <= 0

    def tick(self) -> float:
        self.duration -= 1
        return self.damage_per_tick


class Damageable(Protocol):
    def apply_damage(self, amount: float, damage_type: DamageType) -> None: ...
    def is_alive(self) -> bool: ...


@dataclass
class CombatEntity:
    name: str
    max_health: float
    armor: float = 0.0
    _health: float = field(init=False)
    _effects: list[StatusEffect] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self._health = self.max_health

    def is_alive(self) -> bool:
        return self._health > 0.0

    def apply_damage(self, amount: float, damage_type: DamageType) -> None:
        mitigated = amount * max(0.0, 1.0 - self.armor / 100.0)
        self._health = max(0.0, self._health - mitigated)

    def heal(self, amount: float) -> None:
        self._health = min(self.max_health, self._health + amount)

    def add_effect(self, effect: StatusEffect) -> None:
        self._effects.append(effect)

    def process_effects(self) -> float:
        total = sum(e.tick() for e in self._effects)
        self._effects = [e for e in self._effects if not e.is_expired()]
        return total


class Player(CombatEntity):
    def __init__(self, name: str, max_health: float, level: int = 1) -> None:
        super().__init__(name, max_health)
        self.level = level
        self.experience = 0

    def gain_experience(self, xp: int) -> None:
        self.experience += xp
        while self.experience >= self._xp_threshold():
            self.experience -= self._xp_threshold()
            self.level += 1

    def _xp_threshold(self) -> int:
        return self.level * 100


class Enemy(CombatEntity):
    def __init__(self, name: str, max_health: float, damage: float) -> None:
        super().__init__(name, max_health)
        self.damage = damage

    def attack(self, target: Damageable) -> None:
        target.apply_damage(self.damage, DamageType.PHYSICAL)


def calculate_damage_multiplier(
    damage_type: DamageType,
    resistance: dict[DamageType, float],
) -> float:
    """Return the effective damage multiplier after applying resistances."""
    return max(0.0, 1.0 - resistance.get(damage_type, 0.0))


async def resolve_combat_round(
    attacker: CombatEntity,
    defender: CombatEntity,
) -> dict:
    """Resolve a single round of combat and return a summary."""
    base_damage = 10.0
    multiplier = calculate_damage_multiplier(DamageType.PHYSICAL, {})
    total = base_damage * multiplier
    defender.apply_damage(total, DamageType.PHYSICAL)
    return {
        "attacker": attacker.name,
        "defender": defender.name,
        "damage": total,
        "defender_alive": defender.is_alive(),
    }
