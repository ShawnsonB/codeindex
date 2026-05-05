<?php

namespace App\Auth;

use App\Model\User;

interface AuthProviderInterface
{
    public function authenticate(string $token): ?User;
    public function revoke(string $token): void;
}

trait HasRoles
{
    private array $roles = [];

    public function assignRole(string $role): void
    {
        if (!in_array($role, $this->roles, true)) {
            $this->roles[] = $role;
        }
    }

    public function hasRole(string $role): bool
    {
        return in_array($role, $this->roles, true);
    }
}

abstract class BaseAuthenticator implements AuthProviderInterface
{
    protected function hashToken(string $token): string
    {
        return hash('sha256', $token);
    }

    abstract protected function validateSignature(string $token): bool;
}

final class JwtAuthenticator extends BaseAuthenticator
{
    use HasRoles;

    private string $secret;

    public function __construct(string $secret)
    {
        $this->secret = $secret;
    }

    public function authenticate(string $token): ?User
    {
        if (!$this->validateSignature($token)) {
            return null;
        }
        $payload = $this->decodePayload($token);
        return User::fromPayload($payload);
    }

    public function revoke(string $token): void
    {
        // In a real implementation, store the token in a blocklist
        $hash = $this->hashToken($token);
        $this->storeRevoked($hash);
    }

    protected function validateSignature(string $token): bool
    {
        [$header, $payload, $sig] = explode('.', $token, 3);
        $expected = hash_hmac('sha256', "$header.$payload", $this->secret);
        return hash_equals($expected, $sig);
    }

    private function decodePayload(string $token): array
    {
        [, $payload] = explode('.', $token, 3);
        return json_decode(base64_decode($payload), true);
    }

    private function storeRevoked(string $hash): void
    {
        // closure stored as variable — should NOT be a split point
        $persist = function (string $h) {
            file_put_contents('/tmp/revoked.txt', $h . PHP_EOL, FILE_APPEND);
        };
        $persist($hash);
    }
}
