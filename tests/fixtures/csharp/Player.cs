using System;
using UnityEngine;

namespace Combat
{
    // Player entity. Implements IDamageable to participate in the damage pipeline.
    // Tracks health, invincibility frames, and fires events for UI and animation.
    public class Player : MonoBehaviour, IDamageable
    {
        [SerializeField] private int maxHealth = 100;
        [SerializeField] private float invincibilityDuration = 0.5f;

        public int CurrentHealth { get; private set; }
        public bool IsDead { get; private set; }

        public event Action<int, int> OnHealthChanged;  // (current, max)
        public event Action OnDeath;

        private float lastDamageTime = float.NegativeInfinity;

        private void Awake()
        {
            CurrentHealth = maxHealth;
        }

        // Primary path for all damage applied to the player. Skips if dead or
        // within the invincibility window. Subtracts health and triggers OnDeath
        // when health reaches zero.
        public void TakeDamage(int amount, string source)
        {
            if (IsDead) return;
            if (Time.time - lastDamageTime < invincibilityDuration) return;

            CurrentHealth = Mathf.Max(CurrentHealth - amount, 0);
            lastDamageTime = Time.time;

            OnHealthChanged?.Invoke(CurrentHealth, maxHealth);

            if (CurrentHealth <= 0)
            {
                IsDead = true;
                OnDeath?.Invoke();
            }
        }

        public void Heal(int amount)
        {
            if (IsDead) return;
            CurrentHealth = Mathf.Min(CurrentHealth + amount, maxHealth);
            OnHealthChanged?.Invoke(CurrentHealth, maxHealth);
        }

        // Resets to full health; used by the respawn system.
        public void Revive()
        {
            IsDead = false;
            CurrentHealth = maxHealth;
            lastDamageTime = float.NegativeInfinity;
            OnHealthChanged?.Invoke(CurrentHealth, maxHealth);
        }
    }
}
