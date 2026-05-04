<?php

namespace App\Repository;

use App\Model\User;
use App\Database\Connection;

class UserRepository
{
    private Connection $db;

    public function __construct(Connection $db)
    {
        $this->db = $db;
    }

    public function findById(int $id): ?User
    {
        $row = $this->db->query("SELECT * FROM users WHERE id = ?", [$id])->fetch();
        return $row ? User::fromRow($row) : null;
    }

    public function findByEmail(string $email): ?User
    {
        $row = $this->db->query("SELECT * FROM users WHERE email = ?", [$email])->fetch();
        return $row ? User::fromRow($row) : null;
    }

    public function save(User $user): void
    {
        if ($user->id === null) {
            $this->db->execute(
                "INSERT INTO users (name, email, created_at) VALUES (?, ?, ?)",
                [$user->name, $user->email, $user->createdAt->format('Y-m-d H:i:s')]
            );
        } else {
            $this->db->execute(
                "UPDATE users SET name = ?, email = ? WHERE id = ?",
                [$user->name, $user->email, $user->id]
            );
        }
    }

    public function delete(int $id): void
    {
        $this->db->execute("DELETE FROM users WHERE id = ?", [$id]);
    }

    public function findAll(): array
    {
        $rows = $this->db->query("SELECT * FROM users ORDER BY id")->fetchAll();
        return array_map(fn($row) => User::fromRow($row), $rows);
    }

    private function hydrate(array $rows): array
    {
        // inline arrow fn — should NOT be a split point
        return array_map(fn($r) => User::fromRow($r), $rows);
    }
}
