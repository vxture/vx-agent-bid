// GENERATED_BY_AI
// MODEL: claude-opus-5-5
// DATE: 2026-09-29
package com.td.czghagent.domain.port;

import java.util.List;

/**
 * 系统验证：本产品这一端与平台的对接<strong>现在</strong>能不能走通。
 *
 * <p>与 {@code /api/status} 的分工：那边报「配没配」，这里报「通不通」。配齐了而换票被拒、
 * 票铸出来而 Atlas 不认、权益端点答了但答的是「未覆盖」——这些都只有真打一次才看得见。
 *
 * <p>调用方身份取自当前请求的 {@code PlatformCallerContext}，与业务调用同一条链：
 * 探测证明的是「本产品的调用能走通」，而不是「某条专门的诊断线路能走通」。
 *
 * <p>{@link #check()} 全部只读、不产生费用。另外两个方法<strong>会花钱</strong>，
 * 各自单独暴露，调用方必须经过一次显式确认才能触发。
 */
public interface PlatformDiagnostics {

    /** 只读探测：身份、换票、权益、用量上下行、Atlas 带票读模型清单。 */
    PlatformCheck check();

    /** 对本产品真正会调用的每条 Atlas 路由各发一次最短的真实调用。会花钱，由 Atlas 自行计量。 */
    SpendResult probeAtlas();

    /**
     * C3 幂等重放：同一个幂等键上报两次，第二次必须答 {@code replayed:true} 且带回第一次的
     * {@code event_id}。会花钱：每个工作空间每天至多记一笔（键按日期稳定）。
     */
    SpendResult probeUsageReplay();

    /**
     * 一项探测的结果。
     *
     * @param configured 这条通道配没配；未配时 {@code ok} 恒假，界面显示「未配置」而不是「异常」
     * @param ok         真打一次的结论
     * @param detail     给人看的一句话，写明依据；绝不含密钥
     */
    record Probe(boolean configured, boolean ok, String detail) {

        public static Probe notConfigured(String what) {
            return new Probe(false, false, what + " 未配置");
        }
    }

    record PlatformCheck(
            String time,
            Probe c1,
            Probe tokenMint,
            Probe c2,
            Probe c3Up,
            Probe c3Down,
            Probe atlas,
            Probe atlasRoutes,
            Probe usageReplay
    ) {
    }

    /**
     * 会花钱的探测的结果。
     *
     * @param ok     整体结论
     * @param detail 一句话总结
     * @param items  逐项明细（Atlas 为逐条路由，重放为两次答复）
     */
    record SpendResult(boolean ok, String detail, List<Probe> items) {
    }
}
