// GENERATED_BY_AI
// MODEL: claude-opus-5-5
// DATE: 2026-09-29
package com.td.czghagent.application.command.service;

import com.td.czghagent.domain.model.AuditEvent;
import com.td.czghagent.domain.model.OperationContext;
import com.td.czghagent.domain.port.PlatformDiagnostics;
import com.td.czghagent.domain.repository.AuditRepository;
import org.springframework.stereotype.Service;

/**
 * 系统验证里<strong>会花钱</strong>的两项探测。
 *
 * <p>只读探测直接走 {@link PlatformDiagnostics#check()}；这两项单独成命令，是因为它们
 * 真的在平台与 Atlas 那边留下一笔消耗——谁在什么时候点的，要能在审计流水里查到，
 * 否则月底对账时那几笔「不明来源的 1」没人说得清。
 */
@Service
public class PlatformDiagnosticsCommandService {

    private final PlatformDiagnostics diagnostics;
    private final AuditRepository auditRepository;

    public PlatformDiagnosticsCommandService(PlatformDiagnostics diagnostics,
                                             AuditRepository auditRepository) {
        this.diagnostics = diagnostics;
        this.auditRepository = auditRepository;
    }

    public PlatformDiagnostics.SpendResult probeAtlas(OperationContext context) {
        return audited(context, "PLATFORM_PROBE_ATLAS", diagnostics.probeAtlas());
    }

    public PlatformDiagnostics.SpendResult probeUsageReplay(OperationContext context) {
        return audited(context, "PLATFORM_PROBE_USAGE_REPLAY", diagnostics.probeUsageReplay());
    }

    private PlatformDiagnostics.SpendResult audited(OperationContext context, String action,
                                                    PlatformDiagnostics.SpendResult result) {
        auditRepository.append(AuditEvent.byUser(context, action, "PLATFORM", null,
                result.ok() ? AuditEvent.SUCCESS : AuditEvent.FAILED, truncate(result.detail())));
        return result;
    }

    private static String truncate(String detail) {
        return detail == null || detail.length() <= 480 ? detail : detail.substring(0, 480);
    }
}
