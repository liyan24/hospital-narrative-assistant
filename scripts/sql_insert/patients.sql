/*
 增量数据导入（由 transform_sql_insert.py 从 Navicat 导出改写）
 仅含 INSERT，不含 DROP/CREATE，不会破坏原有表结构与数据
 目标库: hna    执行: python scripts/run_sql_insert.py
*/

SET FOREIGN_KEY_CHECKS=0;

INSERT INTO `patients` (`patient_id`, `medical_record_no`, `age`, `gender`, `marriage`, `occupation`, `allergy_history`, `created_at`, `updated_at`) VALUES ('557c91116af011f19de2d488664b66d4', '', '0', '男', '未知', '职员', '未知', '2026-09-26 21:56:31', '2026-09-26 21:56:31');
