package server

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
)

type User struct {
	ID    int64
	Name  string
	Email string
}

type UserRepository interface {
	FindByID(ctx context.Context, id int64) (*User, error)
	Save(ctx context.Context, u *User) error
	Delete(ctx context.Context, id int64) error
}

type SQLUserRepository struct {
	db *sql.DB
}

func NewSQLUserRepository(db *sql.DB) *SQLUserRepository {
	return &SQLUserRepository{db: db}
}

func (r *SQLUserRepository) FindByID(ctx context.Context, id int64) (*User, error) {
	row := r.db.QueryRowContext(ctx, "SELECT id, name, email FROM users WHERE id = ?", id)
	u := &User{}
	if err := row.Scan(&u.ID, &u.Name, &u.Email); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, fmt.Errorf("user %d not found", id)
		}
		return nil, err
	}
	return u, nil
}

func (r *SQLUserRepository) Save(ctx context.Context, u *User) error {
	_, err := r.db.ExecContext(ctx,
		"INSERT INTO users (name, email) VALUES (?, ?) ON DUPLICATE KEY UPDATE name=VALUES(name)",
		u.Name, u.Email,
	)
	return err
}

func (r *SQLUserRepository) Delete(ctx context.Context, id int64) error {
	_, err := r.db.ExecContext(ctx, "DELETE FROM users WHERE id = ?", id)
	return err
}
