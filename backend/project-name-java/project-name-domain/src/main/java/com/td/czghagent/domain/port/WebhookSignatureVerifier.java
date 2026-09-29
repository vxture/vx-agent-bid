// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-09
package com.td.czghagent.domain.port;

/**
 * Webhook 验签口（C3 下发）。
 *
 * <p>做成端口而不是直接在接收端调工具类，是因为这里有一条<strong>必须能被
 * 单独验证</strong>的判断：未配置密钥时一律拒绝。把它埋在控制器里，
 * 意味着要验它就得起一整个 Web 上下文——于是它多半不会被验。
 */
public interface WebhookSignatureVerifier {

    /**
     * 验签。
     *
     * @param rawBody         <strong>原始请求字节</strong>。不能传解码后的字符串：
     *                        HMAC 算的是字节，而解码再编码会改写非 ASCII 内容
     * @param signatureHeader {@code X-Vxture-Signature} 头原文
     */
    boolean verify(byte[] rawBody, String signatureHeader);

    /** 是否配了任何密钥。未配置时 {@link #verify} 必须恒假。 */
    boolean isConfigured();

    /**
     * 自检：按平台的签法给一段合成报文签名，走一遍真实的 {@link #verify}，
     * 再把报文改一个字节——后者必须被拒。
     *
     * <p>证明的是解析、时间窗与常量时间比较都在工作，不需要等一次真实投递。
     * 未配置时恒假。
     */
    boolean selfTest();
}
