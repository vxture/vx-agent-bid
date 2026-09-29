// GENERATED_BY_AI
// MODEL: claude-opus-5-5
// DATE: 2026-09-29
package com.td.czghagent.rest;

import com.td.czghagent.application.command.service.PlatformDiagnosticsCommandService;
import com.td.czghagent.domain.port.PlatformDiagnostics;
import com.td.czghagent.rest.security.RequestIdentity;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 管理面：系统验证。
 *
 * <p>{@code /api/status} 报「配没配」，这里报「通不通」——每次请求都真打一遍。
 * 挂在 {@code /api/admin} 下，由认证过滤器按管理员角色拦截：它暴露的是本部署的
 * 接入拓扑与换票结论，而两个 POST 会产生真实消耗。
 */
@RestController
@RequestMapping("/api/admin/platform-check")
public class PlatformCheckController {

    private final PlatformDiagnostics diagnostics;
    private final PlatformDiagnosticsCommandService commands;

    public PlatformCheckController(PlatformDiagnostics diagnostics,
                                   PlatformDiagnosticsCommandService commands) {
        this.diagnostics = diagnostics;
        this.commands = commands;
    }

    /** 只读探测，不产生费用。 */
    @GetMapping
    public PlatformDiagnostics.PlatformCheck check() {
        return diagnostics.check();
    }

    /** 逐条路由各打一次 Atlas。<strong>会花钱。</strong> */
    @PostMapping("/atlas-probe")
    public PlatformDiagnostics.SpendResult probeAtlas(HttpServletRequest request) {
        return commands.probeAtlas(RequestIdentity.operation(request));
    }

    /** C3 幂等重放。<strong>会花钱</strong>：每个工作空间每天至多一笔。 */
    @PostMapping("/usage-replay-probe")
    public PlatformDiagnostics.SpendResult probeUsageReplay(HttpServletRequest request) {
        return commands.probeUsageReplay(RequestIdentity.operation(request));
    }
}
