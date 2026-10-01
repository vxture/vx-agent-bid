// GENERATED_BY_AI
// MODEL: claude-opus-5-5
// DATE: 2026-09-29
package com.td.czghagent.infrastructure.platform;

import com.sun.net.httpserver.Headers;
import com.sun.net.httpserver.HttpServer;
import com.td.czghagent.domain.exception.BusinessException;
import com.td.czghagent.domain.model.Entitlement;
import com.td.czghagent.domain.model.PlatformCallerContext;
import com.td.czghagent.domain.model.S2SToken;
import com.td.czghagent.domain.model.TenantScope;
import com.td.czghagent.domain.model.UsageEvent;
import com.td.czghagent.domain.port.EntitlementResolver;
import com.td.czghagent.domain.port.PlatformDiagnostics;
import com.td.czghagent.domain.port.S2STokenMinter;
import com.td.czghagent.domain.port.UsageConsumeClient;
import com.td.czghagent.domain.repository.ProvisioningDeliveryLog;
import com.td.czghagent.domain.repository.UsageBufferRepository;
import com.td.czghagent.infrastructure.integration.AiServiceHttpClient;
import com.td.czghagent.infrastructure.integration.AtlasCallCredentials;
import com.td.czghagent.infrastructure.oidc.OidcDiscovery;
import com.td.czghagent.infrastructure.oidc.OidcProperties;
import com.td.czghagent.infrastructure.oidc.PlatformS2STokenMinter;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.web.client.RestClient;

import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 系统验证的探测引擎：每一项都要<strong>真打一次</strong>，并把平台的原话带回来。
 *
 * <p>这组测试盯的是「看起来通了」的错法：权益端点答了「未覆盖」却被报成故障、
 * 重放第二次没标 replayed 却被报成通过、一条 Atlas 路由未授权却被其余几条的成功盖住。
 */
class PlatformDiagnosticsServiceTest {

    private static final Clock CLOCK = Clock.fixed(Instant.parse("2026-09-29T08:00:00Z"), ZoneOffset.UTC);
    private static final String WORKSPACE = "ws-3f1b";

    private HttpServer server;
    private String baseUrl;
    private final Map<String, String> bodies = new ConcurrentHashMap<>();
    private final Map<String, Integer> statuses = new ConcurrentHashMap<>();
    private final List<Headers> seen = new CopyOnWriteArrayList<>();

    private StubMinter minter;
    private StubConsume consume;

    @BeforeEach
    void setUp() throws Exception {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        for (String path : List.of("/platform/entitlements", "/internal/atlas/models", "/internal/atlas/routes",
                "/internal/atlas/contract", "/internal/atlas/probe")) {
            server.createContext(path, exchange -> {
                seen.add(exchange.getRequestHeaders());
                exchange.getRequestBody().readAllBytes();
                byte[] bytes = bodies.getOrDefault(path, "{}").getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().add("Content-Type", "application/json");
                exchange.getResponseHeaders().add("Cache-Control", "private, max-age=45");
                exchange.sendResponseHeaders(statuses.getOrDefault(path, 200), bytes.length);
                try (OutputStream out = exchange.getResponseBody()) {
                    out.write(bytes);
                }
            });
        }
        server.start();
        baseUrl = "http://127.0.0.1:" + server.getAddress().getPort();
        minter = new StubMinter();
        consume = new StubConsume();
    }

    @AfterEach
    void tearDown() {
        server.stop(0);
    }

    private PlatformDiagnosticsService service() {
        OidcProperties oidc = new OidcProperties("", "", "", "", "", "openid", false, 43200, "local");
        RestClient.Builder builder = RestClient.builder();
        AtlasCallCredentials atlas = new AtlasCallCredentials(minter);
        AiServiceHttpClient ai = new AiServiceHttpClient(builder, atlas, baseUrl, "internal", 30);
        return new PlatformDiagnosticsService(
                oidc, new OidcDiscovery(builder, oidc), minter, atlas, ai, new LiveResolver(), consume,
                new HmacWebhookSignatureVerifier("whsec", null, CLOCK),
                new EmptyBuffer(), new NoDeliveries(), builder, baseUrl, "http://atlas.internal", CLOCK);
    }

    private <T> T asMember(java.util.function.Supplier<T> action) {
        return PlatformCallerContext.run(new TenantScope("org-1", WORKSPACE), "user-access-token", action);
    }

    // ── C2 ─────────────────────────────────────────────────────────────────

    @Test
    void entitlementIsReadLiveWithTheBusinessTicketAndReportsCacheControl() {
        bodies.put("/platform/entitlements", """
                {"status":"active","tier":"pro","bundled":false,"limits":{"seats":5},"quota_pools":[]}
                """);

        PlatformDiagnostics.PlatformCheck check = asMember(() -> service().check());

        assertThat(check.c2().ok()).isTrue();
        assertThat(check.c2().detail()).contains("status=active", "tier=pro", "private, max-age=45");
        assertThat(minter.workspaces).contains(WORKSPACE);
        assertThat(seen).anySatisfy(headers ->
                assertThat(headers.getFirst("Authorization")).isEqualTo("Bearer vxture-token"));
    }

    @Test
    void anUncoveredWorkspaceIsReportedAsThePlatformsAnswerNotAsAnOutage() {
        // 平台 D2 覆盖门：本产品在该工作空间没有订阅/开通时拒绝铸 service 票。
        // 这是一个真实答复——报成「权益端点故障」会让人去查网络。
        minter.workspaceFailure = new BusinessException(PlatformS2STokenMinter.TARGET_NOT_PROVISIONED,
                "尚未开通", 502, false, null);

        PlatformDiagnostics.PlatformCheck check = asMember(() -> service().check());

        assertThat(check.c2().configured()).isTrue();
        assertThat(check.c2().ok()).isFalse();
        assertThat(check.c2().detail()).contains("invalid_target", "没有有效订阅或开通");
        assertThat(check.tokenMint().ok()).isFalse();
        assertThat(check.tokenMint().detail()).contains("atlas：已铸（OBO", "S2S_TARGET_NOT_PROVISIONED");
    }

    @Test
    void aLocalPlaceholderTenantCannotSpeakForAWorkspace() {
        PlatformDiagnostics.PlatformCheck check = PlatformCallerContext.run(
                TenantScope.local("u-1"), null, () -> service().check());

        assertThat(check.c2().ok()).isFalse();
        assertThat(check.c2().detail()).contains("以平台身份登录");
        assertThat(minter.workspaces).isEmpty();
    }

    // ── Atlas ──────────────────────────────────────────────────────────────

    @Test
    void atlasModelsAreReadThroughTheAiServiceWithTheMemberTicket() {
        bodies.put("/internal/atlas/models", "{\"count\":7,\"models\":[]}");

        PlatformDiagnostics.PlatformCheck check = asMember(() -> service().check());

        assertThat(check.atlas().ok()).isTrue();
        assertThat(check.atlas().detail()).contains("7 个模型");
        Headers toAi = seen.stream().filter(h -> h.containsKey("X-vxture-s2s-token")).findFirst().orElseThrow();
        assertThat(toAi.getFirst("X-Vxture-S2S-Token")).isEqualTo("atlas-obo-token");
        assertThat(toAi.getFirst("X-Vxture-Task-Id")).isEqualTo("diag-models-" + WORKSPACE + "-20260929");
    }

    @Test
    void aRouteThatCannotHonourOurThinkingModeFailsTheCapacityCheck() {
        bodies.put("/internal/atlas/routes", """
                {"maxRequestBytes":16777216,"routes":[
                  {"endpointCode":"chat/fast","ok":true,"contextWindow":256000,"maxOutputTokens":128000,
                   "thinkingModes":["off","on"],"problems":[],"unknown":[]},
                  {"endpointCode":"chat/deterministic","ok":false,
                   "problems":["不支持推理模式 off（本产品会发出）"],"unknown":[]}
                ]}
                """);

        PlatformDiagnostics.PlatformCheck check = asMember(() -> service().check());

        assertThat(check.atlasRoutes().ok()).isFalse();
        assertThat(check.atlasRoutes().detail())
                .contains("chat/fast 窗口 256000", "chat/deterministic ✗ 不支持推理模式 off", "16777216");
    }

    @Test
    void oneRefusedRouteFailsTheAtlasProbeEvenWhenTheOthersAnswer() {
        bodies.put("/internal/atlas/probe", """
                {"results":[
                  {"endpointCode":"chat/fast","ok":true,"modelCode":"m-fast","latencyMs":310,"totalTokens":12},
                  {"endpointCode":"chat/reasoning","ok":false,"code":"AI_ATLAS_NOT_ENTITLED","message":"no grant"}
                ]}
                """);

        PlatformDiagnostics.SpendResult result = asMember(() -> service().probeAtlas());

        assertThat(result.ok()).isFalse();
        assertThat(result.detail()).startsWith("1/2");
        assertThat(result.items()).extracting(PlatformDiagnostics.Probe::ok).containsExactly(true, false);
        assertThat(result.items().get(1).detail()).contains("chat/reasoning", "AI_ATLAS_NOT_ENTITLED");
        assertThat(result.items().get(0).detail()).contains("推理已关闭");
    }

    @Test
    void anAtlasProbeThatCannotMintSaysWhyInsteadOfCallingWithoutATicket() {
        PlatformDiagnostics.SpendResult result = PlatformCallerContext.run(
                TenantScope.local("u-1"), null, () -> service().probeAtlas());

        assertThat(result.ok()).isFalse();
        assertThat(result.detail()).contains(AtlasCallCredentials.NO_PLATFORM_TENANT);
        assertThat(seen).isEmpty();
    }

    // ── C3 重放 ────────────────────────────────────────────────────────────

    @Test
    void replayPassesOnlyWhenTheSecondAnswerIsMarkedReplayedWithTheFirstEventId() {
        consume.answers.add(new UsageConsumeClient.Outcome(200, false, false, "evt-1", null));
        consume.answers.add(new UsageConsumeClient.Outcome(200, false, true, "evt-1", null));

        PlatformDiagnostics.SpendResult result = asMember(() -> service().probeUsageReplay());

        assertThat(result.ok()).isTrue();
        assertThat(consume.keys).hasSize(2).containsOnly("probe-replay-" + WORKSPACE + "-20260929");
    }

    @org.junit.jupiter.params.ParameterizedTest
    @org.junit.jupiter.params.provider.CsvSource({
            // 两次都 200、都记下了——但第二次是一笔新账。这恰好是重放要抓的那种错。
            "false, evt-1",
            // 标了 replayed 却带回另一个 event_id：两侧的账对不上。
            "true, evt-2"
    })
    void aSecondAnswerThatIsNotTheFirstEventIsNotAReplay(boolean replayed, String secondEventId) {
        consume.answers.add(new UsageConsumeClient.Outcome(200, false, false, "evt-1", null));
        consume.answers.add(new UsageConsumeClient.Outcome(200, false, replayed, secondEventId, null));

        PlatformDiagnostics.SpendResult result = asMember(() -> service().probeUsageReplay());

        assertThat(result.ok()).isFalse();
        assertThat(result.items()).hasSize(2);
    }

    // ── C3 下行 ────────────────────────────────────────────────────────────

    @Test
    void webhookVerifierProvesItselfWithoutALiveDelivery() {
        PlatformDiagnostics.PlatformCheck check = asMember(() -> service().check());

        assertThat(check.c3Down().ok()).isTrue();
        assertThat(check.c3Down().detail()).contains("自检通过", "尚未收到任何投递");
        assertThat(new HmacWebhookSignatureVerifier("", null, CLOCK).selfTest()).isFalse();
    }

    // ── 替身 ───────────────────────────────────────────────────────────────

    private static final class StubMinter implements S2STokenMinter {
        final List<String> workspaces = new CopyOnWriteArrayList<>();
        volatile RuntimeException workspaceFailure;

        @Override
        public S2SToken onBehalfOf(String audience, String userAccessToken) {
            return token(audience + "-obo-token", audience, S2SToken.Mode.ON_BEHALF_OF);
        }

        @Override
        public S2SToken forService(String audience, TenantScope tenant) {
            return token(audience + "-svc-token", audience, S2SToken.Mode.SERVICE);
        }

        @Override
        public S2SToken forWorkspace(String audience, String workspaceId) {
            workspaces.add(workspaceId);
            if (workspaceFailure != null) {
                throw workspaceFailure;
            }
            return token(audience + "-token", audience, S2SToken.Mode.SERVICE);
        }

        @Override
        public void invalidate(S2SToken token) {
        }

        @Override
        public boolean isConfigured() {
            return true;
        }

        private static S2SToken token(String value, String audience, S2SToken.Mode mode) {
            return new S2SToken(value, audience, mode, null, "11111111-2222-3333-4444-555555555555",
                    LocalDateTime.now().plusSeconds(300));
        }
    }

    private static final class StubConsume implements UsageConsumeClient {
        final List<Outcome> answers = new ArrayList<>();
        final List<String> keys = new CopyOnWriteArrayList<>();

        @Override
        public Outcome consume(UsageBufferRepository.BufferedUsage usage) {
            keys.add(usage.idempotencyKey());
            return answers.remove(0);
        }

        @Override
        public boolean isMock() {
            return false;
        }
    }

    private static final class LiveResolver implements EntitlementResolver {
        @Override
        public Entitlement resolve(String workspaceId) {
            throw new AssertionError("诊断直读平台，不经缓存解析器");
        }

        @Override
        public void invalidate(String workspaceId) {
        }

        @Override
        public boolean isMock() {
            return false;
        }
    }

    private static final class EmptyBuffer implements UsageBufferRepository {
        @Override
        public void buffer(UsageEvent event, LocalDateTime occurredAt) {
        }

        @Override
        public List<BufferedUsage> claim(String claimToken, int limit, LocalDateTime now, LocalDateTime lease) {
            return List.of();
        }

        @Override
        public void markFlushed(Map<String, String> platformEventIds, LocalDateTime flushedAt) {
        }

        @Override
        public void release(List<String> idempotencyKeys, String reason) {
        }

        @Override
        public int purgeFlushedBefore(LocalDateTime before) {
            return 0;
        }

        @Override
        public long countUnflushed() {
            return 0;
        }
    }

    private static final class NoDeliveries implements ProvisioningDeliveryLog {
        @Override
        public List<Delivery> recent(int limit) {
            return List.of();
        }
    }
}

