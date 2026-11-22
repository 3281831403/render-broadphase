# render-broadphase

## 题面

物理宽阶段换成 SAP 后，贴着的箱子判不出碰撞、候选对还重复：sweep 的端点排序在相同坐标时按类型排序错，把 max 排在 min 前，接触的盒被判分离；sweep 的活动集合用列表加 remove，删除第一个同 id 项，重复项让候选对漏掉；sweep 不做结果去重，同一对被返回两次，破坏顺序断言；hash_cells 的单元索引用 int(x/cell) 但边界含右端点，AABB 跨单元重复计入；hash_cells 对大 AABB 返回全部单元格，没有 MAX_CELLS 上限，内存爆炸；grid_pairs 把哈希桶写成单个 dict 值（id），同一单元里的多个箱子互相覆盖，碰撞时漏对；dedupe_pairs 不归一化 (a,b)/(b,a)，无序对重复；incremental 只重算移动物体的新单元，不重算旧单元，遗留旧对；validate_pairs 只查 id 不查 AABB 是否真的相交，假阳性未被报；broadphase_batch 复用网格，第二帧沿用第一帧的单元映射。难点是一致性：端点同值时类型顺序、单元半开区间、无序对归一化。broadphase/sap.py 是核心，tests/test_sap.py 15个红。要修的是：…

## 运行方式

在仓库根目录执行：

```powershell
python -m pytest tests -q
```

初始状态必须恰好得到 `15 failed`，且没有 collection error、import error 或 syntax error。15 个失败都来自 `broadphase/sap.py` 的 `NotImplementedError`；实现 8 个桩后应变为 `15 passed`。

输出尾部形如：

```text
15 failed in 0.05s
```

依赖只有 Python 3 标准库和 pytest，离线运行，不使用随机数。

## 字段表

| 字段 | 取值 |
| --- | --- |
| 所属领域 | 游戏、图形与多媒体 |
| 子方向 | 图形渲染 |
| 任务类型 | Bugfix |
| 语言/框架 | Python 3, pytest |
| 环境可复现等级 | 无外部依赖 |

## 不可修改

`tests/test_sap.py` 是评分测试，不可修改。不要通过改测试、加 `skip`/`xfail`、放宽断言或替换 `conftest.py` 来制造绿色；修复必须发生在 `broadphase/sap.py`。

## 实现契约

8 个公开函数——`sort_endpoints`、`sweep`、`hash_cells`、`grid_pairs`、`dedupe_pairs`、`incremental`、`validate_pairs`、`broadphase_batch`——当前全部 `raise NotImplementedError`。AABB 用 `{"id": int, "min": (x, y), "max": (x, y)}` 表示；AABB 相交按闭区间处理，边界相切也算相交；网格单元按半开区间 `[k*cell, (k+1)*cell)` 覆盖；几何比较容差为 `1e-9`；候选对统一归一化为 `(min(a,b), max(a,b))` 并排序去重。逐函数细节见 `broadphase/sap.py` 的 docstring。
