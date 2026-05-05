using System;

namespace Combat
{
    public interface IDamageable
    {
        int CurrentHealth { get; }
        bool IsDead { get; }

        // Single entry point for all damage. Implementors handle invincibility,
        // blocking, health subtraction, and death internally.
        void TakeDamage(int amount, string source);

        void Heal(int amount);
    }
}
