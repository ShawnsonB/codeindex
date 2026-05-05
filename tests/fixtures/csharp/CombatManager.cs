using System.Collections.Generic;
using UnityEngine;

namespace Combat
{
    // Singleton that brokers damage events between attackers and IDamageable targets.
    // Provides a central log of combat activity and enforces team-damage rules.
    public class CombatManager : MonoBehaviour
    {
        public static CombatManager Instance { get; private set; }

        [SerializeField] private bool friendlyFire = false;

        private readonly List<string> combatLog = new List<string>();

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
            DontDestroyOnLoad(gameObject);
        }

        // Routes a damage request from an attacker to a target. Enforces
        // friendly-fire rules and writes to the combat log.
        public void DealDamage(IDamageable target, int amount, string attackerTag, string targetTag)
        {
            if (target == null || target.IsDead) return;
            if (!friendlyFire && attackerTag == targetTag) return;

            target.TakeDamage(amount, attackerTag);
            combatLog.Add($"[{Time.time:F2}] {attackerTag} dealt {amount} dmg to {targetTag}");
        }

        public void HealTarget(IDamageable target, int amount, string sourceTag)
        {
            if (target == null || target.IsDead) return;
            target.Heal(amount);
            combatLog.Add($"[{Time.time:F2}] {sourceTag} healed {amount} hp");
        }

        public IReadOnlyList<string> GetCombatLog()
        {
            return combatLog.AsReadOnly();
        }

        private void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }
    }
}
