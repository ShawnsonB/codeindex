package com.game.entity;

import java.util.ArrayList;
import java.util.List;

public class Player implements Damageable {
    private final String name;
    private int maxHealth;
    private int health;
    private int level;
    private int experience;
    private final List<StatusEffect> effects = new ArrayList<>();

    public Player(String name, int maxHealth) {
        this.name = name;
        this.maxHealth = maxHealth;
        this.health = maxHealth;
        this.level = 1;
        this.experience = 0;
    }

    @Override
    public void applyDamage(int amount, DamageType type) {
        int mitigated = Math.max(0, amount - getArmor());
        this.health = Math.max(0, this.health - mitigated);
    }

    public void heal(int amount) {
        this.health = Math.min(maxHealth, this.health + amount);
    }

    @Override
    public boolean isAlive() {
        return this.health > 0;
    }

    public void gainExperience(int xp) {
        this.experience += xp;
        while (this.experience >= xpThreshold()) {
            this.experience -= xpThreshold();
            this.level++;
        }
    }

    private int xpThreshold() {
        return this.level * 100;
    }

    protected int getArmor() {
        return 0;
    }

    public String getName()   { return name; }
    public int    getHealth() { return health; }
    public int    getLevel()  { return level; }
}
