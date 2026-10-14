/*
 增量数据导入（由 transform_sql_insert.py 从 Navicat 导出改写）
 仅含 INSERT，不含 DROP/CREATE，不会破坏原有表结构与数据
 目标库: hna    执行: python scripts/run_sql_insert.py
*/

SET FOREIGN_KEY_CHECKS=0;

INSERT INTO `exams` (`patient_id`, `visit_no`, `apply_dept`, `exam_part`, `exam_no`, `description`, `diagnosis`, `exam_date`, `report_date`, `medical_record_no`, `diagnosis1`, `diagnosis2`, `diagnosis3`, `diagnosis4`, `diagnosis5`, `standard_name`, `standard_code`, `standard_category`, `created_at`) VALUES ('557c91116af011f19de2d488664b66d4', '202507778187', '放射科', null, null, '    双肺上、下叶见多发结节，较大者位于左肺下叶前内基底段（IM241）为实性结节，大小约为5mm×3mm，左肺下叶可见钙化灶，双肺可见囊状影，双肺可见条索状高密度影，气管及双侧主支气管通畅；纵隔无移位，纵隔内未见肿大的淋巴结，未见胸腔积液；心脏未见增大，冠脉走形区可见钙化影。左肾可见类圆形稍高密度影。', '    1.双肺小结节，建议动态观察。\n    2.双肺陈旧性病灶。\n    3.双肺肺气肿。\n    4.冠脉钙化。\n    5.左肾稍高密度影，必要时腹部进一步检查。', null, null, null, null, null, null, null, null, null, null, null, '2026-09-26 21:56:34');
INSERT INTO `exams` (`patient_id`, `visit_no`, `apply_dept`, `exam_part`, `exam_no`, `description`, `diagnosis`, `exam_date`, `report_date`, `medical_record_no`, `diagnosis1`, `diagnosis2`, `diagnosis3`, `diagnosis4`, `diagnosis5`, `standard_name`, `standard_code`, `standard_category`, `created_at`) VALUES ('557c91116af011f19de2d488664b66d4', '202507778187', '放射科', null, null, '    双侧基底节及右侧侧脑室体旁见多发点片状异常信号，呈脑脊液信号，黑水像上其周边可见稍高信号环绕，未见扩散受限。双侧侧脑室周围及大脑深部白质区可见多发点片状异常信号，T1WI呈等或稍低信号，T2WI及黑水像呈稍高信号。脑室系统未见扩张、变形及移位。中线结构居中。垂体、脑干、视交叉、双侧听神经干未见明显异常。双侧筛窦粘膜增厚。\n    脑MRA示：双侧大脑前动脉、双侧大脑中动脉、双侧大脑后动脉、双侧颈内动脉颅内段、双侧椎-基底动脉走形迂曲僵硬，管腔粗细不均匀，管壁毛糙，远端显影浅淡。颅内未见异常血管团。\n\n\n\n\n\n', '    1.双侧基底节及右侧侧脑室体旁腔隙性脑梗塞。\n    2.双侧脑白质高信号（Fazekas 1级）。\n    3.双侧筛窦炎。\n    4.脑MRA提示：脑动脉硬化性改变，请结合临床及CTA、DSA等检查协诊。\n\n\n\n\n\n', null, null, null, null, null, null, null, null, null, null, null, '2026-09-26 21:56:34');
