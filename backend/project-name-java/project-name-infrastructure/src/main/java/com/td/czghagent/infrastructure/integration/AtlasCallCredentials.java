// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-09
package com.td.czghagent.infrastructure.integration;

import com.td.czghagent.domain.exception.BusinessException;
import com.td.czghagent.domain.model.PlatformCallerContext;
import com.td.czghagent.domain.model.S2SToken;
import com.td.czghagent.domain.model.TenantScope;
import com.td.czghagent.domain.port.S2STokenMinter;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.stereotype.Component;

/**
 * 给出站 AI 调用铸一张 {@code aud=atlas} 的 S2S 票。
 *
 * <p><strong>票在这里铸，不在 Python 侧。</strong>铸票凭据就是本产品的 OIDC client 对；
 * 把那对凭据复制进 Python 服务意味着产品身份凭据有了第二份副本、两个轮换点，
 * 而多出来的那份跟第一份一样能冒充整个产品。Python 只负责转呈。
 *
 * <p>票只活 300 秒且不可刷新——所以也不存在「配一个长期 ATLAS_TOKEN」这条路，
 * 粘进 .env 的那张五分钟后就过期，只够通过一次手工冒烟。
 */
@Component
public class AtlasCallCredentials {

    private static final Logger LOGGER = LoggerFactory.getLogger(AtlasCallCredentials.class);

    /** Atlas 的受众标识。它同时决定了票上的 scope（{@code tool:atlas}）。 */
    public static final String AUDIENCE = "atlas";

    /** 与 Python 中间件、Atlas 客户端三处保持同名。 */
    public static final String TOKEN_HEADER = "X-Vxture-S2S-Token";
    public static final String TENANT_HEADER = "X-Vxture-Tenant-Id";

    private final S2STokenMinter minter;

    public AtlasCallCredentials(S2STokenMinter minter) {
        this.minter = minter;
    }

    /**
     * 铸一张票；铸不出时返回 null。
     *
     * <p>铸不出是<strong>正常状态</strong>而不是错误：平台凭据还没配、或者当前用户
     * 是本地口令登录因而没有平台身份。返回 null 让下游显式拒绝，
     * 比在这里抛异常好——抛出会让本地开发根本跑不起来，而本地本来就该能跑。
     */
    public S2SToken mint() {
        try {
            return mintOrExplain();
        } catch (BusinessException expected) {
            if (NOT_CONFIGURED.equals(expected.getErrorCode())
                    || NO_PLATFORM_TENANT.equals(expected.getErrorCode())) {
                return null;
            }
            // 铸不出票就让这次调用走没有票的路径，由下游给出明确拒绝。
            // 在这里抛会把一个凭据问题伪装成模型调用失败。
            LOGGER.warn("Minting an Atlas S2S token failed", expected);
            return null;
        } catch (RuntimeException exception) {
            LOGGER.warn("Minting an Atlas S2S token failed", exception);
            return null;
        }
    }

    /** 平台凭据没配，铸不了任何票。 */
    public static final String NOT_CONFIGURED = "S2S_NOT_CONFIGURED";

    /** 没有用户票，而当前租户是过渡值或缺失，service 模式也铸不了。 */
    public static final String NO_PLATFORM_TENANT = "S2S_NO_PLATFORM_TENANT";

    /**
     * 与 {@link #mint()} 同一条判定，但铸不出时<strong>抛出原因</strong>而不是返回 null。
     *
     * <p>系统验证用它：业务路径把失败吞成 null 是对的（下游会给出明确拒绝），
     * 但诊断页要看到的恰恰是被吞掉的那一句——换票被拒的码、缺的是哪一项。
     */
    public S2SToken mintOrExplain() {
        if (!minter.isConfigured()) {
            throw new BusinessException(NOT_CONFIGURED, "平台凭据（OIDC client）未配置", 503, false, null);
        }
        // 有用户票就用 OBO：平台从 subject_token 解出 org/workspace/user，
        // 调用方无从声称一个它没有会话的工作空间，而 Atlas 的归因也就落到人头上。
        // 退回 service 模式不是等价的——那样 Atlas 的审计里只有产品，没有终端用户，
        // 而那要等到有人按用户查一次调用链时才发现。
        String userToken = PlatformCallerContext.userAccessToken();
        if (userToken != null && !userToken.isBlank()) {
            return minter.onBehalfOf(AUDIENCE, userToken);
        }
        TenantScope tenant = PlatformCallerContext.tenant();
        if (tenant == null || tenant.usesLocalPlaceholder()) {
            // 过渡租户铸不出票：平台会校验本产品是否真的覆盖该工作空间，
            // 而 local:<用户id> 在平台那边根本不存在。
            // 这不是可以绕过去的——它说明这条链路在切到平台身份之前无法走通。
            throw new BusinessException(NO_PLATFORM_TENANT,
                    "没有用户票，且当前租户不是平台工作空间", 503, false, null);
        }
        return minter.forService(AUDIENCE, tenant);
    }

    public void invalidate(S2SToken token) {
        if (token != null) {
            minter.invalidate(token);
        }
    }

    /**
     * 把票挂到出站请求上。
     *
     * <p>{@code tenantId} 取自票里的 claim，<strong>不是</strong>产品码，也不是调用方自己
     * 拼的值。送产品码看起来能跑——Atlas 只校验它非空，而产品授权那条路径在租户断言
     * 之前就返回了；一旦授权缺失或 endpoint 被改指，控制流落到 UUID 断言上，
     * 失败表现为 {@code 400 INVALID_TENANT_ID}，读起来像请求体写错了。
     * 非 UUID 还会让 Atlas 的请求日志写进 NULL，本产品的流量就从每一张租户汇总表里
     * 消失，且全程没有任何报错。
     */
    public static void apply(HttpHeaders headers, S2SToken token) {
        if (token == null) {
            return;
        }
        headers.set(TOKEN_HEADER, token.value());
        if (token.tenantId() != null && !token.tenantId().isBlank()) {
            headers.set(TENANT_HEADER, token.tenantId());
        }
    }
}
