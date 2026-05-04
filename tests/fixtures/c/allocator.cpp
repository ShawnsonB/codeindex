#include "allocator.h"
#include <cstdlib>
#include <cassert>

namespace Game {

MemoryPool::MemoryPool(std::size_t blockSize, std::size_t blockCount)
    : m_blockSize(blockSize), m_blockCount(blockCount), m_freeCount(blockCount) {
    m_pool = static_cast<char*>(std::malloc(blockSize * blockCount));
    m_freeList = static_cast<void**>(std::malloc(sizeof(void*) * blockCount));
    for (std::size_t i = 0; i < blockCount; ++i)
        m_freeList[i] = m_pool + i * blockSize;
}

MemoryPool::~MemoryPool() {
    std::free(m_freeList);
    std::free(m_pool);
}

void* MemoryPool::allocate() {
    if (m_freeCount == 0) return nullptr;
    return m_freeList[--m_freeCount];
}

void MemoryPool::deallocate(void* ptr) {
    assert(ownsBlock(ptr));
    m_freeList[m_freeCount++] = ptr;
}

bool MemoryPool::ownsBlock(const void* ptr) const {
    const char* p = static_cast<const char*>(ptr);
    return p >= m_pool && p < m_pool + m_blockSize * m_blockCount;
}

std::size_t MemoryPool::freeBlockCount() const { return m_freeCount; }

std::size_t MemoryPool::totalBlockCount() const { return m_blockCount; }

} // namespace Game
