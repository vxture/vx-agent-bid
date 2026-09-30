// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-09
package com.td.czghagent.infrastructure.integration;

import com.sun.net.httpserver.Headers;
import com.sun.net.httpserver.HttpServer;
import com.td.czghagent.domain.exception.AiGatewayException;
import com.td.czghagent.domain.exception.BusinessException;
import com.td.czghagent.domain.model.PlatformCallerContext;
import com.td.czghagent.domain.model.S2SToken;
import com.td.czghagent.domain.model.TaskContext;
import com.td.czghagent.domain.model.TenantScope;
import com.td.czghagent.domain.port.S2STokenMinter;
import com.td.czghagent.domain.port.TenderAiGateway;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.web.client.RestClient;

import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Java 与 Python 之间那一层错误翻译。
 *
 * <p>它决定每一次模型调用失败之后：报什么错误码、算不算超时、要不要重铸票。
 * 这三个判断都<strong>不会自己报错</strong>——错误码接错了，Temporal 的重试策略
 * 就按错的那条走；超时判成不可用，用户看到的是「服务挂了」而不是「等太久了」；
 * 重铸判错了，要么每次调用都 401，要么一次不幂等的正文生成被重复计费。
 *
 * <p>用真会说 HTTP 的假服务而不是打桩 RestClient：这一层的一半逻辑在
 * Spring 抛出什么异常上，而打桩会把那一半替换掉。
 */
class AiServiceHttpClientTest {

    private HttpServer server;
    private AiServiceHttpClient client;
    private RecordingMinter minter;

    private final AtomicInteger requestCount = new AtomicInteger();
    private final AtomicReference<String> responseBody = new AtomicReference<>(okBody());
    private final AtomicReference<Integer> responseStatus = new AtomicReference<>(200);
    private final AtomicReference<Long> handlerDelayMillis = new AtomicReference<>(0L);
    private final List<Headers> seenHeaders = new ArrayList<>();

    @BeforeEach
    void setUp() throws Exception {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/internal/tender/outline", exchange -> {
            requestCount.incrementAndGet();
            seenHeaders.add(exchange.getRequestHeaders());
            exchange.getRequestBody().readAllBytes();
            long delay = handlerDelayMillis.get();
            if (delay > 0) {
                try {
                    Thread.sleep(delay);
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                }
            }
            byte[] bytes = responseBody.get().getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(responseStatus.get(), bytes.length);
            try (OutputStream out = exchange.getResponseBody()) {
                out.write(bytes);
            }
        });
        server.start();
        minter = new RecordingMinter();
        client = newClient(2);
    }

    @AfterEach
    void tearDown() {
        server.stop(0);
    }

    // ── 重铸票：只重一次，且只为拒票 ────────────────────────────────────────

    /**
     * 被调方说票不认，就作废重铸再来一次——<strong>只来一次</strong>。
     *
     * <p>不作废就重铸的话，缓存里那张被拒的票会被用满剩下的有效期，
     * 期间每一次调用都 401；而无限重试会把一次凭据问题放大成一场风暴。
     */
    @Test
    void remintsOnceWhenTheCalleeRejectsTheToken() {
        responseStatus.set(502);
        responseBody.set(errorBody("AI_ATLAS_TOKEN_REJECTED", "token rejected"));

        assertThatThrownBy(this::callOutline).isInstanceOf(AiGatewayException.class);

        assertThat(requestCount.get()).as("原调用一次，重铸后再一次，就此为止").isEqualTo(2);
        assertThat(minter.invalidated).as("被拒的票必须从缓存里作废").hasSize(1);
        assertThat(minter.minted).isEqualTo(2);
    }

    /**
     * 其它失败<strong>一律不重试</strong>。
     *
     * <p>每一次调用都被计量和审计，而最值得重试的操作恰好都不是幂等的——
     * 一次自动重试的正文生成会产出第二份不同的正文，并且收两笔钱。
     */
    @Test
    void neverRetriesAFailureThatIsNotAboutTheToken() {
        responseStatus.set(502);
        responseBody.set(errorBody("AI_OUTPUT_INVALID", "结构校验未通过"));

        assertThatThrownBy(this::callOutline)
                .isInstanceOf(AiGatewayException.class)
                .satisfies(failure -> assertThat(
                        ((BusinessException) failure).getErrorCode()).isEqualTo("AI_OUTPUT_INVALID"));

        assertThat(requestCount.get()).isEqualTo(1);
        assertThat(minter.invalidated).isEmpty();
    }

    /** 本来就没有票时不重铸——没有票可以作废，重来一次只是白跑。 */
    @Test
    void doesNotRetryWhenThereWasNoTokenToBeginWith() {
        minter.configured = false;
        client = newClient(2);
        responseStatus.set(502);
        responseBody.set(errorBody("AI_ATLAS_TOKEN_REJECTED", "token rejected"));

        assertThatThrownBy(this::callOutline).isInstanceOf(AiGatewayException.class);

        assertThat(requestCount.get()).isEqualTo(1);
    }

    // ── 出站请求带了什么 ────────────────────────────────────────────────────

    @Test
    void carriesTheTaskIdAndTheMintedTokenOnEveryCall() {
        TaskContext.run("task-77", () -> {
            callOutline();
            return null;
        });

        Headers headers = seenHeaders.get(0);
        assertThat(headers.getFirst("X-Vxture-Task-Id")).isEqualTo("task-77");
        assertThat(headers.getFirst("X-Vxture-S2S-Token")).isEqualTo("minted-token");
        assertThat(headers.getFirst("X-Vxture-Tenant-Id"))
                .as("租户取自票里的 claim，被调方据此告诉 Atlas 记在谁头上")
                .isEqualTo("tenant-uuid");
        assertThat(headers.getFirst("X-Internal-Token")).isEqualTo("internal-token");
    }

    /**
     * 没有 task_id 时<strong>不发这个头</strong>。
     *
     * <p>发一个空值会让被调方存下一个空字符串键，而那比没有更难查——
     * 一个空键看起来像是「有人送了聚合键」。
     */
    @Test
    void omitsTheTaskHeaderRatherThanSendingAnEmptyOne() {
        callOutline();

        assertThat(seenHeaders.get(0).getFirst("X-Vxture-Task-Id")).isNull();
    }

    // ── 状态码映射 ──────────────────────────────────────────────────────────

    /**
     * 503 与 504 原样透出，其余一律折成 502。
     *
     * <p>这不是美观问题：上游按状态码决定「等一会儿再来」还是「这条别再试了」。
     * 把一个 429 透传上去会让前端按限流处理，而真相可能是模型输出不合法。
     */
    @Test
    void preservesOnlyTheTwoStatusesThatMeanTryAgainLater() {
        assertThat(statusFor(503)).isEqualTo(503);
        assertThat(statusFor(504)).isEqualTo(504);
        assertThat(statusFor(500)).isEqualTo(502);
        assertThat(statusFor(429)).isEqualTo(502);
        assertThat(statusFor(400)).isEqualTo(502);
    }

    // ── 超时与不可达是两件事 ────────────────────────────────────────────────

    /**
     * 读超时报 {@code AI_GATEWAY_TIMEOUT} / 504，并把已等待的秒数说出来。
     *
     * <p>把它折成「服务不可用」会让用户去查服务状态，而真相是这一阶段本来就慢。
     */
    @Test
    void tellsATimeoutApartFromAnUnreachableService() {
        client = newClient(1);
        handlerDelayMillis.set(3_000L);

        assertThatThrownBy(this::callOutline)
                .isInstanceOf(AiGatewayException.class)
                .satisfies(failure -> {
                    BusinessException business = (BusinessException) failure;
                    assertThat(business.getErrorCode()).isEqualTo("AI_GATEWAY_TIMEOUT");
                    assertThat(business.getHttpStatus()).isEqualTo(504);
                    assertThat(business.getMessage())
                            .as("说清楚等了多久，用户才知道是慢还是坏")
                            .contains("已等待约").contains("秒");
                });
    }

    @Test
    void reportsAnUnreachableServiceAsUnavailableNotAsATimeout() {
        AiServiceHttpClient offline = new AiServiceHttpClient(
                RestClient.builder(), new AtlasCallCredentials(minter),
                "http://127.0.0.1:1", "internal-token", 2);

        assertThatThrownBy(() -> offline.planOutline(outlineRequest()))
                .isInstanceOf(BusinessException.class)
                .satisfies(failure -> assertThat(
                        ((BusinessException) failure).getErrorCode())
                        .isEqualTo("AI_GATEWAY_UNAVAILABLE"));
    }

    // ── 错误信封的解析 ──────────────────────────────────────────────────────

    /** 被调方的诊断要原样带上：它们是 bid_ai_run 里唯一能回答「模型当时怎么了」的东西。 */
    @Test
    void carriesTheCalleeDiagnosticsIntoTheException() {
        responseStatus.set(502);
        responseBody.set("""
                {"code":"AI_OUTPUT_INVALID","message":"结构校验未通过","retryable":false,
                 "details":{"objectName":"技术标目录","validationErrors":["nodes: too few items"],
                 "finishReason":"length","responseLength":1234,"responseHash":"abc",
                 "attempts":2,"inputTokens":100,"outputTokens":20,
                 "stage":"outline_skeleton_planning","elapsedMillis":8000}}
                """);

        assertThatThrownBy(this::callOutline).isInstanceOfSatisfying(
                AiGatewayException.class, failure -> {
                    assertThat(failure.getFinishReason()).isEqualTo("length");
                    assertThat(failure.getResponseLength()).isEqualTo(1234);
                    assertThat(failure.getAttempts()).isEqualTo(2);
                    assertThat(failure.getStage()).isEqualTo("outline_skeleton_planning");
                    assertThat(failure.getElapsedMillis()).isEqualTo(8000L);
                    assertThat(failure.getMessage())
                            .as("对象名和第一条校验错误进用户消息，否则「未通过校验」等于没说")
                            .contains("技术标目录").contains("too few items");
                });
    }

    /**
     * 读不懂的错误体也要给出一个<strong>可分支的码</strong>。
     *
     * <p>代理页面、被截断的响应都会走到这里。给一个通用码而不是抛解析异常：
     * 后者会把「被调方失败了」变成「我们自己坏了」。
     */
    @Test
    void fallsBackToAUsableCodeWhenTheErrorBodyIsNotJson() {
        responseStatus.set(502);
        responseBody.set("<html>bad gateway</html>");

        assertThatThrownBy(this::callOutline).isInstanceOfSatisfying(
                AiGatewayException.class, failure ->
                        assertThat(failure.getErrorCode()).isEqualTo("AI_PROVIDER_ERROR"));
    }

    /** 旧的 {"detail": …} 形状仍读得懂：新旧版本交替发布的窗口里不能再丢一次诊断。 */
    @Test
    void stillReadsTheLegacyDetailEnvelope() {
        responseStatus.set(502);
        responseBody.set("""
                {"detail":{"code":"AI_OUTPUT_INVALID","message":"结构校验未通过",
                 "objectName":"技术标目录","validationErrors":["nodes: too few items"],
                 "finishReason":"length","responseLength":1234,"responseHash":"abc",
                 "attempts":2,"inputTokens":100,"outputTokens":20,
                 "stage":"outline_skeleton_planning","elapsedMillis":8000}}
                """);

        assertThatThrownBy(this::callOutline).isInstanceOfSatisfying(
                AiGatewayException.class, failure -> {
                    assertThat(failure.getFinishReason()).isEqualTo("length");
                    assertThat(failure.getResponseLength()).isEqualTo(1234);
                    assertThat(failure.getAttempts()).isEqualTo(2);
                    assertThat(failure.getStage()).isEqualTo("outline_skeleton_planning");
                    assertThat(failure.getElapsedMillis()).isEqualTo(8000L);
                    assertThat(failure.getMessage())
                            .as("对象名和第一条校验错误进用户消息，否则「未通过校验」等于没说")
                            .contains("技术标目录").contains("too few items");
                });
    }

    /**
     * 被调方（Atlas）的原码要进到异常消息里：这是界面与 bid_ai_run_attempt 上唯一能说明
     * 「为什么失败」的东西。此前 Java 读错了封套形状，每一次失败都只剩「AI 工作流执行失败」。
     */
    @Test
    void surfacesTheCallersOwnCodeAndTheAtlasCode() {
        responseStatus.set(502);
        responseBody.set("""
                {"code":"AI_INPUT_TOO_LARGE","message":"输入超出上限（CONTEXT_LENGTH_EXCEEDED）：too big",
                 "retryable":false,"details":{"stage":"project_overview_source_selection",
                 "atlasCode":"CONTEXT_LENGTH_EXCEEDED","attempts":1,"elapsedMillis":40}}
                """);

        assertThatThrownBy(this::callOutline).isInstanceOfSatisfying(
                AiGatewayException.class, failure -> {
                    assertThat(failure.getErrorCode()).isEqualTo("AI_INPUT_TOO_LARGE");
                    assertThat(failure.getMessage()).contains("CONTEXT_LENGTH_EXCEEDED");
                    assertThat(failure.getStage()).isEqualTo("project_overview_source_selection");
                });
    }

    /**
     * 非 JSON 的错误体里如果出现了 {@code AI_OUTPUT_INVALID}，按它归类。
     *
     * <p>这是一处子串匹配的兜底，值得钉住：它承担的是「被调方在返回结构化信封
     * 之前就崩了」那一档，而结构校验失败是那一档里唯一需要被上游区别对待的
     * ——Temporal 把它列为可重试。
     */
    @Test
    void recognisesAStructuralFailureEvenInAnUnparseableBody() {
        responseStatus.set(502);
        responseBody.set("Internal Server Error: AI_OUTPUT_INVALID at line 3");

        assertThatThrownBy(this::callOutline).isInstanceOfSatisfying(
                AiGatewayException.class, failure ->
                        assertThat(failure.getErrorCode()).isEqualTo("AI_OUTPUT_INVALID"));
    }

    /** 被调方 200 却没给 data 对象时，报结构失败而不是抛空指针。 */
    @Test
    void refusesA200ThatCarriesNoData() {
        responseBody.set("{\"diagnostics\":{}}");

        assertThatThrownBy(this::callOutline)
                .isInstanceOf(BusinessException.class)
                .satisfies(failure -> assertThat(
                        ((BusinessException) failure).getErrorCode()).isEqualTo("AI_OUTPUT_INVALID"));
    }

    // ── 辅助 ────────────────────────────────────────────────────────────────

    private int statusFor(int upstreamStatus) {
        requestCount.set(0);
        responseStatus.set(upstreamStatus);
        responseBody.set(errorBody("AI_PROVIDER_ERROR", "boom"));
        try {
            callOutline();
            throw new AssertionError("expected a failure for HTTP " + upstreamStatus);
        } catch (BusinessException failure) {
            return failure.getHttpStatus();
        }
    }

    private TenderAiGateway.OutlinePlan callOutline() {
        return PlatformCallerContext.run(
                new TenantScope("org-1", "ws-1"), null,
                () -> client.planOutline(outlineRequest()).data());
    }

    private AiServiceHttpClient newClient(long timeoutSeconds) {
        return new AiServiceHttpClient(
                RestClient.builder(), new AtlasCallCredentials(minter),
                "http://127.0.0.1:" + server.getAddress().getPort(),
                "internal-token", timeoutSeconds);
    }

    private static TenderAiGateway.OutlineRequest outlineRequest() {
        return new TenderAiGateway.OutlineRequest(
                "trace-1", "测试技术标", 80, "BLIND", List.of(), List.of());
    }

    private static String okBody() {
        return """
                {"data":{"nodes":[],"coverage":[],
                 "dictionary":{"metrics":[],"terms":[],"fixedFacts":[]},"warnings":[]},
                 "diagnostics":{"finishReason":"stop","responseLength":10,"responseHash":"h",
                 "inputTokens":1,"outputTokens":1,"reasoningTokens":null,
                 "cachedInputTokens":null,"attempts":1}}
                """;
    }

    private static String errorBody(String code, String message) {
        return "{\"code\":\"" + code + "\",\"message\":\"" + message + "\",\"retryable\":false}";
    }

    /** 记下铸了几次、作废了哪几张。 */
    private static final class RecordingMinter implements S2STokenMinter {
        private final List<S2SToken> invalidated = new ArrayList<>();
        private int minted;
        private boolean configured = true;

        @Override
        public S2SToken onBehalfOf(String audience, String userAccessToken) {
            return mint(audience);
        }

        @Override
        public S2SToken forService(String audience, TenantScope tenant) {
            return mint(audience);
        }

        @Override
        public S2SToken forWorkspace(String audience, String workspaceId) {
            return mint(audience);
        }

        private S2SToken mint(String audience) {
            minted++;
            return new S2SToken("minted-token", audience, S2SToken.Mode.SERVICE,
                    null, "tenant-uuid", LocalDateTime.now().plusMinutes(5));
        }

        @Override
        public void invalidate(S2SToken token) {
            invalidated.add(token);
        }

        @Override
        public boolean isConfigured() {
            return configured;
        }
    }
}
