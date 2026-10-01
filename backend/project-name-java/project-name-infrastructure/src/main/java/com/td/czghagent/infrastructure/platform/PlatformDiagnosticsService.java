// GENERATED_BY_AI
// MODEL: claude-opus-5-5
// DATE: 2026-09-29
package com.td.czghagent.infrastructure.platform;

import com.fasterxml.jackson.databind.JsonNode;
import com.td.czghagent.domain.exception.BusinessException;
import com.td.czghagent.domain.model.Entitlement;
import com.td.czghagent.domain.model.PlatformCallerContext;
import com.td.czghagent.domain.model.ProductIdentity;
import com.td.czghagent.domain.model.S2SToken;
import com.td.czghagent.domain.model.TaskContext;
import com.td.czghagent.domain.model.TenantScope;
import com.td.czghagent.domain.model.UsageMetric;
import com.td.czghagent.domain.port.EntitlementResolver;
import com.td.czghagent.domain.port.PlatformDiagnostics;
import com.td.czghagent.domain.port.S2STokenMinter;
import com.td.czghagent.domain.port.UsageConsumeClient;
import com.td.czghagent.domain.port.WebhookSignatureVerifier;
import com.td.czghagent.domain.repository.ProvisioningDeliveryLog;
import com.td.czghagent.domain.repository.UsageBufferRepository;
import com.td.czghagent.infrastructure.integration.AiServiceHttpClient;
import com.td.czghagent.infrastructure.integration.AtlasCallCredentials;
import com.td.czghagent.infrastructure.oidc.OidcDiscovery;
import com.td.czghagent.infrastructure.oidc.OidcProperties;
import com.td.czghagent.infrastructure.oidc.PlatformS2STokenMinter;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Duration;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;

/**
 * 系统验证的探测引擎。每一项都<strong>真打一次</strong>，走业务路径同一个客户端、同一张票。
 *
 * <p>参照 yucer 的 {@code /api/platform-check}：只读探测一次全跑，会花钱的两项各自单独触发。
 * 与它不同的一处：本产品的模型调用由 Python 服务发出，所以 Atlas 的两个探测经
 * {@code /internal/atlas/*} 转一跳——那正是生成正文时走的那一跳，绕开它证明不了任何业务链路。
 *
 * <p><strong>任何一项都不抛出。</strong>一项失败写进它自己的结果，其余照常；
 * 一个会因为第一项失败就整页 500 的诊断页，恰好在最需要它的时候不可用。
 * <strong>detail 里绝不出现密钥</strong>——一个会泄露密钥的自证页面本身就是它要证明的那类问题。
 */
@Component
public class PlatformDiagnosticsService implements PlatformDiagnostics {

    private static final DateTimeFormatter DAY = DateTimeFormatter.BASIC_ISO_DATE;

    /** 重放探测用的指标。任选一个已登记的：它只证明幂等键被平台认得，不代表一次真实导出。 */
    static final UsageMetric REPLAY_METRIC = UsageMetric.DOCUMENT_EXPORTS;

    private final OidcProperties oidcProperties;
    private final OidcDiscovery oidcDiscovery;
    private final S2STokenMinter minter;
    private final AtlasCallCredentials atlasCredentials;
    private final AiServiceHttpClient aiService;
    private final EntitlementResolver entitlementResolver;
    private final UsageConsumeClient usageConsumeClient;
    private final WebhookSignatureVerifier webhookVerifier;
    private final UsageBufferRepository usageBuffer;
    private final ProvisioningDeliveryLog deliveries;
    private final RestClient client;
    private final String platformApiUrl;
    private final String atlasApiUrl;
    private final Clock clock;

    @Autowired
    public PlatformDiagnosticsService(
            OidcProperties oidcProperties,
            OidcDiscovery oidcDiscovery,
            S2STokenMinter minter,
            AtlasCallCredentials atlasCredentials,
            AiServiceHttpClient aiService,
            EntitlementResolver entitlementResolver,
            UsageConsumeClient usageConsumeClient,
            WebhookSignatureVerifier webhookVerifier,
            UsageBufferRepository usageBuffer,
            ProvisioningDeliveryLog deliveries,
            RestClient.Builder builder,
            @Value("${app.platform.api-url:}") String platformApiUrl,
            @Value("${app.atlas.api-url:}") String atlasApiUrl
    ) {
        this(oidcProperties, oidcDiscovery, minter, atlasCredentials, aiService, entitlementResolver,
                usageConsumeClient, webhookVerifier, usageBuffer, deliveries, builder,
                platformApiUrl, atlasApiUrl, Clock.systemUTC());
    }

    PlatformDiagnosticsService(
            OidcProperties oidcProperties,
            OidcDiscovery oidcDiscovery,
            S2STokenMinter minter,
            AtlasCallCredentials atlasCredentials,
            AiServiceHttpClient aiService,
            EntitlementResolver entitlementResolver,
            UsageConsumeClient usageConsumeClient,
            WebhookSignatureVerifier webhookVerifier,
            UsageBufferRepository usageBuffer,
            ProvisioningDeliveryLog deliveries,
            RestClient.Builder builder,
            String platformApiUrl,
            String atlasApiUrl,
            Clock clock
    ) {
        this.oidcProperties = oidcProperties;
        this.oidcDiscovery = oidcDiscovery;
        this.minter = minter;
        this.atlasCredentials = atlasCredentials;
        this.aiService = aiService;
        this.entitlementResolver = entitlementResolver;
        this.usageConsumeClient = usageConsumeClient;
        this.webhookVerifier = webhookVerifier;
        this.usageBuffer = usageBuffer;
        this.deliveries = deliveries;
        this.client = builder.build();
        this.platformApiUrl = platformApiUrl == null ? "" : platformApiUrl.replaceAll("/+$", "");
        this.atlasApiUrl = atlasApiUrl == null ? "" : atlasApiUrl.trim();
        this.clock = clock;
    }

    @Override
    public PlatformCheck check() {
        return new PlatformCheck(
                LocalDateTime.now(clock).toString(),
                c1(), tokenMint(), c2(), c3Up(), c3Down(), atlasModels(), atlasRoutes(), atlasContract(),
                new Probe(!platformApiUrl.isBlank() && !usageConsumeClient.isMock(), false,
                        "只读探测不跑这一项：点「运行重放校验」会把同一个幂等键上报两次，"
                                + "期望第二次答 replayed:true 且带回第一次的 event_id；"
                                + "每个工作空间每天至多记一笔 " + REPLAY_METRIC.key()));
    }

    // ── C1 身份 ────────────────────────────────────────────────────────────

    private Probe c1() {
        if (!oidcProperties.isConfigured()) {
            return Probe.notConfigured("OIDC（issuer / client / redirect_uri）");
        }
        try {
            OidcDiscovery.Document document = oidcDiscovery.document();
            JsonNode jwks = client.get().uri(document.jwksUri()).retrieve().body(JsonNode.class);
            int keys = jwks == null ? 0 : jwks.path("keys").size();
            return new Probe(true, keys > 0,
                    "发现文档可达，issuer 与配置一致；JWKS " + keys + " 把密钥；client "
                            + oidcProperties.clientId()
                            + (oidcProperties.isActive() ? "，已启用" : "，未启用（OIDC_ENABLED=false）"));
        } catch (RuntimeException exception) {
            return failed("身份服务", exception);
        }
    }

    // ── C1b 换票 ───────────────────────────────────────────────────────────

    /**
     * 按业务路径的<strong>原样</strong>铸两张票：给 Atlas 的（有用户票走 OBO）和给平台面的
     * （C2/C3 用，service 模式，受平台 D2 覆盖门约束）。
     */
    private Probe tokenMint() {
        if (!minter.isConfigured()) {
            return Probe.notConfigured("S2S 换票（即 C1 的 client 对）");
        }
        List<String> lines = new ArrayList<>();
        boolean ok = true;
        try {
            lines.add("atlas：" + describe(atlasCredentials.mintOrExplain()));
        } catch (RuntimeException exception) {
            ok = false;
            lines.add("atlas：" + reason(exception));
        }
        String workspaceId = platformWorkspace();
        if (workspaceId == null) {
            ok = false;
            lines.add("vxture：当前会话没有平台工作空间，无从声明");
        } else {
            try {
                lines.add("vxture：" + describe(minter.forWorkspace(PlatformCallCredentials.AUDIENCE, workspaceId)));
            } catch (RuntimeException exception) {
                ok = false;
                lines.add("vxture：" + reason(exception));
            }
        }
        return new Probe(true, ok, "act.sub=" + ProductIdentity.PRODUCT_CODE + "；" + String.join("；", lines));
    }

    private String describe(S2SToken token) {
        long seconds = Math.max(0, Duration.between(LocalDateTime.now(), token.expiresAt()).toSeconds());
        String mode = token.mode() == S2SToken.Mode.ON_BEHALF_OF ? "OBO" : "service";
        // tenant_id 缺失不是换票失败，但 Atlas 会拿它断言 UUID——值得在这里点名。
        String tenant = token.tenantId() == null || token.tenantId().isBlank()
                ? "票上没有 tenant_id" : "tenant_id 已签入";
        return "已铸（" + mode + "，" + tenant + "，" + seconds + " 秒后过期）";
    }

    // ── C2 权益 ────────────────────────────────────────────────────────────

    /**
     * 直读一次，不走 45 秒缓存：要看的是平台<strong>现在</strong>怎么答，以及它实际下发的
     * Cache-Control。
     */
    private Probe c2() {
        if (entitlementResolver.isMock() || platformApiUrl.isBlank()) {
            return Probe.notConfigured("PLATFORM_API_URL（当前为替身权益）");
        }
        String workspaceId = platformWorkspace();
        if (workspaceId == null) {
            return new Probe(true, false, "以平台身份登录后才能读取本工作空间的实时权益");
        }
        try {
            S2SToken token = minter.forWorkspace(PlatformCallCredentials.AUDIENCE, workspaceId);
            ResponseEntity<JsonNode> response = client.get()
                    .uri(platformApiUrl + "/platform/entitlements?workspace_id=" + encode(workspaceId)
                            + "&product=" + encode(ProductIdentity.PRODUCT_CODE))
                    .headers(headers -> PlatformCallCredentials.apply(headers, token))
                    .retrieve()
                    .toEntity(JsonNode.class);
            Entitlement entitlement = PlatformEntitlementResolver.parse(workspaceId, response.getBody());
            String cacheControl = response.getHeaders().getCacheControl();
            return new Probe(true, true,
                    "status=" + orNull(entitlement.status(), "null（从未订阅）")
                            + "，tier=" + orNull(entitlement.tier(), "null")
                            + "，bundled=" + entitlement.bundled()
                            + "，" + entitlement.limits().size() + " 项上限，"
                            + entitlement.quotaPools().size() + " 个配额池；Cache-Control: "
                            + orNull(cacheControl, "（未下发）"));
        } catch (BusinessException exception) {
            if (PlatformS2STokenMinter.TARGET_NOT_PROVISIONED.equals(exception.getErrorCode())) {
                // 平台答了，答案是「没有」：D2 覆盖门拒绝为一个本产品没有订阅/开通的工作空间铸票。
                // 这是一个真实的答复而不是故障——业务路径也会把它读成「未订阅」。
                return new Probe(true, false,
                        "换票被平台 D2 覆盖门拒绝（invalid_target）：本产品在该工作空间没有有效订阅或开通。"
                                + "权益读取因此答「未订阅」；在平台为该工作空间开通本产品后重新探测");
            }
            return failed("权益端点", exception);
        } catch (RuntimeException exception) {
            return failed("权益端点", exception);
        }
    }

    // ── C3 上行 / 下行 ─────────────────────────────────────────────────────

    private Probe c3Up() {
        if (usageConsumeClient.isMock() || platformApiUrl.isBlank()) {
            return Probe.notConfigured("PLATFORM_API_URL（当前为替身上报，用量不入账）");
        }
        try {
            long pending = usageBuffer.countUnflushed();
            return new Probe(true, true,
                    "POST /usage/consume 已配置（永远 200，x-request-id 随行）；缓冲区待冲洗 "
                            + pending + " 行；登记指标 "
                            + java.util.Arrays.stream(UsageMetric.values()).map(UsageMetric::key)
                            .collect(Collectors.joining(" / ")));
        } catch (RuntimeException exception) {
            return failed("用量缓冲区", exception);
        }
    }

    private Probe c3Down() {
        if (!webhookVerifier.isConfigured()) {
            return Probe.notConfigured("PROVISION_WEBHOOK_SECRET");
        }
        boolean selfTest = webhookVerifier.selfTest();
        String seen;
        try {
            List<ProvisioningDeliveryLog.Delivery> recent = deliveries.recent(5);
            seen = recent.isEmpty()
                    ? "尚未收到任何投递——请平台线发一次测试投递"
                    : "最近投递：" + recent.stream()
                    .map(d -> d.eventType() + "（" + d.outcome() + "，" + d.receivedAt() + "）")
                    .collect(Collectors.joining("，"));
        } catch (RuntimeException exception) {
            seen = "读取投递记录失败：" + reason(exception);
        }
        return new Probe(true, selfTest,
                "验签自检" + (selfTest ? "通过（合成签名被认、篡改一个字节被拒）" : "失败")
                        + "；接收地址 " + ProductIdentity.PLATFORM_WEBHOOK_PATH + "；" + seen);
    }

    // ── Atlas ──────────────────────────────────────────────────────────────

    /** 带票读模型清单：不计量，是「票被 Atlas 认」最便宜的证明。 */
    private Probe atlasModels() {
        if (atlasApiUrl.isBlank()) {
            return Probe.notConfigured("ATLAS_API_URL（模型调用正在直连供应商，不入平台的账）");
        }
        try {
            S2SToken token = atlasCredentials.mintOrExplain();
            JsonNode body = TaskContext.run(taskId("diag-models"), () -> aiService.atlasModels(token));
            int count = body.path("count").asInt(0);
            return new Probe(true, true,
                    "Atlas " + atlasApiUrl + "：带票 GET /v1/models 答 200，本产品可见 " + count + " 个模型");
        } catch (RuntimeException exception) {
            return failed("Atlas " + atlasApiUrl + " 带票读模型清单", exception);
        }
    }

    /**
     * 路由容量与推理模式：本产品实际使用的每条路由是否 active、是否支持我们会发出的推理模式、
     * 窗口是否放得下最大的单次输入。运营改路由指向时，最可能悄悄打破的是推理模式——
     * 不支持时那条路由上的每一次调用都是 {@code 422 THINKING_MODE_UNSUPPORTED}。
     */
    private Probe atlasRoutes() {
        if (atlasApiUrl.isBlank()) {
            return Probe.notConfigured("ATLAS_API_URL");
        }
        try {
            S2SToken token = atlasCredentials.mintOrExplain();
            JsonNode body = TaskContext.run(taskId("diag-routes"), () -> aiService.atlasRoutes(token));
            List<String> lines = new ArrayList<>();
            boolean ok = true;
            for (JsonNode route : body.path("routes")) {
                boolean routeOk = route.path("ok").asBoolean(false);
                ok &= routeOk;
                StringBuilder line = new StringBuilder(route.path("endpointCode").asText("?"));
                if (routeOk) {
                    line.append(" 窗口 ").append(route.path("contextWindow").asText("未知"))
                            .append(" / 输出 ").append(route.path("maxOutputTokens").asText("未知"))
                            .append("，推理模式 ").append(route.path("thinkingModes").toString());
                } else {
                    line.append(" ✗ ").append(joinTexts(route.path("problems")));
                }
                if (route.path("unknown").size() > 0) {
                    line.append("（Atlas 未公布：").append(joinTexts(route.path("unknown"))).append("）");
                }
                lines.add(line.toString());
            }
            return new Probe(true, ok && !lines.isEmpty(), String.join("；", lines)
                    + "；请求体上限 " + body.path("maxRequestBytes").asText("未知") + " 字节");
        } catch (RuntimeException exception) {
            return failed("Atlas 路由容量", exception);
        }
    }

    /**
     * 契约指纹：Atlas 的必填规则与错误码词表是否还是本产品核对过的那一版。
     *
     * <p>指纹只在契约变化时才动，所以这一项是 Atlas 发版后唯一需要例行看的东西。
     * 不一致不代表调用已经坏了，代表要对着新契约逐条核对客户端，核对完再改钉住的值。
     */
    private Probe atlasContract() {
        if (atlasApiUrl.isBlank()) {
            return Probe.notConfigured("ATLAS_API_URL");
        }
        try {
            S2SToken token = atlasCredentials.mintOrExplain();
            JsonNode body = TaskContext.run(taskId("diag-contract"), () -> aiService.atlasContract(token));
            boolean matches = body.path("matches").asBoolean(false);
            String live = body.path("fingerprint").asText("未知");
            String pinned = body.path("pinned").asText("?");
            return new Probe(true, matches, matches
                    ? "线上契约指纹 " + live + " 与本产品核对过的一致；错误码 "
                            + body.path("errorCodeCount").asText("?") + " 条"
                    : "线上契约指纹 " + live + " ≠ 本产品核对过的 " + pinned
                            + "：Atlas 改了必填规则或错误码，需要对照新契约逐条核对后再更新");
        } catch (RuntimeException exception) {
            return failed("Atlas 契约", exception);
        }
    }

    private static String joinTexts(JsonNode array) {
        List<String> values = new ArrayList<>();
        array.forEach(item -> values.add(item.asText()));
        return String.join("、", values);
    }

    @Override
    public SpendResult probeAtlas() {
        if (atlasApiUrl.isBlank()) {
            return new SpendResult(false, "ATLAS_API_URL 未配置，模型调用正在直连供应商", List.of());
        }
        S2SToken token;
        try {
            token = atlasCredentials.mintOrExplain();
        } catch (RuntimeException exception) {
            return new SpendResult(false, "铸不出 Atlas 的票：" + reason(exception), List.of());
        }
        JsonNode body;
        try {
            body = TaskContext.run(taskId("diag-atlas"), () -> aiService.atlasProbe(token));
        } catch (RuntimeException exception) {
            return new SpendResult(false, "Atlas 探测失败：" + reason(exception), List.of());
        }
        List<Probe> items = new ArrayList<>();
        for (JsonNode result : body.path("results")) {
            String route = result.path("endpointCode").asText("?");
            if (result.path("ok").asBoolean(false)) {
                // 探测带 thinking=off；Python 侧已核对回显与推理内容，走到这里即已关闭推理。
                // 应答模型可能是路由的备选模型：Atlas 不在响应里标明主备，这里如实给出模型名。
                items.add(new Probe(true, true, route + "：模型 " + result.path("modelCode").asText("?")
                        + " 应答，推理已关闭，" + result.path("latencyMs").asText("?") + " ms，"
                        + result.path("totalTokens").asText("?") + " token"));
            } else {
                items.add(new Probe(true, false, route + "：" + result.path("code").asText("?")
                        + " · " + result.path("message").asText("")));
            }
        }
        long passed = items.stream().filter(Probe::ok).count();
        boolean ok = !items.isEmpty() && passed == items.size();
        return new SpendResult(ok, passed + "/" + items.size()
                + " 条路由走通（请求 thinking=off，核对了 Atlas 的回显）；"
                + "消耗由 Atlas 按 atlas.chat 自行计量上报，本产品不另记", items);
    }

    // ── C3 重放 ────────────────────────────────────────────────────────────

    @Override
    public SpendResult probeUsageReplay() {
        if (usageConsumeClient.isMock() || platformApiUrl.isBlank()) {
            return new SpendResult(false, "PLATFORM_API_URL 未配置，当前为替身上报", List.of());
        }
        String workspaceId = platformWorkspace();
        if (workspaceId == null) {
            return new SpendResult(false, "以平台身份登录后才能以本工作空间上报", List.of());
        }
        String day = LocalDate.now(clock).format(DAY);
        // 键按日期稳定：同一天重复点击命中同一条已记下的事件，而不是再花一次。
        UsageBufferRepository.BufferedUsage row = new UsageBufferRepository.BufferedUsage(
                "probe-replay-" + workspaceId + "-" + day, workspaceId, REPLAY_METRIC.key(), 1,
                null, taskId("diag-replay"), LocalDateTime.now(clock), 0);
        try {
            UsageConsumeClient.Outcome first = usageConsumeClient.consume(row);
            UsageConsumeClient.Outcome second = usageConsumeClient.consume(row);
            boolean ok = first.recorded() && second.recorded() && second.replayed()
                    && first.eventId() != null && first.eventId().equals(second.eventId());
            return new SpendResult(ok,
                    ok ? "幂等已验证：事件 " + second.eventId() + " 答了两次，第二次标为 replayed"
                            : "幂等未验证——比对下面两次答复",
                    List.of(outcome("第一次", first), outcome("第二次", second)));
        } catch (RuntimeException exception) {
            return new SpendResult(false, "上报失败：" + reason(exception), List.of());
        }
    }

    private static Probe outcome(String label, UsageConsumeClient.Outcome outcome) {
        return new Probe(true, outcome.recorded(), label + "：HTTP " + outcome.status()
                + "，event_id=" + outcome.eventId() + "，replayed=" + outcome.replayed()
                + "，gated=" + outcome.gated()
                + (outcome.reason() == null ? "" : "（" + outcome.reason() + "）"));
    }

    // ── 公共 ───────────────────────────────────────────────────────────────

    /** 当前会话的平台工作空间；过渡租户（{@code local:}）视为没有。 */
    private static String platformWorkspace() {
        TenantScope tenant = PlatformCallerContext.tenant();
        return tenant == null || tenant.usesLocalPlaceholder() ? null : tenant.workspaceId();
    }

    /**
     * 诊断调用自带 task_id：Atlas 与平台都强制要求它，而它也是在对方日志里找到这几笔的唯一键。
     */
    private String taskId(String prefix) {
        String workspace = platformWorkspace();
        String id = prefix + "-" + (workspace == null ? "none" : workspace) + "-"
                + LocalDate.now(clock).format(DAY);
        return id.length() > TaskContext.MAX_LENGTH ? id.substring(0, TaskContext.MAX_LENGTH) : id;
    }

    private static Probe failed(String what, RuntimeException exception) {
        return new Probe(true, false, what + "：" + reason(exception));
    }

    /**
     * 一句话说清失败。只取码、状态与消息，不带响应体原文——换票表单里有 client_secret，
     * 一个回显请求参数的端点会让密钥进这一页。
     */
    static String reason(RuntimeException exception) {
        if (exception instanceof BusinessException business) {
            return business.getErrorCode() + " · " + business.getMessage();
        }
        if (exception instanceof RestClientResponseException response) {
            return "HTTP " + response.getStatusCode().value();
        }
        String message = exception.getMessage();
        return exception.getClass().getSimpleName()
                + (message == null ? "" : " · " + message.substring(0, Math.min(200, message.length())));
    }

    private static String orNull(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }

    private static String encode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }
}
