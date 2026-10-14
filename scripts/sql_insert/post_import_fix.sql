-- 导入后修正：源库 admissions 表结构与本地不一致（列错位），
-- 该患者数据的诊断/证型实际落在 emergency_* 与 admission_symptoms 列中。
-- 仅作用于本次新导入的患者，不影响存量数据。
-- 执行: python -c 见 scripts/run_sql_insert.py 或用任意 MySQL 客户端执行本文件

UPDATE `admissions`
SET
  `admission_western_diagnosis` = `emergency_western_diagnosis`,
  `admission_tcm_diagnosis` = `emergency_tcm_diagnosis`,
  `admission_tcm_syndrome` = `admission_symptoms`,
  `marriage` = `marriage_childbirth_history`,
  `emergency_western_diagnosis` = NULL,
  `emergency_tcm_diagnosis` = NULL,
  `admission_symptoms` = NULL,
  `marriage_childbirth_history` = NULL
WHERE `patient_id` = '557c91116af011f19de2d488664b66d4';
