-- ============================================================
-- 医院叙事生成助手 - 数据库建表脚本
-- 数据库: hna
-- 说明: 创建业务数据表与后台管理表
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ------------------------------------------------------------
-- 1. 后台管理: 用户表
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '用户ID',
    `username` VARCHAR(64) NOT NULL COMMENT '登录账号',
    `password_hash` VARCHAR(255) NOT NULL COMMENT '密码哈希',
    `name` VARCHAR(64) DEFAULT NULL COMMENT '姓名',
    `phone` VARCHAR(32) DEFAULT NULL COMMENT '手机号',
    `email` VARCHAR(128) DEFAULT NULL COMMENT '邮箱',
    `department` VARCHAR(64) DEFAULT NULL COMMENT '所属科室',
    `status` TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 0禁用 1启用',
    `last_login_at` DATETIME DEFAULT NULL COMMENT '最后登录时间',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_username` (`username`),
    UNIQUE KEY `uk_phone` (`phone`),
    UNIQUE KEY `uk_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='用户表';

-- ------------------------------------------------------------
-- 2. 后台管理: 角色表
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `roles`;
CREATE TABLE `roles` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '角色ID',
    `role_code` VARCHAR(64) NOT NULL COMMENT '角色编码',
    `role_name` VARCHAR(64) NOT NULL COMMENT '角色名称',
    `description` VARCHAR(255) DEFAULT NULL COMMENT '描述',
    `status` TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 0禁用 1启用',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_role_code` (`role_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='角色表';

-- ------------------------------------------------------------
-- 3. 后台管理: 权限表
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `permissions`;
CREATE TABLE `permissions` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '权限ID',
    `permission_code` VARCHAR(128) NOT NULL COMMENT '权限编码',
    `permission_name` VARCHAR(128) NOT NULL COMMENT '权限名称',
    `resource` VARCHAR(64) NOT NULL COMMENT '资源类型(menu/api/data)',
    `action` VARCHAR(64) NOT NULL COMMENT '操作类型(view/create/update/delete/execute)',
    `description` VARCHAR(255) DEFAULT NULL COMMENT '描述',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_permission_code` (`permission_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='权限表';

-- ------------------------------------------------------------
-- 4. 后台管理: 角色-权限关联表
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `role_permissions`;
CREATE TABLE `role_permissions` (
    `role_id` BIGINT UNSIGNED NOT NULL COMMENT '角色ID',
    `permission_id` BIGINT UNSIGNED NOT NULL COMMENT '权限ID',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`role_id`, `permission_id`),
    KEY `idx_permission_id` (`permission_id`),
    CONSTRAINT `fk_rp_role` FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_rp_permission` FOREIGN KEY (`permission_id`) REFERENCES `permissions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='角色权限关联表';

-- ------------------------------------------------------------
-- 5. 后台管理: 用户-角色关联表
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `user_roles`;
CREATE TABLE `user_roles` (
    `user_id` BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    `role_id` BIGINT UNSIGNED NOT NULL COMMENT '角色ID',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`user_id`, `role_id`),
    KEY `idx_role_id` (`role_id`),
    CONSTRAINT `fk_ur_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_ur_role` FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='用户角色关联表';

-- ------------------------------------------------------------
-- 6. 后台管理: 系统配置表
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `system_configs`;
CREATE TABLE `system_configs` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `config_key` VARCHAR(128) NOT NULL COMMENT '配置键',
    `config_value` TEXT COMMENT '配置值',
    `description` VARCHAR(255) DEFAULT NULL COMMENT '描述',
    `is_public` TINYINT NOT NULL DEFAULT 0 COMMENT '是否前端可见: 0否 1是',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_config_key` (`config_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='系统配置表';

-- ------------------------------------------------------------
-- 7. 后台管理: 功能开关表
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `feature_switches`;
CREATE TABLE `feature_switches` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `feature_code` VARCHAR(128) NOT NULL COMMENT '功能编码',
    `feature_name` VARCHAR(128) NOT NULL COMMENT '功能名称',
    `enabled` TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用: 0关闭 1开启',
    `description` VARCHAR(255) DEFAULT NULL COMMENT '描述',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_feature_code` (`feature_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='功能开关表';

-- ------------------------------------------------------------
-- 8. 后台管理: 操作日志表
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `operation_logs`;
CREATE TABLE `operation_logs` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '用户ID',
    `username` VARCHAR(64) DEFAULT NULL COMMENT '用户名',
    `action` VARCHAR(64) NOT NULL COMMENT '操作类型',
    `resource` VARCHAR(128) NOT NULL COMMENT '操作对象',
    `detail` JSON DEFAULT NULL COMMENT '操作详情',
    `ip_address` VARCHAR(64) DEFAULT NULL COMMENT 'IP地址',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='操作日志表';

-- ------------------------------------------------------------
-- 9. 业务数据: 患者基础信息表
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `patients`;
CREATE TABLE `patients` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `patient_id` VARCHAR(64) NOT NULL COMMENT '患者ID',
    `medical_record_no` VARCHAR(64) DEFAULT NULL COMMENT '病案号',
    `age` INT DEFAULT NULL COMMENT '年龄',
    `gender` VARCHAR(16) DEFAULT NULL COMMENT '性别',
    `marriage` VARCHAR(32) DEFAULT NULL COMMENT '婚姻状况',
    `occupation` VARCHAR(64) DEFAULT NULL COMMENT '职业',
    `allergy_history` TEXT COMMENT '过敏史',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_patient_id` (`patient_id`),
    KEY `idx_medical_record_no` (`medical_record_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='患者基础信息表';

-- ------------------------------------------------------------
-- 10. 业务数据: 就诊记录表
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `visits`;
CREATE TABLE `visits` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `patient_id` VARCHAR(64) NOT NULL COMMENT '患者ID',
    `medical_record_no` VARCHAR(64) DEFAULT NULL COMMENT '病案号',
    `visit_no` VARCHAR(64) NOT NULL COMMENT '就诊流水号',
    `admission_date` DATE DEFAULT NULL COMMENT '入院日期',
    `discharge_date` DATE DEFAULT NULL COMMENT '出院日期',
    `length_of_stay` INT DEFAULT NULL COMMENT '住院天数',
    `department` VARCHAR(64) DEFAULT NULL COMMENT '科室',
    `admission_count` INT DEFAULT NULL COMMENT '入院次数',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_visit_no` (`visit_no`),
    KEY `idx_patient_id` (`patient_id`),
    KEY `idx_admission_date` (`admission_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='就诊记录表';

-- ------------------------------------------------------------
-- 11. 业务数据: 医嘱表
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `orders`;
CREATE TABLE `orders` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `patient_id` VARCHAR(64) NOT NULL COMMENT '患者ID',
    `medical_record_no` VARCHAR(64) DEFAULT NULL COMMENT '病案号',
    `visit_no` VARCHAR(64) DEFAULT NULL COMMENT '就诊流水号',
    `order_no` VARCHAR(64) DEFAULT NULL COMMENT '医嘱流水号',
    `order_type` VARCHAR(32) DEFAULT NULL COMMENT '类型',
    `order_time` DATETIME DEFAULT NULL COMMENT '医嘱下达时间',
    `confirm_time` DATETIME DEFAULT NULL COMMENT '医嘱确认时间',
    `order_dept` VARCHAR(64) DEFAULT NULL COMMENT '医嘱下达科室名称',
    `start_time` DATETIME DEFAULT NULL COMMENT '医嘱开始时间',
    `stop_time` DATETIME DEFAULT NULL COMMENT '医嘱停止时间',
    `order_category` VARCHAR(64) DEFAULT NULL COMMENT '医嘱类别',
    `order_group_no` VARCHAR(64) DEFAULT NULL COMMENT '医嘱组号',
    `item_code` VARCHAR(128) DEFAULT NULL COMMENT '医嘱项目代码',
    `item_name` VARCHAR(255) DEFAULT NULL COMMENT '医嘱项目名称',
    `single_dose` VARCHAR(64) DEFAULT NULL COMMENT '单次剂量',
    `single_dose_unit` VARCHAR(64) DEFAULT NULL COMMENT '单次剂量单位',
    `drug_form` VARCHAR(64) DEFAULT NULL COMMENT '药品剂型',
    `frequency_code` VARCHAR(64) DEFAULT NULL COMMENT '使用频率代码',
    `frequency_name` VARCHAR(64) DEFAULT NULL COMMENT '使用频率名称',
    `administration_route` VARCHAR(64) DEFAULT NULL COMMENT '给药途径',
    `total_quantity` VARCHAR(64) DEFAULT NULL COMMENT '总数量',
    `total_unit` VARCHAR(64) DEFAULT NULL COMMENT '总数量单位',
    `remark` TEXT COMMENT '医嘱备注',
    `side_effects` TEXT COMMENT '药物潜在副作用',
    `is_drug` TINYINT DEFAULT NULL COMMENT '是否药品',
    `manufacturer` VARCHAR(255) DEFAULT NULL COMMENT '生产厂家',
    `trade_name` VARCHAR(255) DEFAULT NULL COMMENT '药品商品名',
    `order_status` VARCHAR(32) DEFAULT NULL COMMENT '医嘱状态',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_patient_id` (`patient_id`),
    KEY `idx_visit_no` (`visit_no`),
    KEY `idx_order_time` (`order_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='医嘱表';

-- ------------------------------------------------------------
-- 12. 业务数据: 手术表
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `surgeries`;
CREATE TABLE `surgeries` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `patient_id` VARCHAR(64) NOT NULL COMMENT '患者ID',
    `medical_record_no` VARCHAR(64) DEFAULT NULL COMMENT '病案号',
    `visit_no` VARCHAR(64) DEFAULT NULL COMMENT '就诊流水号',
    `order_no` VARCHAR(64) DEFAULT NULL COMMENT '医嘱流水号',
    `surgery_category` VARCHAR(64) DEFAULT NULL COMMENT '手术类别',
    `surgery_level` VARCHAR(32) DEFAULT NULL COMMENT '手术等级',
    `operation_number` VARCHAR(64) DEFAULT NULL COMMENT 'operation_number（icu）',
    `anesthesia_method` VARCHAR(64) DEFAULT NULL COMMENT '麻醉方式',
    `surgery_code` VARCHAR(128) DEFAULT NULL COMMENT '手术编码',
    `surgery_name` VARCHAR(255) DEFAULT NULL COMMENT '手术名称',
    `surgery_description` TEXT COMMENT '手术过程描述',
    `start_time` DATETIME DEFAULT NULL COMMENT '手术开始时间',
    `end_time` DATETIME DEFAULT NULL COMMENT '手术结束时间',
    `duration` VARCHAR(64) DEFAULT NULL COMMENT '手术持续时间',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_patient_id` (`patient_id`),
    KEY `idx_visit_no` (`visit_no`),
    KEY `idx_start_time` (`start_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='手术表';

-- ------------------------------------------------------------
-- 13. 业务数据: 检查表
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `exams`;
CREATE TABLE `exams` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `patient_id` VARCHAR(64) NOT NULL COMMENT '患者ID',
    `visit_no` VARCHAR(64) DEFAULT NULL COMMENT '就诊流水号',
    `apply_dept` VARCHAR(64) DEFAULT NULL COMMENT '申请科室',
    `exam_part` VARCHAR(128) DEFAULT NULL COMMENT '检查部位',
    `exam_no` VARCHAR(64) DEFAULT NULL COMMENT '检查编号',
    `description` TEXT COMMENT '描述',
    `diagnosis` TEXT COMMENT '诊断',
    `exam_date` DATE DEFAULT NULL COMMENT '检查日期',
    `report_date` DATE DEFAULT NULL COMMENT '报告日期',
    `medical_record_no` VARCHAR(64) DEFAULT NULL COMMENT '病案号',
    `diagnosis1` VARCHAR(255) DEFAULT NULL,
    `diagnosis2` VARCHAR(255) DEFAULT NULL,
    `diagnosis3` VARCHAR(255) DEFAULT NULL,
    `diagnosis4` VARCHAR(255) DEFAULT NULL,
    `diagnosis5` VARCHAR(255) DEFAULT NULL,
    `standard_name` VARCHAR(255) DEFAULT NULL COMMENT '标准化项目名称（匹配结果）',
    `standard_code` VARCHAR(128) DEFAULT NULL COMMENT '编码',
    `standard_category` VARCHAR(128) DEFAULT NULL COMMENT '标准大类名称',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_patient_id` (`patient_id`),
    KEY `idx_visit_no` (`visit_no`),
    KEY `idx_exam_date` (`exam_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='检查表';

-- ------------------------------------------------------------
-- 14. 业务数据: 检验表
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `labs`;
CREATE TABLE `labs` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `patient_id` VARCHAR(64) NOT NULL COMMENT '患者ID',
    `visit_no` VARCHAR(64) DEFAULT NULL COMMENT '就诊流水号',
    `submit_dept` VARCHAR(64) DEFAULT NULL COMMENT '送检科室',
    `sample_type` VARCHAR(64) DEFAULT NULL COMMENT '样本种类',
    `sample_code` VARCHAR(64) DEFAULT NULL COMMENT '样本编码',
    `submit_time` DATETIME DEFAULT NULL COMMENT '送检时间',
    `test_time` DATETIME DEFAULT NULL COMMENT '检验时间',
    `report_time` DATETIME DEFAULT NULL COMMENT '报告时间',
    `result_value` VARCHAR(255) DEFAULT NULL COMMENT '检验项目结果',
    `result_unit` VARCHAR(64) DEFAULT NULL COMMENT '检验项目单位',
    `result_hint` VARCHAR(64) DEFAULT NULL COMMENT '检验项目提示',
    `reference_range` VARCHAR(128) DEFAULT NULL COMMENT '参考范围',
    `medical_record_no` VARCHAR(64) DEFAULT NULL COMMENT '病案号',
    `result_name` VARCHAR(255) DEFAULT NULL COMMENT '检验结果名称',
    `standard_name` VARCHAR(255) DEFAULT NULL COMMENT '标准项目名称',
    `standard_code` VARCHAR(128) DEFAULT NULL COMMENT '标准编码',
    `quantitative_value` DECIMAL(18,6) DEFAULT NULL COMMENT '结果定量化',
    `item_name` VARCHAR(255) DEFAULT NULL COMMENT '检验项目名称',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_patient_id` (`patient_id`),
    KEY `idx_visit_no` (`visit_no`),
    KEY `idx_report_time` (`report_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='检验表';

-- ------------------------------------------------------------
-- 15. 业务数据: 入院信息宽表
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `admissions`;
CREATE TABLE `admissions` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `patient_id` VARCHAR(64) NOT NULL COMMENT '患者ID',
    `medical_record_no` VARCHAR(64) DEFAULT NULL COMMENT '病案号',
    `visit_no` VARCHAR(64) DEFAULT NULL COMMENT '就诊流水号',
    `admission_date` DATE DEFAULT NULL COMMENT '入院日期',
    `age` INT DEFAULT NULL,
    `marriage` VARCHAR(32) DEFAULT NULL,
    `occupation` VARCHAR(64) DEFAULT NULL,
    `allergy_history` TEXT,
    `admission_record` TEXT COMMENT '入院记录',
    `admission_count` INT DEFAULT NULL COMMENT '入院次数',
    `chief_complaint` TEXT COMMENT '主诉',
    `present_illness` TEXT COMMENT '现病史',
    `past_history` TEXT COMMENT '既往史',
    `personal_history` TEXT COMMENT '个人史',
    `family_history` TEXT COMMENT '家族史',
    `surgery_trauma_history` TEXT COMMENT '手术外伤史',
    `blood_transfusion_history` TEXT COMMENT '输血史',
    `marriage_childbirth_history` TEXT COMMENT '婚育史',
    `payment_method` VARCHAR(64) DEFAULT NULL COMMENT '医保付费方式',
    `physical_exam` TEXT COMMENT '体格检查',
    `specialist_exam` TEXT COMMENT '专科检查',
    `auxiliary_exam` TEXT COMMENT '辅助检查',
    `onset_solar_term` VARCHAR(32) DEFAULT NULL COMMENT '发病节气',
    `tcm_four_diagnosis` TEXT COMMENT '中医四诊',
    `admission_condition` TEXT COMMENT '入院情况',
    `western_treatment_plan` TEXT COMMENT '西医治疗计划',
    `tcm_treatment_plan` TEXT COMMENT '中医治疗计划',
    `emergency_western_diagnosis` VARCHAR(255) DEFAULT NULL COMMENT '门急诊诊断西医',
    `emergency_tcm_diagnosis` VARCHAR(255) DEFAULT NULL COMMENT '门急诊诊断中医',
    `admission_western_diagnosis` VARCHAR(255) DEFAULT NULL COMMENT '入院西医诊断',
    `admission_tcm_diagnosis` VARCHAR(255) DEFAULT NULL COMMENT '入院中医诊断',
    `diagnosis_basis_analysis` TEXT COMMENT '诊断依据中医辨病辨证分析',
    `admission_tcm_syndrome` VARCHAR(255) DEFAULT NULL COMMENT '入院中医证型',
    `admission_symptoms` TEXT COMMENT '入院症见',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_patient_id` (`patient_id`),
    KEY `idx_visit_no` (`visit_no`),
    KEY `idx_admission_date` (`admission_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='入院信息宽表';

-- ------------------------------------------------------------
-- 16. 业务数据: 出院信息宽表
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `discharges`;
CREATE TABLE `discharges` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `patient_id` VARCHAR(64) NOT NULL COMMENT '患者ID',
    `medical_record_no` VARCHAR(64) DEFAULT NULL COMMENT '病案号',
    `visit_no` VARCHAR(64) DEFAULT NULL COMMENT '就诊流水号',
    `age` INT DEFAULT NULL,
    `admission_date` DATE DEFAULT NULL,
    `discharge_date` DATE DEFAULT NULL,
    `length_of_stay` INT DEFAULT NULL COMMENT '住院天数',
    `admission_condition` TEXT COMMENT '入院情况',
    `disease_description` TEXT COMMENT '病情描述',
    `hospital_course` TEXT COMMENT '住院治疗经过',
    `western_treatment_course` TEXT COMMENT '西医诊疗经过',
    `tcm_treatment_course` TEXT COMMENT '中医诊疗经过',
    `discharge_western_diagnosis1` VARCHAR(255) DEFAULT NULL,
    `discharge_western_diagnosis2` VARCHAR(255) DEFAULT NULL,
    `discharge_western_diagnosis3` VARCHAR(255) DEFAULT NULL,
    `discharge_western_diagnosis4` VARCHAR(255) DEFAULT NULL,
    `discharge_western_diagnosis5` VARCHAR(255) DEFAULT NULL,
    `discharge_western_diagnosis6` VARCHAR(255) DEFAULT NULL,
    `discharge_western_diagnosis7` VARCHAR(255) DEFAULT NULL,
    `discharge_tcm_diagnosis` VARCHAR(255) DEFAULT NULL COMMENT '出院中医诊断',
    `discharge_tcm_syndrome` VARCHAR(255) DEFAULT NULL COMMENT '出院中医证型',
    `discharge_condition` TEXT COMMENT '出院情况',
    `discharge_orders` TEXT COMMENT '出院医嘱',
    `discharge_medication` TEXT COMMENT '出院用药医嘱',
    `discharge_diet` TEXT COMMENT '出院饮食医嘱',
    `discharge_other_orders` TEXT COMMENT '出院其他医嘱',
    `discharge_outcome` VARCHAR(128) DEFAULT NULL COMMENT '出院结局',
    `discharge_dept` VARCHAR(64) DEFAULT NULL COMMENT '出院科室',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_patient_id` (`patient_id`),
    KEY `idx_visit_no` (`visit_no`),
    KEY `idx_discharge_date` (`discharge_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='出院信息宽表';

SET FOREIGN_KEY_CHECKS = 1;
