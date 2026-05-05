using System.Collections;
using UnityEngine;

namespace Combat
{
    // Basic enemy that implements IDamageable and attacks the player by calling
    // TakeDamage on the player's IDamageable component.
    public class Enemy : MonoBehaviour, IDamageable
    {
        [SerializeField] private int maxHealth = 50;
        [SerializeField] private int attackDamage = 10;
        [SerializeField] private float attackRange = 1.5f;
        [SerializeField] private float attackCooldown = 1.0f;

        public int CurrentHealth { get; private set; }
        public bool IsDead { get; private set; }

        private float lastAttackTime;
        private Transform playerTransform;
        private IDamageable playerDamageable;

        private void Start()
        {
            CurrentHealth = maxHealth;
            var playerObj = GameObject.FindWithTag("Player");
            if (playerObj != null)
            {
                playerTransform = playerObj.transform;
                playerDamageable = playerObj.GetComponent<IDamageable>();
            }
        }

        private void Update()
        {
            if (IsDead || playerDamageable == null || playerDamageable.IsDead) return;

            float dist = Vector3.Distance(transform.position, playerTransform.position);
            if (dist <= attackRange && Time.time - lastAttackTime >= attackCooldown)
            {
                AttackPlayer();
            }
        }

        // Delivers a melee hit to the player via the IDamageable interface.
        private void AttackPlayer()
        {
            lastAttackTime = Time.time;
            playerDamageable.TakeDamage(attackDamage, "Enemy");
        }

        public void TakeDamage(int amount, string source)
        {
            if (IsDead) return;
            CurrentHealth = Mathf.Max(CurrentHealth - amount, 0);
            if (CurrentHealth <= 0)
            {
                IsDead = true;
                StartCoroutine(DieRoutine());
            }
        }

        public void Heal(int amount) { }

        private IEnumerator DieRoutine()
        {
            yield return new WaitForSeconds(0.3f);
            Destroy(gameObject);
        }
    }
}
