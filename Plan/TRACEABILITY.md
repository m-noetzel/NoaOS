# Requirements Traceability Matrix

Generated: 2026-03-12 17:09 UTC

## Summary

| Metric | Count |
|--------|-------|
| Total SPEC sections | 128 |
| Covered (phase + test) | 97 |
| Partial (phase or test only) | 12 |
| Orphaned (no coverage) | 19 |
| Critical orphans (§1–§25) | 9 |
| Non-critical orphans (§26+) | 10 |

## Critical Orphans (FAIL — §1–§25 with no coverage)

- **§2.3**
- **§4.2**
- **§4.3**
- **§7.2**
- **§10.2**
- **§10.3**
- **§11.4**
- **§20.2**
- **§20.5**

## Non-Critical Orphans (§26+ deferred/future)

- §27.1
- §27.2
- §28.6
- §32
- §32.1
- §32.2
- §32.3
- §33
- §35
- §38

## Full Coverage Table

| SPEC Section | Phase(s) | Test File(s) | Status |
|---|---|---|---|
| §1 | GO3 | test_qe5_traceability.py | COVERED |
| §2 | AB5, CP1, CP2, MR3, MR5, MR8, MR9, OC1, TG1, TI6 | test_orchestrator.py, test_qe5_traceability.py, test_tg1_gateway.py, test_tm4_tool_permissions.py, test_tm6_mcp_server_connector.py, test_tool_interface.py | COVERED |
| §2.1 | CP2, MR3, MR5, MR8, MR9, OC1, TG1, TI6 | test_orchestrator.py, test_qe5_traceability.py, test_tg1_gateway.py, test_tm4_tool_permissions.py, test_tm6_mcp_server_connector.py, test_tool_interface.py | COVERED |
| §2.2 | CP1, OC1 | test_orchestrator.py, test_qe5_traceability.py, test_tm4_tool_permissions.py, test_tool_interface.py | COVERED |
| §2.3 | — | — | ORPHANED |
| §2.4 | AB5 | — | PARTIAL |
| §3 | GO3 | test_qe5_traceability.py | COVERED |
| §4 | CP4, F1 | test_config.py, test_qe5_traceability.py, test_tm6_mcp_server_connector.py | COVERED |
| §4.1 | CP4, F1 | test_config.py, test_qe5_traceability.py, test_tm6_mcp_server_connector.py | COVERED |
| §4.2 | — | — | ORPHANED |
| §4.3 | — | — | ORPHANED |
| §5 | F4, GO1, GO3, MR1, MR7, iOS4 | test_auth.py, test_go1_oauth_backend.py, test_ios11_integration_polish.py, test_ios4_auth_contract.py, test_models.py, test_mr1_auth.py, test_pr6_integration.py, test_qe1_ci_backlog.py, test_qe5_traceability.py | COVERED |
| §5.1 | F4, MR1, iOS4 | test_auth.py, test_ios4_auth_contract.py, test_mr1_auth.py, test_pr6_integration.py | COVERED |
| §5.2 | F4, MR1 | test_auth.py, test_ios4_auth_contract.py, test_models.py, test_mr1_auth.py | COVERED |
| §5.3 | F4, GO1, MR1, MR7 | test_auth.py, test_go1_oauth_backend.py, test_ios11_integration_polish.py, test_ios4_auth_contract.py, test_mr1_auth.py | COVERED |
| §5.4 | F4, MR1 | test_auth.py, test_ios4_auth_contract.py, test_mr1_auth.py | COVERED |
| §6 | DW2, OC1 | test_ios5_chat_contract.py, test_orchestrator.py, test_qc4_domain_isolation.py | COVERED |
| §6.1 | OC1 | test_orchestrator.py | COVERED |
| §6.2 | DW2 | test_ios5_chat_contract.py, test_qc4_domain_isolation.py | COVERED |
| §7 | DE2, DW3, F1, OC1 | test_config.py, test_de2_tls.py, test_mr6_compose_hardening.py, test_orchestrator.py | COVERED |
| §7.1 | DE2, F1, OC1 | test_config.py, test_de2_tls.py, test_mr6_compose_hardening.py, test_orchestrator.py | COVERED |
| §7.2 | — | — | ORPHANED |
| §7.3 | DW3 | — | PARTIAL |
| §8 | AB5, DE3, DW1, DW2, F1, GT2, GT4, LP4, MR6, TG2 | test_config.py, test_gt2_google_clients.py, test_gt4_mcp_remote.py, test_llm_ollama.py, test_mr6_compose_hardening.py, test_private_worker.py, test_qc4_domain_isolation.py, test_tm6_mcp_server_connector.py | COVERED |
| §8.1 | DE3, DW1, F1, LP4, MR6 | test_config.py, test_llm_ollama.py, test_mr6_compose_hardening.py, test_private_worker.py | COVERED |
| §8.2 | AB5, DE3, DW2, F1, GT2, GT4, TG2 | test_config.py, test_gt2_google_clients.py, test_gt4_mcp_remote.py | COVERED |
| §8.3 | — | test_qc4_domain_isolation.py, test_tm6_mcp_server_connector.py | PARTIAL |
| §9 | DW1, MR2 | test_memory_tool.py, test_private_worker.py, test_qc4_domain_isolation.py, test_qc5_database_integrity.py, test_qe5_traceability.py | COVERED |
| §9.1 | DW1, MR2 | test_memory_tool.py, test_private_worker.py, test_qc4_domain_isolation.py, test_qe5_traceability.py | COVERED |
| §9.2 | DW1 | test_private_worker.py, test_qc4_domain_isolation.py, test_qe5_traceability.py | COVERED |
| §9.3 | DW1 | test_private_worker.py | COVERED |
| §9.4 | DW1 | test_private_worker.py, test_qc5_database_integrity.py | COVERED |
| §10 | DE1, DE4, F2, GO3, MR9, OP1, OP4, OP5 | test_audit_fixes.py, test_backup.py, test_ios3_networking_contract.py, test_models.py, test_mv1_threads.py, test_qc5_database_integrity.py, test_qc8_architecture.py | COVERED |
| §10.1 | F2 | test_audit_fixes.py, test_ios3_networking_contract.py, test_models.py, test_mv1_threads.py, test_qc5_database_integrity.py, test_qc8_architecture.py | COVERED |
| §10.2 | — | — | ORPHANED |
| §10.3 | — | — | ORPHANED |
| §10.4 | DE1, F2, OP4 | test_models.py | COVERED |
| §10.5 | DE4, MR9, OP1, OP5 | test_backup.py | COVERED |
| §11 | CM1, CM2, GO1, GO3, GT1, GT3 | test_go1_oauth_backend.py, test_gt1_google_oauth.py, test_gt3_notion_client.py, test_keychain_config.py, test_pr2_frontend_fixes.py, test_pr4_security_robustness.py, test_pr6_integration.py, test_qc8_architecture.py, test_settings.py, test_tm1_tool_health.py | COVERED |
| §11.1 | CM1, CM2, GO1, GO3, GT1, GT3 | test_go1_oauth_backend.py, test_gt3_notion_client.py, test_keychain_config.py, test_pr2_frontend_fixes.py, test_pr4_security_robustness.py, test_pr6_integration.py, test_settings.py | COVERED |
| §11.2 | CM2, GT1 | test_gt1_google_oauth.py, test_keychain_config.py | COVERED |
| §11.3 | CM2, GO1, GT1 | test_go1_oauth_backend.py, test_gt1_google_oauth.py, test_qc8_architecture.py | COVERED |
| §11.4 | — | — | ORPHANED |
| §12 | CM1, GO1, GO2, GO3, GT2, GT3, TG2, TG3, TI1, TI2, TI3, TI4, TI5, TI6 | test_calendar_tool.py, test_gmail_tool.py, test_go1_oauth_backend.py, test_gt1_google_oauth.py, test_gt2_google_clients.py, test_gt3_notion_client.py, test_memory_tool.py, test_notion_tool.py, test_tm1_tool_health.py, test_tm2_tools_enrichment.py, test_tm5_custom_tools.py, test_tool_interface.py, test_web_search_tool.py | COVERED |
| §12.1 | GO1, GO2, GO3, GT2, TI2 | test_calendar_tool.py, test_go1_oauth_backend.py, test_gt1_google_oauth.py, test_gt2_google_clients.py, test_tm2_tools_enrichment.py, test_tool_interface.py | COVERED |
| §12.2 | GO1, GO2, GO3, GT2, TI3 | test_gmail_tool.py, test_go1_oauth_backend.py, test_gt1_google_oauth.py, test_gt2_google_clients.py, test_tool_interface.py | COVERED |
| §12.3 | GT3, TI4 | test_gt3_notion_client.py, test_notion_tool.py, test_tool_interface.py | COVERED |
| §12.4 | TG2, TG3, TI5 | test_tool_interface.py, test_web_search_tool.py | COVERED |
| §12.5 | TI1 | test_memory_tool.py, test_tool_interface.py | COVERED |
| §13 | DW1, MR2, PR1, TI1, WC5 | test_ios5_chat_contract.py, test_memory_tool.py, test_mr2_memory_persistence.py, test_mv2_mv3_stubs.py, test_mv5_smoke.py, test_pr1_backend_fixes.py, test_pr4_security_robustness.py, test_pr6_integration.py, test_private_worker.py | COVERED |
| §13.1 | DW1 | test_ios5_chat_contract.py, test_private_worker.py | COVERED |
| §13.2 | DW1, MR2, PR1, TI1, WC5 | test_memory_tool.py, test_mr2_memory_persistence.py, test_mv2_mv3_stubs.py, test_mv5_smoke.py, test_pr1_backend_fixes.py, test_pr4_security_robustness.py, test_pr6_integration.py, test_private_worker.py | COVERED |
| §13.3 | TI1 | test_memory_tool.py | COVERED |
| §14 | CP1, CP4, DW2, DW4, LP1, LP2, LP3, LP4, LP5, MR8, WC6 | test_llm_anthropic.py, test_llm_google_ai.py, test_llm_ollama.py, test_llm_openai.py, test_llm_router.py, test_privacy_router.py, test_qc5_database_integrity.py | COVERED |
| §14.1 | DW2, LP1, LP2, LP3, LP4 | test_llm_anthropic.py, test_llm_google_ai.py, test_llm_ollama.py, test_llm_openai.py | COVERED |
| §14.2 | CP1, CP4, DW4, LP5 | test_llm_router.py, test_privacy_router.py | COVERED |
| §14.3 | CP1, DW4, LP5 | test_llm_router.py, test_privacy_router.py | COVERED |
| §14.4 | LP1, LP2, LP3, LP5, MR8, WC6 | test_llm_anthropic.py, test_llm_google_ai.py, test_llm_openai.py, test_llm_router.py, test_privacy_router.py | COVERED |
| §15 | AB5 | — | PARTIAL |
| §16 | AB2, TI6 | test_calendar_tool.py, test_gmail_tool.py, test_notion_tool.py, test_validation.py | COVERED |
| §16.1 | AB2 | test_validation.py | COVERED |
| §16.2 | AB2 | test_validation.py | COVERED |
| §16.3 | AB2 | test_calendar_tool.py, test_gmail_tool.py, test_notion_tool.py, test_validation.py | COVERED |
| §16.4 | AB2 | test_validation.py | COVERED |
| §17 | AB4 | test_durable_queue.py, test_models.py, test_mv2_mv3_stubs.py, test_mv5_smoke.py, test_qc5_database_integrity.py | COVERED |
| §17.1 | AB4 | test_durable_queue.py | COVERED |
| §17.2 | AB4 | test_durable_queue.py, test_models.py, test_mv2_mv3_stubs.py, test_mv5_smoke.py, test_qc5_database_integrity.py | COVERED |
| §17.3 | AB4 | test_durable_queue.py | COVERED |
| §18 | DW4 | test_privacy_router.py | COVERED |
| §19 | MR4, MR5, OC4, TG1, TG3, TI6, WC3 | test_ios11_integration_polish.py, test_memory_tool.py, test_policy.py, test_qc8_architecture.py, test_tg1_gateway.py, test_tm4_tool_permissions.py, test_tm5_custom_tools.py, test_tool_governance.py | COVERED |
| §19.1 | TG1, TI6 | test_memory_tool.py, test_qc8_architecture.py, test_tg1_gateway.py, test_tool_governance.py | COVERED |
| §19.2 | OC4, TG1, TI6, WC3 | test_ios11_integration_polish.py, test_policy.py, test_tg1_gateway.py, test_tool_governance.py | COVERED |
| §19.3 | MR4, TG1, TG3, TI6 | test_qc8_architecture.py, test_tg1_gateway.py, test_tool_governance.py | COVERED |
| §20 | DE2, DW3, F1, GT4, MR6 | test_config.py, test_de2_tls.py, test_gt4_mcp_remote.py | COVERED |
| §20.1 | DE2, DW3, F1, MR6 | test_config.py, test_de2_tls.py | COVERED |
| §20.2 | — | — | ORPHANED |
| §20.3 | DW3 | — | PARTIAL |
| §20.4 | DW3 | — | PARTIAL |
| §20.5 | — | — | ORPHANED |
| §21 | OC4, WC3 | test_policy.py, test_qc8_architecture.py, test_tm2_tools_enrichment.py | COVERED |
| §22 | CP2, CP3, F2, OC2, PR1, WC1, WC2, WC7, iOS5 | test_ios11_integration_polish.py, test_ios3_networking_contract.py, test_ios5_chat_contract.py, test_models.py, test_mv2_mv3_stubs.py, test_mv5_smoke.py, test_pr1_backend_fixes.py, test_pr4_security_robustness.py, test_pr6_integration.py, test_qc5_database_integrity.py, test_qc8_architecture.py, test_runs.py | COVERED |
| §22.1 | CP2, F2, OC2, PR1 | test_ios3_networking_contract.py, test_ios5_chat_contract.py, test_models.py, test_pr1_backend_fixes.py, test_pr4_security_robustness.py, test_pr6_integration.py, test_runs.py | COVERED |
| §22.2 | CP2, F2, OC2, PR1, WC2, iOS5 | test_ios11_integration_polish.py, test_ios3_networking_contract.py, test_ios5_chat_contract.py, test_models.py, test_pr1_backend_fixes.py, test_pr6_integration.py, test_qc5_database_integrity.py, test_runs.py | COVERED |
| §22.3 | OC2, WC7 | test_models.py, test_mv2_mv3_stubs.py, test_mv5_smoke.py, test_runs.py | COVERED |
| §22.4 | CP2, CP3, OC2, WC1 | test_ios5_chat_contract.py, test_qc8_architecture.py, test_runs.py | COVERED |
| §22.5 | F2, OC2 | test_models.py, test_runs.py | COVERED |
| §23 | AB3, OC4, WC4, iOS1, iOS6, iOS7 | test_ios1_apns.py, test_policy.py, test_qc5_database_integrity.py, test_scheduler.py | COVERED |
| §23.1 | AB3 | test_scheduler.py | COVERED |
| §23.2 | OC4, iOS1, iOS6, iOS7 | test_ios1_apns.py, test_policy.py, test_qc5_database_integrity.py | COVERED |
| §23.3 | AB3 | test_scheduler.py | COVERED |
| §23.4 | AB3, WC4 | test_scheduler.py | COVERED |
| §24 | AB1, CM1, WC6 | test_cost.py, test_pr2_frontend_fixes.py, test_settings.py | COVERED |
| §25 | CP3, F3, MR7, TI6, iOS3, iOS9 | test_api_health.py, test_ios3_networking_contract.py, test_qc8_architecture.py, test_qe5_traceability.py, test_tool_governance.py | COVERED |
| §25.1 | CP3, F3, MR7 | — | PARTIAL |
| §25.2 | F3 | — | PARTIAL |
| §25.3 | F3, iOS3 | test_api_health.py, test_ios3_networking_contract.py, test_qc8_architecture.py | COVERED |
| §25.4 | TI6, iOS9 | test_ios3_networking_contract.py, test_qc8_architecture.py, test_tool_governance.py | COVERED |
| §26 | — | test_qe5_traceability.py | PARTIAL |
| §27 | — | test_qe5_traceability.py | PARTIAL |
| §27.1 | — | — | ORPHANED |
| §27.2 | — | — | ORPHANED |
| §28 | F3, MR3, MR4, MR7, MR9, OC3, OP2, OP3, OP5 | test_api_health.py, test_audit.py, test_audit_fixes.py, test_compose_health.py, test_log_rotation.py, test_models.py, test_qc5_database_integrity.py, test_retention.py | COVERED |
| §28.1 | MR3, MR7, OC3 | test_audit.py, test_models.py, test_qc5_database_integrity.py | COVERED |
| §28.2 | MR3, MR9, OC3 | test_audit.py, test_models.py, test_qc5_database_integrity.py | COVERED |
| §28.3 | OC3, OP2 | test_audit.py, test_log_rotation.py | COVERED |
| §28.4 | MR4 | — | PARTIAL |
| §28.5 | F3, MR4, OP3 | test_api_health.py, test_audit_fixes.py, test_compose_health.py | COVERED |
| §28.6 | — | — | ORPHANED |
| §28.7 | MR9, OC3, OP2 | test_audit.py, test_qc5_database_integrity.py, test_retention.py | COVERED |
| §29 | DE2, GO2, GO3, OC4, WC1, WC2, WC3, WC6, WC7, iOS1, iOS10, iOS2, iOS3, iOS4, iOS5, iOS6, iOS7, iOS8, iOS9 | test_de2_tls.py, test_ios11_integration_polish.py, test_ios1_apns.py, test_ios2_voice.py, test_ios3_networking_contract.py, test_ios4_auth_contract.py, test_ios5_chat_contract.py, test_ios8_voice_transcription.py, test_mv2_mv3_stubs.py, test_mv5_smoke.py, test_policy.py, test_pr6_integration.py, test_qc2_security_hardening.py, test_qe5_traceability.py | COVERED |
| §29.1 | WC1, iOS3 | test_ios3_networking_contract.py | COVERED |
| §29.2 | GO2, WC1, WC2, WC6, WC7, iOS5 | test_ios5_chat_contract.py | COVERED |
| §29.3 | GO3, WC7, iOS2, iOS4, iOS7, iOS8, iOS9 | test_ios11_integration_polish.py, test_ios2_voice.py, test_ios3_networking_contract.py, test_ios4_auth_contract.py, test_ios5_chat_contract.py, test_ios8_voice_transcription.py, test_pr6_integration.py, test_qc2_security_hardening.py, test_qe5_traceability.py | COVERED |
| §29.4 | DE2, iOS10 | test_de2_tls.py, test_ios11_integration_polish.py, test_ios3_networking_contract.py, test_ios4_auth_contract.py | COVERED |
| §29.5 | iOS1, iOS6 | test_ios11_integration_polish.py, test_ios1_apns.py | COVERED |
| §29.6 | OC4, WC3, iOS1, iOS7 | test_ios11_integration_polish.py, test_ios1_apns.py, test_ios3_networking_contract.py, test_ios5_chat_contract.py, test_mv2_mv3_stubs.py, test_mv5_smoke.py, test_policy.py, test_pr6_integration.py | COVERED |
| §30 | DE3, MR6, MR9, OP3, OP4 | test_compose_health.py, test_preflight.py | COVERED |
| §31 | DE3, MR9, OP3, OP5 | test_compose_health.py, test_preflight.py | COVERED |
| §32 | — | — | ORPHANED |
| §32.1 | — | — | ORPHANED |
| §32.2 | — | — | ORPHANED |
| §32.3 | — | — | ORPHANED |
| §33 | — | — | ORPHANED |
| §34 | DE1, DE4, MR5 | test_qe5_traceability.py | COVERED |
| §35 | — | — | ORPHANED |
| §36 | DE1 | — | PARTIAL |
| §37 | iOS11 | test_ios11_integration_polish.py, test_pr6_integration.py | COVERED |
| §38 | — | — | ORPHANED |

<!-- MANUAL SECTIONS -->

## Test Quality Baselines (QE6)

These baselines are maintained manually and survive traceability regenerations.

| Metric | Baseline | Date |
|--------|----------|------|
| Total tests passing | 1452 Python + 233 Swift | 2026-03-12 |
| Unit test files | 67 | 2026-03-12 |
| Integration test files | 6 | 2026-03-12 |
| SPEC coverage (Covered) | ≥60% | 2026-03-12 |
| Critical orphans (§1–§25) | ≤15 | 2026-03-12 |
