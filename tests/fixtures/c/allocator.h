#pragma once
#include <cstddef>

namespace Game {

class MemoryPool {
public:
    explicit MemoryPool(std::size_t blockSize, std::size_t blockCount);
    ~MemoryPool();
    void* allocate();
    void deallocate(void* ptr);
    bool ownsBlock(const void* ptr) const;
    std::size_t freeBlockCount() const;
    std::size_t totalBlockCount() const;
private:
    char*       m_pool;
    void**      m_freeList;
    std::size_t m_blockSize;
    std::size_t m_blockCount;
    std::size_t m_freeCount;
};

} // namespace Game
