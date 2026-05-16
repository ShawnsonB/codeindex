/**
 * REST API client for the game backend.
 */

const BASE_URL = 'https://api.example.com/v1';

class ApiError extends Error {
    constructor(status, message) {
        super(message);
        this.status = status;
        this.name = 'ApiError';
    }
}

class ApiClient {
    constructor(baseUrl, token) {
        this.baseUrl = baseUrl;
        this.token = token;
    }

    async get(path) {
        const response = await fetch(`${this.baseUrl}${path}`, {
            headers: { Authorization: `Bearer ${this.token}` },
        });
        if (!response.ok) {
            throw new ApiError(response.status, await response.text());
        }
        return response.json();
    }

    async post(path, body) {
        const response = await fetch(`${this.baseUrl}${path}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${this.token}`,
            },
            body: JSON.stringify(body),
        });
        if (!response.ok) {
            throw new ApiError(response.status, await response.text());
        }
        return response.json();
    }

    static create(token) {
        return new ApiClient(BASE_URL, token);
    }
}

async function fetchUserProfile(client, userId) {
    return client.get(`/users/${userId}`);
}

async function updatePlayerScore(client, playerId, score) {
    return client.post(`/players/${playerId}/score`, { score });
}

const formatScore = (score) => score.toLocaleString('en-US');

const parseLeaderboard = function(data) {
    return data.entries.map((e, i) => ({ rank: i + 1, ...e }));
};

export { ApiClient, ApiError, fetchUserProfile, updatePlayerScore, formatScore };
