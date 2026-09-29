// GENERATED_BY_AI
// MODEL: claude-opus-5
// DATE: 2026-09-09
package com.td.czghagent.infrastructure.platform;

import com.td.czghagent.domain.port.WebhookSignatureVerifier;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Clock;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;

/**
 * Provisioning webhook 的验签。
 *
 * <p>头 {@code X-Vxture-Signature: t=<unix秒>,v1=<hex>[,v1=<hex>]}，
 * 签名对象是 {@code "{t}." + 原始请求字节}，{@code v1 = hex(HMAC_SHA256(secret, payload))}。
 *
 * <p><strong>必须对原始字节验签，绝不能反序列化后再拼回来。</strong>
 * 在 Java 里这条有个格外容易踩的形式：用 {@code @RequestBody String} 接收，
 * Spring 会按请求声明的字符集解码，而缺省字符集<em>不一定</em>是 UTF-8；
 * 再 {@code getBytes(UTF_8)} 拿去算 HMAC，任何非 ASCII 字节都已经被改写过了。
 * 表现是：全英文的 payload 一切正常，直到某个租户名里出现一个中文字符，
 * 那一条投递开始永远验签失败并被平台无限重试——而没有任何日志说得清为什么。
 * 所以这里只接受 {@code byte[]}。
 */
public final class HmacWebhookSignatureVerifier implements WebhookSignatureVerifier {

    /**
     * 时间戳容差。
     *
     * <p>防重放。放宽等于延长一个被截获的请求可被重放的窗口；
     * 收紧则会让两侧时钟的正常漂移变成随机的验签失败。
     */
    private static final long TOLERANCE_SECONDS = 300;

    private static final String ALGORITHM = "HmacSHA256";

    private final List<String> secrets;
    private final Clock clock;

    /**
     * @param current 当前密钥
     * @param next    轮换中的下一把，可为空
     * @param clock   时间源；容差窗口要能在测试里被钉住，否则那几条断言
     *                只在「现在」成立，明天跑就是另一回事
     */
    public HmacWebhookSignatureVerifier(String current, String next, Clock clock) {
        List<String> configured = new ArrayList<>();
        if (current != null && !current.isBlank()) {
            configured.add(current);
        }
        if (next != null && !next.isBlank()) {
            configured.add(next);
        }
        this.secrets = List.copyOf(configured);
        this.clock = clock;
    }

    @Override
    public boolean isConfigured() {
        return !secrets.isEmpty();
    }

    /**
     * 验签。
     *
     * <p>没有配置任何密钥时<strong>一律拒绝</strong>。放行是最糟的兜底：
     * 一个漏配了密钥的部署会变成任何人都能往里发开通事件的开放端点，
     * 而它看起来完全正常。
     */
    @Override
    public boolean verify(byte[] rawBody, String signatureHeader) {
        long nowSeconds = clock.instant().getEpochSecond();
        if (!isConfigured() || rawBody == null) {
            return false;
        }
        Signature signature = parse(signatureHeader);
        if (signature == null) {
            return false;
        }
        if (Math.abs(nowSeconds - signature.timestamp()) > TOLERANCE_SECONDS) {
            return false;
        }
        byte[] payload = payload(signature.timestamp(), rawBody);
        // 轮换期间平台可能用旧的也可能用新的签，任一命中即通过。
        // 少了这一条，轮换那一刻所有投递会同时开始失败。
        for (String secret : secrets) {
            String expected = hmacHex(secret, payload);
            for (String candidate : signature.values()) {
                if (constantTimeEquals(candidate, expected)) {
                    return true;
                }
            }
        }
        return false;
    }

    /** {@code "{t}." + 原始字节}，在字节层面拼接——原始字节一路不解码。 */
    @Override
    public boolean selfTest() {
        if (!isConfigured()) {
            return false;
        }
        long timestamp = clock.instant().getEpochSecond();
        byte[] body = "{\"probe\":true}".getBytes(StandardCharsets.UTF_8);
        String header = "t=" + timestamp + ",v1=" + hmacHex(secrets.get(0), payload(timestamp, body));
        byte[] tampered = "{\"probe\":true} ".getBytes(StandardCharsets.UTF_8);
        return verify(body, header) && !verify(tampered, header);
    }

    private static byte[] payload(long timestamp, byte[] rawBody) {
        byte[] prefix = (timestamp + ".").getBytes(StandardCharsets.US_ASCII);
        byte[] payload = new byte[prefix.length + rawBody.length];
        System.arraycopy(prefix, 0, payload, 0, prefix.length);
        System.arraycopy(rawBody, 0, payload, prefix.length, rawBody.length);
        return payload;
    }

    private static String hmacHex(String secret, byte[] payload) {
        try {
            Mac mac = Mac.getInstance(ALGORITHM);
            mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), ALGORITHM));
            return HexFormat.of().formatHex(mac.doFinal(payload));
        } catch (java.security.GeneralSecurityException impossible) {
            throw new IllegalStateException("HmacSHA256 unavailable", impossible);
        }
    }

    /**
     * 定长比较。
     *
     * <p>用 {@code equals} 会在第一个不同的字符处返回，于是比较耗时泄露了
     * 前缀匹配了多少位——攻击者可以据此逐字节把签名试出来。这不是理论问题：
     * 签名是攻击者可以任意重发的东西，他有无限次测量机会。
     */
    private static boolean constantTimeEquals(String candidate, String expected) {
        // 十六进制大小写不携带任何信息，却足以让一条本来正确的签名被拒。
        // 归一化的是<strong>调用方送来的那一串</strong>，安全性不受影响。
        return MessageDigest.isEqual(
                candidate.toLowerCase(java.util.Locale.ROOT)
                        .getBytes(StandardCharsets.US_ASCII),
                expected.getBytes(StandardCharsets.US_ASCII));
    }

    static Signature parse(String header) {
        if (header == null || header.isBlank()) {
            return null;
        }
        Long timestamp = null;
        List<String> values = new ArrayList<>();
        for (String part : header.split(",")) {
            int equals = part.indexOf('=');
            if (equals < 0) {
                continue;
            }
            String key = part.substring(0, equals).trim();
            String value = part.substring(equals + 1).trim();
            if ("t".equals(key)) {
                try {
                    timestamp = Long.parseLong(value);
                } catch (NumberFormatException malformed) {
                    return null;
                }
            } else if ("v1".equals(key)) {
                values.add(value);
            }
            // 其它键忽略：平台以后加 v2 时，一个只认 v1 的产品应该继续工作，
            // 而不是因为看到不认识的键就整个拒绝。
        }
        if (timestamp == null || values.isEmpty()) {
            return null;
        }
        return new Signature(timestamp, List.copyOf(values));
    }

    record Signature(long timestamp, List<String> values) {
    }
}
