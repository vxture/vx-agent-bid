// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-09
package com.td.czghagent.domain.repository;

import com.td.czghagent.domain.model.UsageEvent;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 用量缓冲区。
 *
 * <p>缓冲落在<strong>本产品自己的库里</strong>，而不是进程内存。区别在重启那一刻：
 * 内存缓冲区里没冲洗完的用量随进程一起消失，而那正是「刚上线一个新版本」
 * 与「刚出过一次故障」这两个用量最值得对账的时刻。
 *
 * <p>更要紧的是，落库让计量可以和被计量的那件事<strong>同一个事务提交</strong>：
 * 导出回滚了，那条用量也就不存在，不需要任何补偿逻辑。
 */
public interface UsageBufferRepository {

    /**
     * 写入一条待冲洗的用量。
     *
     * <p>按幂等键去重：同一个键第二次写入是无操作，不是覆盖也不是报错。
     */
    void buffer(UsageEvent event, LocalDateTime occurredAt);

    /**
     * 认领一批待冲洗的行，返回认领到的那些。
     *
     * <p>api 与 worker 跑的是同一个镜像，两边都会起冲洗任务。认领用数据库行锁
     * 做互斥：先 UPDATE 打上令牌，再按令牌读回——两个节点同时打令牌时，
     * 后到的那个在拿到行锁后会看到 {@code claimed_at} 已被填上，条件不再成立。
     *
     * @param lease 租约边界；早于它的认领视为认领者已死，可以被抢走
     */
    List<BufferedUsage> claim(String claimToken, int limit, LocalDateTime now, LocalDateTime lease);

    /**
     * 标记为已冲洗，并记下平台给这一行的用量事件 id。行不立刻删除——对账要看得见已经报过什么。
     *
     * @param platformEventIds 幂等键 → 平台 consume 返回的 {@code event_id}（可为 null：替身或
     *                         未返回该字段的平台版本）。重放时平台返回的是<strong>原始事件</strong>的 id，
     *                         这正是两侧能逐条对上的原因（通则 C3 上行）
     */
    void markFlushed(Map<String, String> platformEventIds, LocalDateTime flushedAt);

    /**
     * 归还认领并记下失败原因。
     *
     * <p>不归还的后果是这批行要等一整个租约周期才会被重试，
     * 而平台的一次 502 通常几秒钟就恢复了。
     */
    void release(List<String> idempotencyKeys, String reason);

    /** 清掉已冲洗且过了对账窗口的行。 */
    int purgeFlushedBefore(LocalDateTime before);

    /** 尚未冲洗的行数。系统验证用它说明「上报链路是不是积压了」。 */
    long countUnflushed();

    /**
     * 缓冲区里一条待冲洗的用量。
     *
     * @param attempts 已尝试次数，只用于观测——<strong>不设上限丢弃</strong>：
     *                 一条报不上去的用量是账，丢掉它等于悄悄少收一笔钱
     */
    record BufferedUsage(
            String idempotencyKey, String workspaceId, String metric, long amount,
            String endUserId, String taskId, LocalDateTime occurredAt, int attempts) {
    }
}
