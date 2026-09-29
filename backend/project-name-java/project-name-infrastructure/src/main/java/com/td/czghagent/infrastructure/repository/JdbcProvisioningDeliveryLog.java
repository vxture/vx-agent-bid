// GENERATED_BY_AI
// MODEL: claude-opus-5-5
// DATE: 2026-09-29
package com.td.czghagent.infrastructure.repository;

import com.td.czghagent.domain.repository.ProvisioningDeliveryLog;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.List;

/** 只读投递流水表；不碰开通状态表。 */
@Repository
public class JdbcProvisioningDeliveryLog implements ProvisioningDeliveryLog {

    private final JdbcTemplate jdbcTemplate;

    public JdbcProvisioningDeliveryLog(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @Override
    public List<Delivery> recent(int limit) {
        return jdbcTemplate.query("""
                SELECT event_type, outcome, received_at FROM platform_provision_delivery
                ORDER BY received_at DESC LIMIT ?
                """, (rs, row) -> new Delivery(
                        rs.getString("event_type"), rs.getString("outcome"),
                        JdbcTimes.localDateTime(rs, "received_at")), limit);
    }
}
