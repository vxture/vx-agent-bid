// GENERATED_BY_AI
// MODEL: claude-opus-5-5
// DATE: 2026-09-29
package com.td.czghagent.domain.repository;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 开通投递流水的只读视图，只给系统验证用。
 *
 * <p><strong>刻意不放进 {@link ProvisioningRepository}。</strong>那个接口的方法集是封闭的
 * （{@code scripts/guardrails/check_provisioning_record_only.py}）：开通<em>状态</em>一旦有人读，
 * 丢一条投递就从「延迟」变成「永久缺失」，而本产品没有对账兜底。这里读的是投递<em>流水</em>
 * （收到过什么、怎么处置的），不是开通状态，也不该被任何门控或业务路径依赖——
 * 它只回答运维的一个问题：平台到底往这里投递过没有。
 */
public interface ProvisioningDeliveryLog {

    /** 最近收到的几次投递，新的在前。 */
    List<Delivery> recent(int limit);

    record Delivery(String eventType, String outcome, LocalDateTime receivedAt) {
    }
}
