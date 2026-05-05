<?php

namespace App\Model;

enum Status: string
{
    case Active   = 'active';
    case Inactive = 'inactive';
    case Banned   = 'banned';

    public function label(): string
    {
        return match($this) {
            Status::Active   => 'Active',
            Status::Inactive => 'Inactive',
            Status::Banned   => 'Banned',
        };
    }

    public function isAccessAllowed(): bool
    {
        return $this === Status::Active;
    }
}
