-- ============================================================
-- 医院叙事生成助手 - 初始数据脚本
-- 数据库: hna
-- 说明: 插入默认角色、权限、用户、系统配置、功能开关
-- ============================================================

SET NAMES utf8mb4;

-- ------------------------------------------------------------
-- 1. 初始化角色
-- ------------------------------------------------------------
INSERT INTO `roles` (`role_code`, `role_name`, `description`, `status`) VALUES
('admin', '系统管理员', '拥有系统全部权限，可管理用户、角色、配置', 1),
('hospital_manager', '医务部/院领导', '可查看全院跨科室运营、资源调配、风险预警', 1),
('department_manager', '科室主任', '可查看科室运营数据、管理科室用户、查看质控报告', 1),
('quality_controller', '质控员', '负责质控异常闭环管理、整改追踪', 1),
('attending_doctor', '主治医师', '可使用患者全息视图、查房助手、查看重点患者', 1),
('resident_doctor', '住院医师', '可使用患者全息视图、查房助手、接收待办提醒', 1),
('researcher', '科研人员', '可筛选队列、导出脱敏数据、查看统计摘要', 1),
('doctor', '医生', '通用医生角色，可查看患者与使用查房助手', 1),
('viewer', '只读用户', '仅可查看数据，不可修改', 1)
ON DUPLICATE KEY UPDATE `role_name` = VALUES(`role_name`), `description` = VALUES(`description`);

-- ------------------------------------------------------------
-- 2. 初始化权限
-- ------------------------------------------------------------
INSERT INTO `permissions` (`permission_code`, `permission_name`, `resource`, `action`, `description`) VALUES
-- 用户与权限管理
('user:view', '查看用户', 'user', 'view', '查看用户列表与详情'),
('user:create', '创建用户', 'user', 'create', '创建新用户'),
('user:update', '编辑用户', 'user', 'update', '编辑用户信息'),
('user:delete', '删除用户', 'user', 'delete', '删除用户'),
('role:view', '查看角色', 'role', 'view', '查看角色与权限'),
('role:update', '分配权限', 'role', 'update', '为角色分配权限'),

-- 系统配置
('config:view', '查看配置', 'config', 'view', '查看系统配置'),
('config:update', '修改配置', 'config', 'update', '修改系统配置'),
('feature:view', '查看功能开关', 'feature', 'view', '查看功能开关'),
('feature:update', '修改功能开关', 'feature', 'update', '启用/禁用功能'),

-- 前台业务功能
('patient:view', '患者全息视图', 'patient', 'view', '查看患者全息视图'),
('ward_round:view', '查房助手', 'ward_round', 'view', '使用查房助手'),
('briefing:view', '科室晨会简报', 'briefing', 'view', '查看科室晨会简报'),
('report:view', '查看报告', 'report', 'view', '查看统计报告'),
('report:create', '生成报告', 'report', 'create', '生成统计报告'),
('kg:view', '知识图谱查看', 'knowledge_graph', 'view', '查看知识图谱'),
('kg:build', '构建知识图谱', 'knowledge_graph', 'execute', '构建/重建知识图谱'),
('rag:query', 'RAG问答', 'rag', 'view', '使用RAG问答'),
('quality:view', '查看质控', 'quality', 'view', '查看质控异常'),
('quality:manage', '管理质控', 'quality', 'update', '质控闭环管理'),
('risk:view', '查看风险预警', 'risk', 'view', '查看风险预警'),
('similar:view', '相似患者推荐', 'similar', 'view', '查看相似患者推荐'),
('pathway:view', '诊疗路径', 'pathway', 'view', '查看诊疗路径推荐'),
('research:view', '科研查看', 'research', 'view', '查看科研统计摘要'),
('research:export', '科研导出', 'research', 'execute', '导出脱敏数据集'),
('cache:view', '查看缓存', 'cache', 'view', '查看LLM缓存统计'),
('cache:clear', '清理缓存', 'cache', 'delete', '清理LLM缓存')
ON DUPLICATE KEY UPDATE `permission_name` = VALUES(`permission_name`), `resource` = VALUES(`resource`), `action` = VALUES(`action`);

-- ------------------------------------------------------------
-- 3. 分配角色权限
-- ------------------------------------------------------------
-- admin 拥有全部权限
INSERT IGNORE INTO `role_permissions` (`role_id`, `permission_id`)
SELECT r.id, p.id FROM `roles` r, `permissions` p WHERE r.role_code = 'admin';

-- hospital_manager 院领导：看全院数据与风险，不看系统配置
INSERT IGNORE INTO `role_permissions` (`role_id`, `permission_id`)
SELECT r.id, p.id FROM `roles` r, `permissions` p
WHERE r.role_code = 'hospital_manager'
  AND p.permission_code IN (
    'user:view', 'role:view',
    'patient:view', 'briefing:view', 'report:view', 'report:create',
    'kg:view', 'rag:query', 'quality:view', 'risk:view',
    'similar:view', 'pathway:view', 'research:view'
  );

-- department_manager 科室主任
INSERT IGNORE INTO `role_permissions` (`role_id`, `permission_id`)
SELECT r.id, p.id FROM `roles` r, `permissions` p
WHERE r.role_code = 'department_manager'
  AND p.permission_code IN (
    'user:view', 'role:view',
    'config:view', 'feature:view',
    'patient:view', 'ward_round:view', 'briefing:view',
    'report:view', 'report:create', 'kg:view', 'kg:build',
    'rag:query', 'quality:view', 'quality:manage', 'risk:view',
    'similar:view', 'pathway:view', 'research:view'
  );

-- quality_controller 质控员
INSERT IGNORE INTO `role_permissions` (`role_id`, `permission_id`)
SELECT r.id, p.id FROM `roles` r, `permissions` p
WHERE r.role_code = 'quality_controller'
  AND p.permission_code IN (
    'patient:view', 'briefing:view', 'report:view',
    'quality:view', 'quality:manage', 'risk:view',
    'similar:view', 'pathway:view'
  );

-- attending_doctor 主治医师
INSERT IGNORE INTO `role_permissions` (`role_id`, `permission_id`)
SELECT r.id, p.id FROM `roles` r, `permissions` p
WHERE r.role_code = 'attending_doctor'
  AND p.permission_code IN (
    'patient:view', 'ward_round:view', 'briefing:view',
    'report:view', 'report:create', 'kg:view', 'rag:query',
    'quality:view', 'risk:view', 'similar:view', 'pathway:view'
  );

-- resident_doctor 住院医师
INSERT IGNORE INTO `role_permissions` (`role_id`, `permission_id`)
SELECT r.id, p.id FROM `roles` r, `permissions` p
WHERE r.role_code = 'resident_doctor'
  AND p.permission_code IN (
    'patient:view', 'ward_round:view', 'briefing:view',
    'report:view', 'kg:view', 'rag:query',
    'quality:view', 'risk:view', 'similar:view'
  );

-- researcher 科研人员
INSERT IGNORE INTO `role_permissions` (`role_id`, `permission_id`)
SELECT r.id, p.id FROM `roles` r, `permissions` p
WHERE r.role_code = 'researcher'
  AND p.permission_code IN (
    'patient:view', 'briefing:view', 'report:view',
    'kg:view', 'research:view', 'research:export'
  );

-- doctor 通用医生
INSERT IGNORE INTO `role_permissions` (`role_id`, `permission_id`)
SELECT r.id, p.id FROM `roles` r, `permissions` p
WHERE r.role_code = 'doctor'
  AND p.permission_code IN (
    'patient:view', 'ward_round:view', 'briefing:view',
    'report:view', 'kg:view', 'rag:query',
    'quality:view', 'risk:view', 'similar:view'
  );

-- viewer 只读
INSERT IGNORE INTO `role_permissions` (`role_id`, `permission_id`)
SELECT r.id, p.id FROM `roles` r, `permissions` p
WHERE r.role_code = 'viewer'
  AND p.permission_code IN (
    'patient:view', 'briefing:view', 'report:view', 'kg:view'
  );

-- ------------------------------------------------------------
-- 4. 初始化默认用户
-- 默认密码: admin123 / director123 / quality123 / hospital123 / attending123 / resident123 / research123 / doctor123
-- ------------------------------------------------------------
INSERT INTO `users` (`username`, `password_hash`, `name`, `phone`, `email`, `department`, `status`) VALUES
('admin', '$2b$12$cUZHqjqVhUjQODgjGWLsxeRGuvJWk73VH0L8YeMimNRjvTkkF4U3.', '系统管理员', '13800000001', 'admin@hospital.local', '信息科', 1),
('director', '$2b$12$/TLukHAtisB96eoGzlnbpeQRVeijENZLGtqJVQMBz1uxo.yEKgEZq', '李主任', '13800000003', 'director@hospital.local', '肿瘤血液科', 1),
('quality', '$2b$12$1W69/q5FokPDXYLwsr8VV.Cv0vJRuOQ/cO5oX0LZkIK57kg9N9EXC', '王质控', '13800000004', 'quality@hospital.local', '质控科', 1),
('hospital', '$2b$12$A0242yjGTJIIBZK2NTaCOuV0EBEFGHVSNEOZNIWv2hqaEuKkouT7W', '赵院长', '13800000005', 'hospital@hospital.local', '医务部', 1),
('attending', '$2b$12$mngNZkniJkXM5j/kdD1zmO8xv/moRvfY9R04oFiRDUAr3.E1qiXUi', '刘主治', '13800000006', 'attending@hospital.local', '肿瘤血液科', 1),
('resident', '$2b$12$38EmoOe5MBdXPalM0m/PSeOtpAf/NNNpEBa17vjpma3qab7zmb80W', '陈住院医', '13800000007', 'resident@hospital.local', '肿瘤血液科', 1),
('researcher', '$2b$12$M4Lk38gt.gDkQZ7HIzhVl.308CM1jIxSkY8YO6lKvacYfc1NYs0E2', '林科研', '13800000008', 'researcher@hospital.local', '科研处', 1),
('doctor', '$2b$12$7IitbllQjqnlpctq.gzgqeW60PQZm3BYhzYeWXpkrRvEf9kAYhXQO', '张医生', '13800000002', 'doctor@hospital.local', '肿瘤血液科', 1),
('viewer', '$2b$12$7IitbllQjqnlpctq.gzgqeW60PQZm3BYhzYeWXpkrRvEf9kAYhXQO', '赵只读', '13800000009', 'viewer@hospital.local', '肿瘤血液科', 1)
ON DUPLICATE KEY UPDATE `name` = VALUES(`name`), `status` = VALUES(`status`);

-- 绑定角色
INSERT IGNORE INTO `user_roles` (`user_id`, `role_id`)
SELECT u.id, r.id FROM `users` u, `roles` r WHERE u.username = 'admin' AND r.role_code = 'admin';
INSERT IGNORE INTO `user_roles` (`user_id`, `role_id`)
SELECT u.id, r.id FROM `users` u, `roles` r WHERE u.username = 'director' AND r.role_code = 'department_manager';
INSERT IGNORE INTO `user_roles` (`user_id`, `role_id`)
SELECT u.id, r.id FROM `users` u, `roles` r WHERE u.username = 'quality' AND r.role_code = 'quality_controller';
INSERT IGNORE INTO `user_roles` (`user_id`, `role_id`)
SELECT u.id, r.id FROM `users` u, `roles` r WHERE u.username = 'hospital' AND r.role_code = 'hospital_manager';
INSERT IGNORE INTO `user_roles` (`user_id`, `role_id`)
SELECT u.id, r.id FROM `users` u, `roles` r WHERE u.username = 'attending' AND r.role_code = 'attending_doctor';
INSERT IGNORE INTO `user_roles` (`user_id`, `role_id`)
SELECT u.id, r.id FROM `users` u, `roles` r WHERE u.username = 'resident' AND r.role_code = 'resident_doctor';
INSERT IGNORE INTO `user_roles` (`user_id`, `role_id`)
SELECT u.id, r.id FROM `users` u, `roles` r WHERE u.username = 'researcher' AND r.role_code = 'researcher';
-- doctor 演示账号绑定通用 doctor 角色（不再绑定 attending_doctor，避免角色混淆）
DELETE ur FROM `user_roles` ur
JOIN `users` u ON ur.user_id = u.id
WHERE u.username = 'doctor';

INSERT IGNORE INTO `user_roles` (`user_id`, `role_id`)
SELECT u.id, r.id FROM `users` u, `roles` r WHERE u.username = 'doctor' AND r.role_code = 'doctor';

INSERT IGNORE INTO `user_roles` (`user_id`, `role_id`)
SELECT u.id, r.id FROM `users` u, `roles` r WHERE u.username = 'viewer' AND r.role_code = 'viewer';

-- ------------------------------------------------------------
-- 5. 初始化系统配置
-- ------------------------------------------------------------
INSERT INTO `system_configs` (`config_key`, `config_value`, `description`, `is_public`) VALUES
('llm.model', 'moonshot-v1-32k', '默认LLM模型', 1),
('llm.temperature', '0.7', 'LLM温度参数', 1),
('llm.max_tokens', '4096', 'LLM最大输出token数', 1),
('cache.ttl_hours', '24', 'LLM缓存默认TTL(小时)', 1),
('cache.enabled', 'true', '是否启用LLM缓存', 1),
('department.default', '肿瘤血液科', '默认科室', 1),
('report.auto_load_last', 'true', '报告生成是否默认加载最近一次', 1),
('briefing.push_time', '07:30', '每日晨会简报推送时间', 1),
('risk.high_score_threshold', '70', '高风险患者评分阈值', 1)
ON DUPLICATE KEY UPDATE `config_value` = VALUES(`config_value`), `description` = VALUES(`description`);

-- ------------------------------------------------------------
-- 6. 初始化功能开关
-- ------------------------------------------------------------
INSERT INTO `feature_switches` (`feature_code`, `feature_name`, `enabled`, `description`) VALUES
('patient_holographic', '患者全息视图', 1, '前台患者全息视图模块'),
('ward_round', '查房助手', 1, '前台查房助手模块'),
('daily_briefing', '科室晨会简报', 1, '前台科室晨会简报模块'),
('report_generation', '智能报告生成', 1, '科室运营简报与周简报生成'),
('rag_qa', 'RAG问答', 1, '基于知识图谱的RAG问答'),
('tcm_analysis', '中医辨证', 1, '中医特色分析'),
('kg_visualization', '知识图谱可视化', 1, '知识图谱可视化探索'),
('quality_control', '质控闭环管理', 1, '质控异常检测与闭环管理'),
('risk_prediction', '风险预警', 1, '患者风险预警'),
('similar_patient', '相似患者推荐', 1, '相似患者推荐'),
('pathway', '诊疗路径推荐', 1, '诊疗路径偏离提醒与推荐'),
('research_export', '科研导出', 1, '科研队列筛选与脱敏导出')
ON DUPLICATE KEY UPDATE `feature_name` = VALUES(`feature_name`), `enabled` = VALUES(`enabled`);
