# User model and authentication logic.
require 'bcrypt'
require 'securerandom'

module Auth
  class AuthenticationError < StandardError; end
  class UserNotFoundError < AuthenticationError; end

  module Tokenizable
    def generate_token
      SecureRandom.urlsafe_base64(32)
    end

    def token_expired?(issued_at, ttl_seconds = 3600)
      Time.now - issued_at > ttl_seconds
    end
  end

  class User
    include Tokenizable

    attr_reader :id, :email, :role

    def initialize(id:, email:, password_hash:, role: :user)
      @id            = id
      @email         = email
      @password_hash = password_hash
      @role          = role
    end

    def authenticate(password)
      BCrypt::Password.new(@password_hash) == password
    end

    def admin?
      @role == :admin
    end

    def to_h
      { id: @id, email: @email, role: @role }
    end

    def self.create(email:, password:, role: :user)
      hash = BCrypt::Password.create(password)
      new(id: SecureRandom.uuid, email: email, password_hash: hash, role: role)
    end
  end

  class UserRepository
    def initialize
      @store = {}
    end

    def save(user)
      @store[user.id] = user
      user
    end

    def find_by_id(id)
      @store[id] || raise(UserNotFoundError, "User #{id} not found")
    end

    def find_by_email(email)
      @store.values.find { |u| u.email == email }
    end

    def delete(id)
      @store.delete(id)
    end
  end
end
