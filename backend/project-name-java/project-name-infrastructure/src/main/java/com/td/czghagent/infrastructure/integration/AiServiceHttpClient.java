// GENERATED_BY_AI
// MODEL: gpt-5
// DATE: 2026-08-02
package com.td.czghagent.infrastructure.integration;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.td.czghagent.domain.exception.AiGatewayException;
import com.td.czghagent.domain.exception.BusinessException;
import com.td.czghagent.domain.model.ParsedDocument;
import com.td.czghagent.domain.model.S2SToken;
import com.td.czghagent.domain.model.StoredFile;
import com.td.czghagent.domain.port.DocumentParser;
import com.td.czghagent.domain.port.TenderAiGateway;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;

import java.net.SocketTimeoutException;
import java.net.http.HttpTimeoutException;
import java.time.Duration;

@Component
public class AiServiceHttpClient implements DocumentParser, TenderAiGateway {

    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();
    /**
     * Atlas 拒票的错误码，与 Python 侧同名。
     *
     * <p>按<strong>码</strong>分支而不是按状态码：一张过期的票和一次模型故障
     * 都可能以 502 到达，而只有前者该重铸。
     */
    private static final String ATLAS_TOKEN_REJECTED = "AI_ATLAS_TOKEN_REJECTED";

    private final RestClient client;
    private final String internalToken;
    private final AtlasCallCredentials atlasCredentials;

    public AiServiceHttpClient(
            RestClient.Builder builder,
            AtlasCallCredentials atlasCredentials,
            @Value("${app.ai.base-url}") String baseUrl,
            @Value("${app.ai.internal-token}") String internalToken,
            @Value("${app.ai.timeout-seconds:120}") long timeoutSeconds
    ) {
        this.atlasCredentials = atlasCredentials;
        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(Duration.ofSeconds(Math.min(timeoutSeconds, 30)));
        requestFactory.setReadTimeout(Duration.ofSeconds(timeoutSeconds));
        this.client = builder.requestFactory(requestFactory).baseUrl(baseUrl).build();
        this.internalToken = internalToken;
    }

    @Override
    public ParsedDocument parse(String documentId, StoredFile file) {
        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("documentId", documentId);
        body.add("file", filePart(file));
        try {
            ParsedDocument result = client.post()
                    .uri("/internal/parse")
                    .header("X-Internal-Token", internalToken)
                    .headers(TaskHeaders::apply)
                    .contentType(MediaType.MULTIPART_FORM_DATA)
                    .body(body)
                    .retrieve()
                    .body(ParsedDocument.class);
            if (result == null) {
                throw new BusinessException("PARSER_EMPTY_RESPONSE", "文件解析服务未返回结果", 502);
            }
            return result;
        } catch (RestClientResponseException exception) {
            throw new BusinessException(
                    "PARSER_REJECTED",
                    exception.getStatusCode().is4xxClientError()
                            ? "文件内容无法解析，请检查格式" : "文件解析服务处理失败",
                    exception.getStatusCode().is4xxClientError() ? 422 : 502
            );
        } catch (RestClientException exception) {
            throw new BusinessException("PARSER_UNAVAILABLE", "文件解析服务暂不可用", 502);
        }
    }

    @Override
    public Interpretation interpret(InterpretationRequest request) {
        ProjectOverview overview = extractProjectOverview(request).data();
        TechnicalScoring scoring = extractTechnicalScoring(request).data();
        return new Interpretation(
                overview.projectOverview(), scoring.technicalScoringRequirements());
    }

    @Override
    public AiResponse<ProjectOverview> extractProjectOverview(InterpretationRequest request) {
        return postAi("/internal/tender/interpretation/project-overview",
                request, ProjectOverview.class);
    }

    @Override
    public AiResponse<TechnicalScoring> extractTechnicalScoring(InterpretationRequest request) {
        return postAi("/internal/tender/interpretation/technical-scoring",
                request, TechnicalScoring.class);
    }

    @Override
    public AiResponse<OutlinePlan> planOutline(OutlineRequest request) {
        return postAi("/internal/tender/outline", request, OutlinePlan.class);
    }

    @Override
    public AiResponse<BidStrategy> planOutlineStrategy(OutlineRequest request) {
        return postAi("/internal/tender/outline/strategy", request, BidStrategy.class);
    }

    @Override
    public AiResponse<OutlineSkeletonPlan> planOutlineSkeleton(OutlineSkeletonRequest request) {
        return postAi("/internal/tender/outline/skeleton", request, OutlineSkeletonPlan.class);
    }

    @Override
    public AiResponse<OutlineExpansion> expandOutline(OutlineExpansionRequest request) {
        return postAi("/internal/tender/outline/expansion", request, OutlineExpansion.class);
    }

    @Override
    public OutlinePlan assembleOutline(OutlineAssemblyRequest request) {
        return postObject("/internal/tender/outline/assemble", request, OutlinePlan.class);
    }

    @Override
    public AiResponse<BranchBlueprint> planBranchBlueprint(BranchBlueprintRequest request) {
        return postAi("/internal/tender/chapter/blueprint", request, BranchBlueprint.class);
    }

    @Override
    public AiResponse<ChapterDraft> draftChapter(ChapterDraftRequest request) {
        return postAi("/internal/tender/chapter", request, ChapterDraft.class);
    }

    @Override
    public AiResponse<RevisionCandidate> revise(RevisionRequest request) {
        return postAi("/internal/tender/revision", request, RevisionCandidate.class);
    }

    @Override
    public AiResponse<Review> review(ReviewRequest request) {
        return postAi("/internal/tender/review", request, Review.class);
    }

    /**
     * 系统验证：带这张票读 Atlas 的模型清单（不计量）。
     *
     * <p>票由调用方显式传入而不是在这里现铸：{@link AtlasCallCredentials#mint()} 把铸票失败
     * 吞成 null，那正是业务路径该有的行为，却会让诊断页只看到「没带票」而看不到平台为什么拒。
     */
    public JsonNode atlasModels(S2SToken token) {
        return atlasDiagnostic(client.get().uri("/internal/atlas/models"), token, "/internal/atlas/models");
    }

    /** 系统验证：带票读 Atlas 契约指纹，与本产品钉住的值比对（不计量）。 */
    public JsonNode atlasContract(S2SToken token) {
        return atlasDiagnostic(client.get().uri("/internal/atlas/contract"), token, "/internal/atlas/contract");
    }

    /** 系统验证：带票读 Atlas 路由容量，核对本产品实际路由（不计量）。 */
    public JsonNode atlasRoutes(S2SToken token) {
        return atlasDiagnostic(client.get().uri("/internal/atlas/routes"), token, "/internal/atlas/routes");
    }

    /** 系统验证：对本产品会调用的每条 Atlas 路由各打一次最短调用。<strong>会花钱。</strong> */
    public JsonNode atlasProbe(S2SToken token) {
        return atlasDiagnostic(client.post().uri("/internal/atlas/probe")
                .contentType(MediaType.APPLICATION_JSON)
                .body(java.util.Map.of()), token, "/internal/atlas/probe");
    }

    private JsonNode atlasDiagnostic(RestClient.RequestHeadersSpec<?> request, S2SToken token,
                                     String path) {
        long started = System.nanoTime();
        try {
            JsonNode body = request
                    .header("X-Internal-Token", internalToken)
                    .headers(TaskHeaders::apply)
                    .headers(headers -> AtlasCallCredentials.apply(headers, token))
                    .retrieve()
                    .body(JsonNode.class);
            if (body == null) {
                throw new BusinessException("AI_OUTPUT_INVALID", "AI 服务未返回结果", 502);
            }
            return body;
        } catch (RestClientResponseException exception) {
            throw responseFailure(exception, path, started);
        } catch (RestClientException exception) {
            throw transportFailure(exception, path, started);
        }
    }

    /**
     * 发一次 AI 调用，必要时重铸一次票再来。
     *
     * <p>只重试<strong>拒票</strong>这一种失败，且只重一次。其余失败一概不重试：
     * 每一次调用都会被计量和审计，而最值得重试的那些操作恰好都不是幂等的——
     * 一次自动重试的正文生成会产出第二份不同的正文，并且收两笔钱。
     */
    private <T> AiResponse<T> postAi(String path, Object body, Class<T> responseType) {
        S2SToken token = atlasCredentials.mint();
        try {
            return postAiOnce(path, body, responseType, token);
        } catch (AiGatewayException failure) {
            if (!ATLAS_TOKEN_REJECTED.equals(failure.getErrorCode()) || token == null) {
                throw failure;
            }
            // 被调方说这张票不认。作废缓存里的那张再铸一张——不作废的话，
            // 接下来整个缓存有效期内每一次调用都会 401。
            atlasCredentials.invalidate(token);
            S2SToken reminted = atlasCredentials.mint();
            if (reminted == null) {
                throw failure;
            }
            return postAiOnce(path, body, responseType, reminted);
        }
    }

    private <T> AiResponse<T> postAiOnce(String path, Object body, Class<T> responseType,
                                         S2SToken token) {
        long started = System.nanoTime();
        try {
            JsonNode result = client.post()
                    .uri(path)
                    .header("X-Internal-Token", internalToken)
                    .headers(TaskHeaders::apply)
                    .headers(headers -> AtlasCallCredentials.apply(headers, token))
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body)
                    .retrieve()
                    .body(JsonNode.class);
            if (result == null || !result.path("data").isObject()) {
                throw new BusinessException("AI_OUTPUT_INVALID", "AI 服务未返回有效结果", 502);
            }
            T data = OBJECT_MAPPER.treeToValue(result.path("data"), responseType);
            AiDiagnostics diagnostics = OBJECT_MAPPER.treeToValue(
                    result.path("diagnostics"), AiDiagnostics.class);
            return new AiResponse<>(data, diagnostics);
        } catch (RestClientResponseException exception) {
            throw responseFailure(exception, path, started);
        } catch (RestClientException exception) {
            // 一并接住 ResourceAccessException（它是子类）。
            //
            // 曾经这里先接 ResourceAccessException 再兜 RestClientException，
            // 而 Spring 的 RestClient <b>把读超时包成普通的 RestClientException</b>
            // ——不是老 RestTemplate 那个 ResourceAccessException。于是超时分支
            // 从来没命中过：整个 AI_GATEWAY_TIMEOUT / 504 / 「已等待约 N 秒」
            // 对最常见的超时情形是死代码，用户收到的是「AI 网关暂不可用」。
            // 模型调用是本产品最慢的一环，超时正是它的常规失败形态。
            throw transportFailure(exception, path, started);
        } catch (Exception exception) {
            throw new BusinessException("AI_OUTPUT_INVALID", "AI 服务响应无法解析", 502);
        }
    }

    private <T> T postObject(String path, Object body, Class<T> responseType) {
        long started = System.nanoTime();
        try {
            T result = client.post().uri(path)
                    .header("X-Internal-Token", internalToken)
                    .headers(TaskHeaders::apply)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body).retrieve().body(responseType);
            if (result == null) {
                throw new BusinessException("AI_OUTPUT_INVALID", "AI 服务未返回有效结果", 502);
            }
            return result;
        } catch (RestClientResponseException exception) {
            throw responseFailure(exception, path, started);
        } catch (RestClientException exception) {
            // 一并接住 ResourceAccessException（它是子类）。
            //
            // 曾经这里先接 ResourceAccessException 再兜 RestClientException，
            // 而 Spring 的 RestClient <b>把读超时包成普通的 RestClientException</b>
            // ——不是老 RestTemplate 那个 ResourceAccessException。于是超时分支
            // 从来没命中过：整个 AI_GATEWAY_TIMEOUT / 504 / 「已等待约 N 秒」
            // 对最常见的超时情形是死代码，用户收到的是「AI 网关暂不可用」。
            // 模型调用是本产品最慢的一环，超时正是它的常规失败形态。
            throw transportFailure(exception, path, started);
        }
    }

    private AiGatewayException responseFailure(
            RestClientResponseException exception, String path, long started
    ) {
        AiError error = parseAiError(exception.getResponseBodyAsString());
        int upstreamStatus = exception.getStatusCode().value();
        int status = upstreamStatus == 503 || upstreamStatus == 504 ? upstreamStatus : 502;
        String stage = error.stage() == null ? stage(path) : error.stage();
        Long elapsed = error.elapsedMillis() == null ? elapsedMillis(started) : error.elapsedMillis();
        return new AiGatewayException(
                error.code(), userMessage(error, stage, elapsed), status, error.failureReason(),
                error.finishReason(), error.responseLength(), error.responseHash(),
                error.attempts(), error.inputTokens(), error.outputTokens(),
                error.reasoningTokens(), error.cachedInputTokens(), stage, elapsed);
    }

    private BusinessException transportFailure(
            RestClientException exception, String path, long started
    ) {
        if (isTimeout(exception)) {
            String stage = stage(path);
            long elapsed = elapsedMillis(started);
            return new AiGatewayException(
                    "AI_GATEWAY_TIMEOUT",
                    timeoutMessage("AI_GATEWAY_TIMEOUT", stage, elapsed), 504, "",
                    null, null, null, 1, null, null, null, null, stage, elapsed);
        }
        return new BusinessException("AI_GATEWAY_UNAVAILABLE", "AI 网关暂不可用", 502);
    }

    private String userMessage(AiError error, String stage, long elapsedMillis) {
        if ("AI_MODEL_TIMEOUT".equals(error.code())
                || "AI_GATEWAY_TIMEOUT".equals(error.code())) {
            return timeoutMessage(error.code(), stage, elapsedMillis);
        }
        return error.message();
    }

    private String timeoutMessage(String code, String stage, long elapsedMillis) {
        String failure = "AI_MODEL_TIMEOUT".equals(code) ? "模型执行超时" : "AI 网关响应超时";
        long elapsedSeconds = Math.max(1, (elapsedMillis + 999) / 1000);
        return stageLabel(stage) + failure + "（已等待约" + elapsedSeconds + "秒），请稍后重试";
    }

    private String stageLabel(String stage) {
        if (stage == null || stage.isBlank()) {
            return "AI 阶段";
        }
        if (stage.contains("bid_strategy") || stage.equals("outline_strategy")
                || stage.equals("strategy")) {
            return "目录策略";
        }
        if (stage.contains("outline_skeleton") || stage.equals("skeleton")) {
            return "目录骨架";
        }
        if (stage.contains("outline_expansion") || stage.contains("outline_branch_expansion")
                || stage.equals("expansion")) {
            return "三级目录扩展";
        }
        if (stage.contains("project_overview")) {
            return "项目概要解析";
        }
        if (stage.contains("technical_scoring")) {
            return "评分点解析";
        }
        if (stage.contains("chapter")) {
            return "章节生成";
        }
        if (stage.contains("review")) {
            return "标书审查";
        }
        if (stage.contains("revision")) {
            return "局部修订";
        }
        if (stage.equals("assemble")) {
            return "目录合并";
        }
        return "AI 阶段";
    }

    private String aiErrorMessage(String code) {
        return switch (code) {
            case "AI_MODEL_AUTH_FAILED" -> "AI 模型凭据校验失败";
            case "AI_PROVIDER_NOT_CONFIGURED" -> "AI 模型尚未完成配置";
            case "AI_OUTPUT_INVALID" -> "AI 返回内容未通过结构校验";
            case "AI_MODEL_TIMEOUT" -> "AI 模型阶段执行超时";
            case "AI_GATEWAY_TIMEOUT" -> "AI 网关响应超时";
            case "AI_INPUT_TOO_LARGE" -> "送给模型的内容超出上限，需要分段处理";
            case "AI_OUTPUT_BUDGET_EXHAUSTED" -> "模型的输出预算在给出结果前已用完";
            case "AI_ATLAS_NOT_ENTITLED" -> "本产品尚未被授权使用该模型路由";
            default -> "AI 工作流执行失败";
        };
    }

    /**
     * 读 Python 服务的失败封套。
     *
     * <p>现行形状是 X-1：顶层 {@code {code, message, retryable}}，诊断在 {@code details} 里。
     * 这里曾经只读 FastAPI 旧的 {@code {"detail": {…}}}，而 Python 早已不再发那个形状——
     * 两边都不报错，结果是每一次 AI 失败都落成 {@code AI_PROVIDER_ERROR}「AI 工作流执行失败」，
     * 阶段、耗时、校验错误与被调方原码一概丢失（2026-09-29 请求体超限要读 Atlas 进程日志才定位）。
     * 旧形状仍兼容读取，免得新旧版本交替发布的窗口里又丢一次。
     */
    private AiError parseAiError(String response) {
        try {
            JsonNode root = OBJECT_MAPPER.readTree(response);
            JsonNode legacy = root.path("detail");
            boolean current = root.path("code").isTextual();
            JsonNode detail = current ? root.path("details") : legacy;
            String code = (current ? root : legacy).path("code").asText("AI_PROVIDER_ERROR");
            String message = (current ? root : legacy).path("message").asText(aiErrorMessage(code));
            String atlasCode = detail.path("atlasCode").asText("");
            if (!atlasCode.isBlank() && !message.contains(atlasCode)) {
                message = message + "（" + atlasCode + "）";
            }
            String objectName = detail.path("objectName").asText("");
            JsonNode validationErrors = detail.path("validationErrors");
            String validation = validationErrors.isArray() && !validationErrors.isEmpty()
                    ? validationErrors.get(0).asText("") : "";
            String failureReason = validationErrors.isArray()
                    ? limit(OBJECT_MAPPER.writeValueAsString(validationErrors)) : "";
            String context = objectName.isBlank() ? "" : "（" + objectName + "）";
            if (!validation.isBlank()) {
                context += "：" + validation;
            }
            return new AiError(
                    code, limit(message + context), failureReason,
                    nullableText(detail, "finishReason"), nullableInt(detail, "responseLength"),
                    nullableText(detail, "responseHash"), nullableInt(detail, "attempts"),
                    nullableLong(detail, "inputTokens"), nullableLong(detail, "outputTokens"),
                    nullableLong(detail, "reasoningTokens"),
                    nullableLong(detail, "cachedInputTokens"),
                    nullableText(detail, "stage"), nullableLong(detail, "elapsedMillis"));
        } catch (Exception ignored) {
            String code = response.contains("AI_OUTPUT_INVALID")
                    ? "AI_OUTPUT_INVALID" : "AI_PROVIDER_ERROR";
            return new AiError(code, aiErrorMessage(code), "", null, null, null, null,
                    null, null, null, null, null, null);
        }
    }

    private String nullableText(JsonNode node, String field) {
        JsonNode value = node.path(field);
        return value.isTextual() && !value.asText().isBlank() ? value.asText() : null;
    }

    private Integer nullableInt(JsonNode node, String field) {
        JsonNode value = node.path(field);
        return value.isIntegralNumber() ? value.asInt() : null;
    }

    private Long nullableLong(JsonNode node, String field) {
        JsonNode value = node.path(field);
        return value.isIntegralNumber() ? value.asLong() : null;
    }

    private boolean isTimeout(Throwable exception) {
        Throwable current = exception;
        while (current != null) {
            if (current instanceof SocketTimeoutException
                    || current instanceof HttpTimeoutException) {
                return true;
            }
            current = current.getCause();
        }
        return false;
    }

    private String stage(String path) {
        int separator = path.lastIndexOf('/');
        return separator < 0 ? path : path.substring(separator + 1);
    }

    private long elapsedMillis(long started) {
        return (System.nanoTime() - started) / 1_000_000;
    }

    private String limit(String value) {
        return value.substring(0, Math.min(1000, value.length()));
    }

    private record AiError(
            String code, String message, String failureReason, String finishReason,
            Integer responseLength, String responseHash, Integer attempts,
            Long inputTokens, Long outputTokens, Long reasoningTokens, Long cachedInputTokens,
            String stage, Long elapsedMillis
    ) {
    }

    private HttpEntity<ByteArrayResource> filePart(StoredFile file) {
        ByteArrayResource resource = new ByteArrayResource(file.content()) {
            @Override
            public String getFilename() {
                return file.fileName();
            }
        };
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(mediaType(file.mediaType()));
        headers.setContentDispositionFormData("file", file.fileName());
        return new HttpEntity<>(resource, headers);
    }

    private MediaType mediaType(String value) {
        try {
            return MediaType.parseMediaType(value);
        } catch (IllegalArgumentException exception) {
            return MediaType.APPLICATION_OCTET_STREAM;
        }
    }
}
