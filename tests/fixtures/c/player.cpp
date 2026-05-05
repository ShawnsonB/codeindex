#include "player.h"

namespace Game {

Player::Player(std::string name, int maxHealth)
    : m_name(std::move(name)), m_health(maxHealth),
      m_maxHealth(maxHealth), m_state(PlayerState::Alive) {}

Player::~Player() {}

void Player::applyDamage(int amount) {
    m_health -= amount;
    if (m_health < 0) m_health = 0;
    updateState();
}

void Player::heal(int amount) {
    if (m_state == PlayerState::Dead) return;
    m_health += amount;
    if (m_health > m_maxHealth) m_health = m_maxHealth;
    updateState();
}

bool Player::isAlive() const {
    return m_state != PlayerState::Dead;
}

int Player::getHealth() const {
    return m_health;
}

PlayerState Player::getState() const {
    return m_state;
}

void Player::updateState() {
    if (m_health <= 0)
        m_state = PlayerState::Dead;
    else if (m_state == PlayerState::Dead)
        m_state = PlayerState::Alive;
}

} // namespace Game
