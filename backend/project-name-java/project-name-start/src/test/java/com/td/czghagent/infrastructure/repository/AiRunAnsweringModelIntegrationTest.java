// GENERATED_BY_AI
// MODEL: claude-opus-5-5
// DATE: 2026-10-01
package com.td.czghagent.infrastructure.repository;

import com.td.czghagent.PostgresBackedTest;
import com.td.czghagent.domain.repository.BidProductionRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 运行记录的模型名是<strong>实际应答的那个</strong>，不是配置里的那个。
 *
 * <p>按 endpointCode 路由时，模型由运营挂在路由上、故障转移后还可能换成兜底模型；
 * 开始时写入的配置名（如 {@code AI_MODEL_FAST_NAME}）只是猜测。完成时用 Atlas 回显的
 * {@code modelCode} 覆盖它。以受限的服务角色连库：{@code model_name} 若没在
 * {@code 98_column_locks.sql} 授予 UPDATE，<strong>每一次</strong>模型调用的完成都会
 * {@code permission denied}——这条测试在那之前就会红。
 */
@SpringBootTest(properties = {
        "app.platform.usage-flush-enabled=false",
        "app.storage.root=${java.io.tmpdir}/ai-run-model-${random.uuid}"
})
class AiRunAnsweringModelIntegrationTest extends PostgresBackedTest {

    @Autowired
    private BidProductionRepository repository;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    private String bidId;

    @BeforeEach
    void insertBid() {
        bidId = UUID.randomUUID().toString();
        jdbcTemplate.update("""
                INSERT INTO bid_document(id, owner_id, org_id, workspace_id, code, writing_method, title)
                VALUES (?, 'owner-1', 'org-1', 'ws-1', ?, 'SCORING_CRITERIA', '模型回显')
                """, bidId, "SN-" + bidId.substring(0, 8));
    }

    private BidProductionRepository.AiRunHandle begin() {
        return repository.beginAiRun(new BidProductionRepository.AiRunStart(
                UUID.randomUUID().toString(), bidId, null, null, null, "OUTLINE_STRATEGY", "ATLAS",
                "deepseek-v4-pro", "outline-v2", "a".repeat(64), "idem-" + UUID.randomUUID()));
    }

    private String modelName(String runId) {
        return jdbcTemplate.queryForObject(
                "SELECT model_name FROM bid_ai_run WHERE id = ?::uuid", String.class, runId);
    }

    @Test
    void theModelAtlasReportsReplacesTheConfiguredGuess() {
        BidProductionRepository.AiRunHandle run = begin();

        repository.completeAiRun(run.id(), run.attemptId(), 1200L, 100L, 20L, 5L, 30L,
                "out-hash", "{}", "stop", 40, "resp-hash", 1, "doubao-seed-2-0-pro-260215");

        assertThat(modelName(run.id())).isEqualTo("doubao-seed-2-0-pro-260215");
    }

    @Test
    void withoutAnEchoTheConfiguredNameIsKept() {
        BidProductionRepository.AiRunHandle run = begin();

        repository.completeAiRun(run.id(), run.attemptId(), 1200L, 100L, 20L, null, null,
                "out-hash", "{}", "stop", 40, "resp-hash", 1, null);

        assertThat(modelName(run.id())).isEqualTo("deepseek-v4-pro");
    }
}
