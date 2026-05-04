#pragma once

namespace Game {

struct Vec2 {
    float x, y;
    Vec2 operator+(const Vec2& rhs) const;
    Vec2 operator-(const Vec2& rhs) const;
    Vec2& operator+=(const Vec2& rhs);
    float dot(const Vec2& rhs) const;
    float length() const;
    Vec2 normalized() const;
};

struct AABB {
    Vec2 min, max;
};

bool checkCollision(const AABB& a, const AABB& b);
Vec2 resolveOverlap(const AABB& a, const AABB& b);

} // namespace Game
