/**
 * Domain models for the game leaderboard service.
 */

export enum Rank {
    Bronze = 'bronze',
    Silver = 'silver',
    Gold = 'gold',
    Platinum = 'platinum',
}

export type PlayerId = string;

export interface PlayerProfile {
    id: PlayerId;
    name: string;
    rank: Rank;
    score: number;
    createdAt: Date;
}

export interface LeaderboardEntry {
    position: number;
    player: PlayerProfile;
    delta: number;
}

export type ScoreUpdate = Pick<PlayerProfile, 'id' | 'score'>;

export abstract class BaseRepository<T, ID> {
    protected readonly items = new Map<ID, T>();

    abstract findById(id: ID): T | undefined;
    abstract save(entity: T): void;

    findAll(): T[] {
        return Array.from(this.items.values());
    }

    delete(id: ID): boolean {
        return this.items.delete(id);
    }
}

export class PlayerRepository extends BaseRepository<PlayerProfile, PlayerId> {
    findById(id: PlayerId): PlayerProfile | undefined {
        return this.items.get(id);
    }

    save(player: PlayerProfile): void {
        this.items.set(player.id, player);
    }

    findByRank(rank: Rank): PlayerProfile[] {
        return this.findAll().filter(p => p.rank === rank);
    }

    static rankFromScore(score: number): Rank {
        if (score >= 10000) return Rank.Platinum;
        if (score >= 5000)  return Rank.Gold;
        if (score >= 1000)  return Rank.Silver;
        return Rank.Bronze;
    }
}

export function buildLeaderboard(players: PlayerProfile[]): LeaderboardEntry[] {
    return players
        .sort((a, b) => b.score - a.score)
        .map((player, index) => ({ position: index + 1, player, delta: 0 }));
}

export const computeDelta = (prev: number, curr: number): number => curr - prev;
