#include "physics.h"
#include <cmath>
#include <algorithm>

namespace Game {

Vec2 Vec2::operator+(const Vec2& rhs) const { return {x + rhs.x, y + rhs.y}; }
Vec2 Vec2::operator-(const Vec2& rhs) const { return {x - rhs.x, y - rhs.y}; }

Vec2& Vec2::operator+=(const Vec2& rhs) {
    x += rhs.x;
    y += rhs.y;
    return *this;
}

float Vec2::dot(const Vec2& rhs) const {
    return x * rhs.x + y * rhs.y;
}

float Vec2::length() const {
    return std::sqrt(x * x + y * y);
}

Vec2 Vec2::normalized() const {
    float len = length();
    if (len == 0.0f) return {0.0f, 0.0f};
    return {x / len, y / len};
}

bool checkCollision(const AABB& a, const AABB& b) {
    return a.min.x < b.max.x && a.max.x > b.min.x
        && a.min.y < b.max.y && a.max.y > b.min.y;
}

Vec2 resolveOverlap(const AABB& a, const AABB& b) {
    float ox = std::min(a.max.x, b.max.x) - std::max(a.min.x, b.min.x);
    float oy = std::min(a.max.y, b.max.y) - std::max(a.min.y, b.min.y);
    return ox < oy ? Vec2{ox, 0.0f} : Vec2{0.0f, oy};
}

} // namespace Game
