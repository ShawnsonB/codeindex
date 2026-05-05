#pragma once
#include <string>

namespace Game {

enum class PlayerState { Alive, Dead, Respawning };

class Player {
public:
    Player(std::string name, int maxHealth);
    ~Player();
    void applyDamage(int amount);
    void heal(int amount);
    bool isAlive() const;
    int getHealth() const;
    PlayerState getState() const;
private:
    std::string m_name;
    int m_health;
    int m_maxHealth;
    PlayerState m_state;
    void updateState();
};

} // namespace Game
