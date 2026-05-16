package com.game.combat;

public enum DamageType {
    PHYSICAL, MAGIC, FIRE, POISON
}

interface Damageable {
    void applyDamage(int amount, DamageType type);
    boolean isAlive();
}

@FunctionalInterface
interface DamageCalculator {
    int calculate(int baseDamage, DamageType type);
}

abstract class BaseEnemy implements Damageable {
    protected String name;
    protected int health;
    protected int damage;

    public BaseEnemy(String name, int health, int damage) {
        this.name = name;
        this.health = health;
        this.damage = damage;
    }

    public abstract void attack(Damageable target);

    @Override
    public boolean isAlive() {
        return health > 0;
    }
}

final class Goblin extends BaseEnemy {
    public Goblin(int health) {
        super("Goblin", health, 5);
    }

    @Override
    public void attack(Damageable target) {
        target.applyDamage(damage, DamageType.PHYSICAL);
    }

    @Override
    public void applyDamage(int amount, DamageType type) {
        this.health = Math.max(0, this.health - amount);
    }

    private static int applyResistance(int amount, float resistance) {
        return (int) (amount * (1.0f - resistance));
    }
}
