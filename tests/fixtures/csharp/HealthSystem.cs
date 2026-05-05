using System;

namespace Combat
{
    // Standalone health container for entities that don't inherit MonoBehaviour.
    // Tracks current/max health and fires events on change and on death.
    public class HealthSystem
    {
        public int Current { get; private set; }
        public int Max     { get; private set; }
        public bool IsDead => Current <= 0;

        public event Action<int, int> OnChanged;  // (current, max)
        public event Action OnDied;

        public HealthSystem(int maxHealth)
        {
            if (maxHealth <= 0) throw new ArgumentOutOfRangeException(nameof(maxHealth));
            Max     = maxHealth;
            Current = maxHealth;
        }

        public void ApplyDamage(int amount)
        {
            if (IsDead) return;
            Current = Math.Max(Current - amount, 0);
            OnChanged?.Invoke(Current, Max);
            if (Current == 0) OnDied?.Invoke();
        }

        public void Restore(int amount)
        {
            if (IsDead) return;
            Current = Math.Min(Current + amount, Max);
            OnChanged?.Invoke(Current, Max);
        }

        public void IncreaseMax(int bonus, bool healToNewMax = false)
        {
            Max += bonus;
            if (healToNewMax) Current = Max;
            OnChanged?.Invoke(Current, Max);
        }

        public void Reset()
        {
            Current = Max;
            OnChanged?.Invoke(Current, Max);
        }
    }
}
