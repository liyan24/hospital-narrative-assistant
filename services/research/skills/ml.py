"""机器学习类算子：分类、聚类、降维、特征重要性、回归。"""
import numpy as np
import pandas as pd

from services.research.dataset_service import dataset_service
from services.research.skills.base import (
    BaseSkill, SkillMeta, make_result, bar_option, horizontal_bar_option,
    line_option, scatter_option,
)

MIN_SAMPLES = 200  # 机器学习算子的最小样本量


def build_feature_matrix(top_n: int = 20, target: str | None = None) -> tuple[pd.DataFrame, pd.Series | None, list[str]]:
    """
    构建机器学习特征矩阵：年龄 + 诊断 TopN one-hot + 用药 TopN one-hot + 检验特征。
    target: "is_readmission" / "is_long_stay" / None
    """
    visits = dataset_service.build_visit_matrix()
    df = pd.DataFrame(index=visits.index)
    df["age_years"] = visits["age_years"]

    # 诊断 TopN one-hot
    top_diags = pd.Series([d for ds in visits["diagnoses"] for d in ds]).value_counts().head(top_n).index
    for d in top_diags:
        df[f"诊断_{d}"] = visits["diagnoses"].apply(lambda ds: int(d in ds))

    # 用药 TopN one-hot
    top_drugs = pd.Series([x for ds in visits["drugs"] for x in ds]).value_counts().head(top_n).index
    for d in top_drugs:
        df[f"用药_{d}"] = visits["drugs"].apply(lambda ds: int(d in ds))

    # 检验特征（缺失过多的列剔除，其余用中位数填补）
    lab_cols = [c for c in visits.columns if c.startswith("lab_")]
    for c in lab_cols:
        if visits[c].notna().mean() >= 0.1:
            df[c] = visits[c].fillna(visits[c].median())

    df["had_surgery"] = visits["had_surgery"].astype(int)

    y = None
    if target == "length_of_stay":
        y = visits["length_of_stay"]
    elif target in ("is_readmission", "is_long_stay"):
        y = visits[target].astype(int)

    valid = df["age_years"].notna()
    if target == "length_of_stay":
        valid = valid & y.notna()
    X = df[valid]
    y = y[valid] if y is not None else None
    feature_names = X.columns.tolist()
    return X, y, feature_names


def _insufficient_result(target_desc: str, n: int) -> dict:
    return make_result(
        f"可用样本量不足（当前 {n} 条，至少需 {MIN_SAMPLES} 条），"
        f"无法可靠地完成{target_desc}建模。建议先运行数据集画像了解数据覆盖情况。"
    )


class ClassificationSkill(BaseSkill):
    meta = SkillMeta(
        id="classification",
        name="分类预测（再入院/长住院）",
        category="机器学习",
        description="LogisticRegression 与 RandomForest 对比，预测再入院或长住院，输出 accuracy/AUC/混淆矩阵/特征重要性",
        params_schema=[
            {"name": "target", "label": "预测目标", "type": "select",
             "default": "is_readmission", "options": ["is_readmission", "is_long_stay"],
             "description": "is_readmission=是否多次就诊，is_long_stay=住院天数>P75"},
            {"name": "top_n", "label": "诊断/用药特征数", "type": "number",
             "default": 20, "min": 5, "max": 100},
            {"name": "test_size", "label": "测试集比例", "type": "number",
             "default": 0.3, "min": 0.1, "max": 0.5},
        ],
        data_requirements="就诊级宽表（年龄/诊断/用药/检验）",
    )

    def run(self, params: dict) -> dict:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import accuracy_score, confusion_matrix, roc_auc_score
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler

        target = self.get_param(params, "target")
        top_n = int(self.get_param(params, "top_n"))
        test_size = float(self.get_param(params, "test_size"))
        target_label = "再入院" if target == "is_readmission" else "长住院"

        X, y, feature_names = build_feature_matrix(top_n=top_n, target=target)
        if len(X) < MIN_SAMPLES:
            return _insufficient_result(f"{target_label}分类", len(X))
        if y.nunique() < 2:
            return make_result(f"目标变量 {target} 只有一个类别，无法进行分类建模。")

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y)

        scaler = StandardScaler()
        lr = LogisticRegression(max_iter=1000)
        lr.fit(scaler.fit_transform(X_train), y_train)
        lr_pred = lr.predict(scaler.transform(X_test))
        lr_prob = lr.predict_proba(scaler.transform(X_test))[:, 1]

        rf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        rf.fit(X_train, y_train)
        rf_pred = rf.predict(X_test)
        rf_prob = rf.predict_proba(X_test)[:, 1]

        def safe_auc(prob):
            try:
                return round(roc_auc_score(y_test, prob), 3)
            except ValueError:
                return None

        metrics = [
            ["LogisticRegression", round(accuracy_score(y_test, lr_pred), 3), safe_auc(lr_prob)],
            ["RandomForest", round(accuracy_score(y_test, rf_pred), 3), safe_auc(rf_prob)],
        ]
        cm = confusion_matrix(y_test, rf_pred)
        cm_rows = [[f"实际{cls}", *[int(v) for v in row]] for cls, row in zip(sorted(y.unique()), cm)]

        importances = pd.Series(rf.feature_importances_, index=feature_names).sort_values(ascending=False)
        top_imp = importances.head(15)

        tables = [
            {"title": "模型性能对比", "columns": ["模型", "Accuracy", "AUC"], "rows": metrics},
            {"title": "RandomForest 混淆矩阵",
             "columns": ["", *[f"预测{c}" for c in sorted(y.unique())]], "rows": cm_rows},
            {"title": "特征重要性 Top15", "columns": ["特征", "重要性"],
             "rows": [[k, round(v, 4)] for k, v in top_imp.items()]},
        ]
        charts = [{"title": "特征重要性", "option": horizontal_bar_option(
            f"{target_label}预测特征重要性 Top15",
            top_imp.index.tolist()[::-1], [round(v, 4) for v in top_imp.tolist()[::-1]], "重要性")}]

        pos_rate = y.mean()
        summary = (
            f"使用 {len(X)} 次就诊样本（{target_label}阳性率 {pos_rate:.1%}）训练二分类模型："
            f"RandomForest Accuracy={metrics[1][1]}、AUC={metrics[1][2]}；"
            f"LogisticRegression Accuracy={metrics[0][1]}、AUC={metrics[0][2]}。"
            f"最重要的预测特征为「{top_imp.index[0]}」（重要性 {top_imp.iloc[0]:.3f}）。"
            "提示：本结果为回顾性关联分析，特征重要性不代表因果关系。"
        )
        facts = {
            "target": target,
            "sample_count": len(X),
            "positive_rate": float(pos_rate),
            "metrics": {"logistic": {"accuracy": metrics[0][1], "auc": metrics[0][2]},
                        "random_forest": {"accuracy": metrics[1][1], "auc": metrics[1][2]}},
            "top_features": {k: float(v) for k, v in top_imp.head(10).items()},
        }
        return make_result(summary, tables, charts, facts)


class ClusteringSkill(BaseSkill):
    meta = SkillMeta(
        id="clustering",
        name="就诊聚类分群",
        category="机器学习",
        description="KMeans 聚类 + PCA 二维散点着色 + 各群画像对比表",
        params_schema=[
            {"name": "k", "label": "聚类数 k", "type": "number",
             "default": 3, "min": 2, "max": 10},
            {"name": "top_n", "label": "诊断/用药特征数", "type": "number",
             "default": 20, "min": 5, "max": 100},
        ],
        data_requirements="就诊级宽表（年龄/诊断/用药/检验）",
    )

    def run(self, params: dict) -> dict:
        from sklearn.cluster import KMeans
        from sklearn.decomposition import PCA
        from sklearn.preprocessing import StandardScaler

        k = int(self.get_param(params, "k"))
        top_n = int(self.get_param(params, "top_n"))

        X, _, feature_names = build_feature_matrix(top_n=top_n)
        if len(X) < MIN_SAMPLES:
            return _insufficient_result("聚类", len(X))

        X_scaled = StandardScaler().fit_transform(X)
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X_scaled)

        # PCA 二维散点（抽样）
        pca = PCA(n_components=2, random_state=42)
        coords = pca.fit_transform(X_scaled)
        plot_idx = np.random.RandomState(42).choice(len(coords), min(3000, len(coords)), replace=False)
        series = []
        for c in range(k):
            pts = coords[plot_idx][labels[plot_idx] == c]
            series.append({"name": f"群{c}", "type": "scatter", "symbolSize": 5,
                           "itemStyle": {"opacity": 0.5}, "data": pts.tolist()})
        option = scatter_option("KMeans 聚类（PCA 二维投影）", [], "PC1", "PC2")
        option["series"] = series
        option["legend"] = {"top": "bottom"}

        # 各群画像
        visits = dataset_service.build_visit_matrix().loc[X.index].copy()
        visits["cluster"] = labels
        profile_rows = []
        for c in range(k):
            grp = visits[visits["cluster"] == c]
            top_diag = pd.Series([d for ds in grp["diagnoses"] for d in ds]).value_counts().head(3)
            profile_rows.append([
                f"群{c}", len(grp),
                round(grp["age_years"].mean(), 1),
                round(grp["length_of_stay"].median(), 1),
                f"{grp['is_readmission'].mean():.1%}",
                "、".join(top_diag.index.tolist()),
            ])
        sizes = pd.Series(labels).value_counts().sort_index()

        tables = [{
            "title": "各群画像对比",
            "columns": ["群组", "就诊数", "平均年龄(岁)", "住院天数中位数", "再入院率", "Top3诊断"],
            "rows": profile_rows,
        }]
        charts = [
            {"title": "聚类散点图", "option": option},
            {"title": "各群规模", "option": bar_option("各群就诊数",
             [f"群{c}" for c in sizes.index], sizes.tolist(), "", "就诊数")},
        ]

        biggest = max(profile_rows, key=lambda r: r[1])
        summary = (
            f"对 {len(X)} 次就诊进行 KMeans（k={k}）聚类，"
            f"最大群为{biggest[0]}（{biggest[1]} 次，占 {biggest[1]/len(X):.1%}），"
            f"其平均年龄 {biggest[2]} 岁、住院天数中位数 {biggest[3]} 天、再入院率 {biggest[4]}，"
            f"主要诊断为{biggest[5]}。各群画像详见对比表。"
        )
        facts = {
            "k": k,
            "sample_count": len(X),
            "cluster_sizes": {f"群{c}": int(s) for c, s in sizes.items()},
            "cluster_profiles": [
                {"cluster": r[0], "size": r[1], "age_mean": r[2], "los_median": r[3],
                 "readmission_rate": r[4], "top_diagnoses": r[5]}
                for r in profile_rows
            ],
        }
        return make_result(summary, tables, charts, facts)


class DimensionalityReductionSkill(BaseSkill):
    meta = SkillMeta(
        id="dimensionality_reduction",
        name="主成分分析（PCA）",
        category="机器学习",
        description="PCA 降维，展示各主成分解释方差比（柱状）与累计解释方差（折线）",
        params_schema=[
            {"name": "n_components", "label": "主成分数", "type": "number",
             "default": 10, "min": 2, "max": 30},
            {"name": "top_n", "label": "诊断/用药特征数", "type": "number",
             "default": 20, "min": 5, "max": 100},
        ],
        data_requirements="就诊级宽表（年龄/诊断/用药/检验）",
    )

    def run(self, params: dict) -> dict:
        from sklearn.decomposition import PCA
        from sklearn.preprocessing import StandardScaler

        n_components = int(self.get_param(params, "n_components"))
        top_n = int(self.get_param(params, "top_n"))

        X, _, feature_names = build_feature_matrix(top_n=top_n)
        if len(X) < MIN_SAMPLES:
            return _insufficient_result("PCA 降维", len(X))

        n_components = min(n_components, X.shape[1])
        X_scaled = StandardScaler().fit_transform(X)
        pca = PCA(n_components=n_components, random_state=42)
        pca.fit(X_scaled)

        ratio = pca.explained_variance_ratio_
        cum = np.cumsum(ratio)
        labels = [f"PC{i+1}" for i in range(n_components)]

        n_90 = int(np.argmax(cum >= 0.9) + 1) if (cum >= 0.9).any() else n_components

        tables = [{
            "title": "主成分解释方差",
            "columns": ["主成分", "解释方差比", "累计解释方差"],
            "rows": [[labels[i], round(ratio[i], 4), round(cum[i], 4)] for i in range(n_components)],
        }]
        charts = [
            {"title": "解释方差比", "option": bar_option("各主成分解释方差比",
             labels, [round(r, 4) for r in ratio], "", "解释方差比")},
            {"title": "累计解释方差", "option": line_option("累计解释方差",
             labels, [round(c, 4) for c in cum], "", "累计解释方差比")},
        ]

        summary = (
            f"对 {X.shape[1]} 维特征进行 PCA：第一主成分解释方差比 {ratio[0]:.1%}，"
            f"前 {n_components} 个主成分累计解释 {cum[-1]:.1%} 方差，"
            f"达到 90% 累计解释方差需要 {n_90} 个主成分。"
        )
        facts = {
            "n_features": X.shape[1],
            "pc1_ratio": float(ratio[0]),
            "cumulative_ratio": [float(c) for c in cum],
            "components_for_90pct": n_90,
        }
        return make_result(summary, tables, charts, facts)


class FeatureImportanceSkill(BaseSkill):
    meta = SkillMeta(
        id="feature_importance",
        name="特征重要性排行",
        category="机器学习",
        description="RandomForest 特征重要性 Top20（默认以再入院为目标）",
        params_schema=[
            {"name": "target", "label": "预测目标", "type": "select",
             "default": "is_readmission", "options": ["is_readmission", "is_long_stay"]},
            {"name": "top_n", "label": "诊断/用药特征数", "type": "number",
             "default": 30, "min": 5, "max": 100},
        ],
        data_requirements="就诊级宽表（年龄/诊断/用药/检验）",
    )

    def run(self, params: dict) -> dict:
        from sklearn.ensemble import RandomForestClassifier

        target = self.get_param(params, "target")
        top_n = int(self.get_param(params, "top_n"))
        target_label = "再入院" if target == "is_readmission" else "长住院"

        X, y, feature_names = build_feature_matrix(top_n=top_n, target=target)
        if len(X) < MIN_SAMPLES:
            return _insufficient_result("特征重要性分析", len(X))
        if y.nunique() < 2:
            return make_result(f"目标变量 {target} 只有一个类别，无法训练模型。")

        rf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        rf.fit(X, y)
        importances = pd.Series(rf.feature_importances_, index=feature_names).sort_values(ascending=False)
        top = importances.head(20)

        tables = [{
            "title": f"{target_label}相关特征重要性 Top20",
            "columns": ["排名", "特征", "重要性"],
            "rows": [[i + 1, k, round(v, 4)] for i, (k, v) in enumerate(top.items())],
        }]
        charts = [{"title": "特征重要性 Top20", "option": horizontal_bar_option(
            f"{target_label}特征重要性 Top20",
            top.index.tolist()[::-1], [round(v, 4) for v in top.tolist()[::-1]], "重要性")}]

        summary = (
            f"以{target_label}为目标训练 RandomForest（{len(X)} 样本、{X.shape[1]} 特征），"
            f"重要性最高的三个特征为：{'、'.join(top.index[:3])}。"
            "特征重要性反映预测贡献，不等于临床因果。"
        )
        facts = {"target": target, "top_features": {k: float(v) for k, v in top.items()}}
        return make_result(summary, tables, charts, facts)


class RegressionSkill(BaseSkill):
    meta = SkillMeta(
        id="regression",
        name="住院天数预测（回归）",
        category="机器学习",
        description="Ridge 与 RandomForest 回归对比，预测住院天数，输出 MAE/R²",
        params_schema=[
            {"name": "top_n", "label": "诊断/用药特征数", "type": "number",
             "default": 20, "min": 5, "max": 100},
            {"name": "test_size", "label": "测试集比例", "type": "number",
             "default": 0.3, "min": 0.1, "max": 0.5},
        ],
        data_requirements="就诊级宽表（年龄/诊断/用药/检验/住院天数）",
    )

    def run(self, params: dict) -> dict:
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.linear_model import Ridge
        from sklearn.metrics import mean_absolute_error, r2_score
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler

        top_n = int(self.get_param(params, "top_n"))
        test_size = float(self.get_param(params, "test_size"))

        X, y, feature_names = build_feature_matrix(top_n=top_n, target="length_of_stay")
        if len(X) < MIN_SAMPLES:
            return _insufficient_result("住院天数回归", len(X))

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42)

        scaler = StandardScaler()
        ridge = Ridge()
        ridge.fit(scaler.fit_transform(X_train), y_train)
        ridge_pred = ridge.predict(scaler.transform(X_test))

        rf = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        rf.fit(X_train, y_train)
        rf_pred = rf.predict(X_test)

        metrics = [
            ["Ridge", round(mean_absolute_error(y_test, ridge_pred), 2), round(r2_score(y_test, ridge_pred), 3)],
            ["RandomForest", round(mean_absolute_error(y_test, rf_pred), 2), round(r2_score(y_test, rf_pred), 3)],
        ]

        importances = pd.Series(rf.feature_importances_, index=feature_names).sort_values(ascending=False).head(15)

        tables = [
            {"title": "回归模型性能对比", "columns": ["模型", "MAE(天)", "R²"], "rows": metrics},
            {"title": "特征重要性 Top15", "columns": ["特征", "重要性"],
             "rows": [[k, round(v, 4)] for k, v in importances.items()]},
        ]
        charts = [{"title": "特征重要性", "option": horizontal_bar_option(
            "住院天数预测特征重要性 Top15",
            importances.index.tolist()[::-1], [round(v, 4) for v in importances.tolist()[::-1]], "重要性")}]

        summary = (
            f"使用 {len(X)} 次就诊样本预测住院天数（均值 {y.mean():.1f} 天，标准差 {y.std():.1f}）："
            f"RandomForest MAE={metrics[1][1]} 天、R²={metrics[1][2]}；"
            f"Ridge MAE={metrics[0][1]} 天、R²={metrics[0][2]}。"
            f"最重要特征为「{importances.index[0]}」。"
            "R² 偏低说明住院天数受非结构化因素（病情变化、出院安排等）影响较大。"
        )
        facts = {
            "sample_count": len(X),
            "los_mean": float(y.mean()),
            "metrics": {"ridge": {"mae": metrics[0][1], "r2": metrics[0][2]},
                        "random_forest": {"mae": metrics[1][1], "r2": metrics[1][2]}},
            "top_features": {k: float(v) for k, v in importances.head(10).items()},
        }
        return make_result(summary, tables, charts, facts)


classification_skill = ClassificationSkill()
clustering_skill = ClusteringSkill()
dimensionality_reduction_skill = DimensionalityReductionSkill()
feature_importance_skill = FeatureImportanceSkill()
regression_skill = RegressionSkill()
