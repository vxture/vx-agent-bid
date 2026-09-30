// GENERATED_BY_AI
// MODEL: claude-opus-5-5
// DATE: 2026-09-30
package com.td.czghagent.infrastructure.repository;

import com.td.czghagent.PostgresBackedTest;
import com.td.czghagent.domain.model.BidWorkspace;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 目录提示随任务落库，并原样读回。
 *
 * <p>以受限的服务角色连库（{@link PostgresBackedTest}）：{@code warnings_json} 若没在
 * {@code 98_column_locks.sql} 里授予 UPDATE，完成任务的那条 UPDATE 在这里就会
 * {@code permission denied}，而不是等到生产上目录生成完最后一步才失败。
 */
@SpringBootTest(properties = {
        "app.platform.usage-flush-enabled=false",
        "app.storage.root=${java.io.tmpdir}/outline-warnings-${random.uuid}"
})
class OutlineTaskWarningsIntegrationTest extends PostgresBackedTest {

    @Autowired
    private JdbcTemplate jdbcTemplate;

    private JdbcBidTaskExportPersistence tasks;
    private String bidId;

    @BeforeEach
    void insertBid() {
        tasks = new JdbcBidTaskExportPersistence(jdbcTemplate);
        bidId = UUID.randomUUID().toString();
        jdbcTemplate.update("""
                INSERT INTO bid_document(id, owner_id, org_id, workspace_id, code, writing_method, title)
                VALUES (?, 'owner-1', 'org-1', 'ws-1', ?, 'SCORING_CRITERIA', '提示落库')
                """, bidId, "SN-" + bidId.substring(0, 8));
    }

    @Test
    void warningsGivenAtCompletionAreReadBackWithTheTask() {
        String taskId = tasks.createOutlineTask(bidId);
        List<String> warnings = List.of(
                "二级目录共49个，多于按篇幅估算的上限21个（建议9至14个）：目录会偏细，每节篇幅偏短。",
                "三级小节共98个，按100页估算约42个：目录偏细，平均每节约1.0页。");

        assertThat(tasks.completeOutlineTask(taskId, warnings)).isTrue();

        BidWorkspace.OutlineTask task = tasks.latestOutlineTask(bidId);
        assertThat(task.status()).isEqualTo("SUCCEEDED");
        assertThat(task.warnings()).containsExactlyElementsOf(warnings);
    }

    @Test
    void aTaskWithoutWarningsReadsBackAsAnEmptyList() {
        String taskId = tasks.createOutlineTask(bidId);

        tasks.completeOutlineTask(taskId, List.of());

        assertThat(tasks.latestOutlineTask(bidId).warnings()).isEmpty();
        assertThat(jdbcTemplate.queryForObject(
                "SELECT warnings_json FROM bid_outline_task WHERE id = ?", String.class, taskId))
                .as("没有提示时不写一个空数组")
                .isNull();
    }
}
