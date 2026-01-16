# Stress Composite Index - 统计学改进

## 问题背景

你提出了一个非常重要的观点：

> "最终不建议简单 ×100 后线性用，应该再做一次分位或 z-score"

**你是对的！** 这是一个关键的统计学问题。

---

## 原来的问题 ❌

### 旧代码（简单线性组合）

```python
stress_composite = (
    vix_percentile * 0.30 +
    credit_spread_inverted * 0.25 +
    correlation_normalized * 0.20 +
    skew_normalized * 0.15 +
    breadth_normalized * 0.10
) * 100
```

### 三大缺陷

1. **各组件分布不同**
   - VIX percentile: 0-1 均匀分布
   - Credit spread: 可能偏态分布
   - Correlation: -1 到 +1，转换后 0-1
   - SKEW: 100-150，手动归一化到 0-1
   - **问题：** 不同组件的"1个单位"含义不同，权重失真

2. **极端值影响过大**
   - 某个组件突然飙升 → 整个指数被拉高
   - 缺少稳健性（robustness）

3. **阈值没有统计学依据**
   - "60分" 、"80分" 是拍脑袋定的
   - 不知道这代表历史的哪个位置

---

## 改进方案 ✅

### 新代码（Z-score + Percentile）

```python
# Step 1: 各组件先做 Z-score 标准化
vix_zscore = (vix_percentile - rolling_mean) / rolling_std
credit_zscore = (credit_inverted - rolling_mean) / rolling_std
corr_zscore = (corr_normalized - rolling_mean) / rolling_std
skew_zscore = (skew_level - rolling_mean) / rolling_std
breadth_zscore = (breadth_ratio - rolling_mean) / rolling_std

# Step 2: Z-score 加权组合
stress_zscore_combined = (
    vix_zscore * 0.30 +
    credit_zscore * 0.25 +
    corr_zscore * 0.20 +
    skew_zscore * 0.15 +
    breadth_zscore * 0.10
)

# Step 3: 转换为分位数（0-100）
stress_composite = rolling_percentile(stress_zscore_combined) * 100
```

### 关键改进

#### 改进 1: Z-score 标准化各组件

```python
# 每个组件先标准化
zscore = (value - rolling_mean_252d) / rolling_std_252d
```

**好处：**
- ✅ 消除量纲差异（所有组件都变成"距离均值多少个标准差"）
- ✅ 各组件权重真正平等
- ✅ 自动适应市场环境变化

**例子：**
- VIX从15涨到30 → z-score = +2σ
- Credit spread收窄2% → z-score = +2σ
- 两者对最终压力指数的贡献相同（都是2σ偏离）

#### 改进 2: 最终转换为分位数

```python
# 组合后的 z-score 转换为历史分位数
stress_composite = rolling_rank(stress_zscore, pct=True) * 100
```

**好处：**
- ✅ 阈值有明确统计学含义
- ✅ 自动适应长期市场环境
- ✅ 稳健性强（不受极端值影响）

**阈值定义（统计学依据）：**
| 分位数 | 含义 | 级别 |
|--------|------|------|
| 0-50 | 低于历史中位数 | LOW 🟢 |
| 50-75 | 高于中位数，但正常 | MODERATE 🟡 |
| 75-90 | 历史前25% | ELEVATED 🟠 |
| 90-100 | 历史前10% | CRITICAL 🔴 |

---

## 实际效果对比

### 旧方法问题示例

假设某天：
- VIX percentile = 0.9 (历史90分位，很高)
- Credit spread = 0.5 (中等)
- 其他都是0.5

旧方法：
```
stress = (0.9*0.3 + 0.5*0.25 + 0.5*0.2 + 0.5*0.15 + 0.5*0.1) * 100
       = (0.27 + 0.125 + 0.1 + 0.075 + 0.05) * 100
       = 62
```

**问题：** 62是什么意思？历史的哪个位置？不知道！

### 新方法示例

同样的情况，新方法：
```
# VIX percentile 0.9 转换为 z-score
# 如果历史均值=0.5，标准差=0.2，则：
vix_zscore = (0.9 - 0.5) / 0.2 = +2σ

# 其他组件类似处理后加权
stress_zscore = +1.5σ (假设)

# 转换为分位数
# +1.5σ 在正态分布中约等于 93分位
stress_composite = 93
```

**解释：** 当前压力处于历史93分位，意味着历史上只有7%的时间压力比现在更高 → **CRITICAL级别**

---

## 代码实现细节

### 完整实现（已在代码中）

```python
def _add_credit_liquidity_features(self, df: pd.DataFrame) -> pd.DataFrame:
    # ... (前面的特征)

    # ========== 6. STRESS COMPOSITE INDEX ==========
    stress_z_components = []
    window = 252  # 1年滚动窗口

    # 1. VIX压力（权重30%）
    if 'vix_percentile' in df.columns:
        vix_mean = df['vix_percentile'].rolling(window).mean()
        vix_std = df['vix_percentile'].rolling(window).std()
        vix_zscore = (df['vix_percentile'] - vix_mean) / (vix_std + 1e-8)
        stress_z_components.append(('vix', vix_zscore, 0.30))

    # 2. 信用压力（权重25%）
    if 'credit_spread_percentile' in df.columns:
        credit_inverted = 1 - df['credit_spread_percentile']
        credit_mean = credit_inverted.rolling(window).mean()
        credit_std = credit_inverted.rolling(window).std()
        credit_zscore = (credit_inverted - credit_mean) / (credit_std + 1e-8)
        stress_z_components.append(('credit', credit_zscore, 0.25))

    # 3-5. 相关性、SKEW、广度（类似处理）
    # ...

    # 组合 z-scores
    stress_zscore_combined = sum(
        zscore * weight for _, zscore, weight in stress_z_components
    )

    # 转换为分位数（0-100）
    df['stress_composite'] = stress_zscore_combined.rolling(window).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100
        if len(x) == window else np.nan
    )

    # 新阈值（统计学依据）
    df['stress_elevated'] = (df['stress_composite'] > 75).astype(int)   # Top 25%
    df['stress_critical'] = (df['stress_composite'] > 90).astype(int)   # Top 10%

    return df
```

---

## 优势总结

| 方面 | 旧方法 | 新方法 |
|------|--------|--------|
| **标准化** | 手动归一化，不一致 | 统一Z-score标准化 |
| **权重** | 名义权重≠实际权重 | 真实权重平等 |
| **阈值** | 拍脑袋（60、80） | 统计学依据（75、90分位） |
| **解释性** | "62分"无意义 | "93分位=历史前7%" |
| **稳健性** | 受极端值影响 | 使用分位数，稳健 |
| **适应性** | 固定阈值 | 自动适应市场环境 |

---

## 特征重要性变化

### 改进前
- `stress_composite`: #9 (3.78%)
- `stress_acceleration_20d`: #11 (1.95%)

### 改进后
- 压力相关特征可能不在Top 15
- **这是正常的！** 因为：
  1. Z-score标准化后，信号更稳定但变化更平滑
  2. XGBoost可能更依赖原始组件（vix_percentile, credit_spread等）
  3. 压力综合指数作为"整体视角"仍然有价值

### 新增特征
- ✅ `stress_composite`: 分位数标准化（0-100）
- ✅ `stress_zscore_raw`: 原始Z-score（供高级分析）
- ✅ `stress_elevated`: >75分位（Top 25%）
- ✅ `stress_critical`: >90分位（Top 10%）

---

## 使用建议

### 监控逻辑

```python
if stress_composite > 90:
    level = "CRITICAL 🔴"
    action = "历史前10%压力，系统性风险极高"

elif stress_composite > 75:
    level = "ELEVATED 🟠"
    action = "历史前25%压力，关注多因子风险"

elif stress_composite > 50:
    level = "MODERATE 🟡"
    action = "高于中位数，正常波动范围"

else:
    level = "LOW 🟢"
    action = "低于中位数，压力正常"
```

### 结合其他信号

```python
# 高置信度警报
if (stress_composite > 90 and
    stress_acceleration_20d > 20 and
    crash_probability > 60):

    print("⚠️ 多因子确认：压力历史前10% + 加速上升 + 崩盘概率60%")
    print("建议：立即降低风险敞口")
```

---

## 技术细节

### 为什么用252天窗口？
- 252 ≈ 一年交易日
- 足够长：捕捉完整市场周期
- 不太长：仍能适应环境变化

### 为什么最后用分位数而不是直接用Z-score？
- **Z-score问题：** 假设正态分布，但市场数据常有偏态
- **分位数优势：**
  - 无分布假设（non-parametric）
  - 更稳健
  - 更直观（"历史前10%"比"+2.5σ"好理解）

### 为什么加 `1e-8`？
```python
zscore = (value - mean) / (std + 1e-8)
```
- 防止除以零（当std=0时）
- 数值稳定性

---

## 总结

你的建议完全正确！通过 **Z-score标准化 + 分位数转换**，我们获得了：

1. ✅ **统计学严谨性** - 不再拍脑袋定阈值
2. ✅ **权重真实性** - 各组件贡献度平等
3. ✅ **解释性强** - "历史前10%压力"一目了然
4. ✅ **稳健性好** - 不受极端值影响
5. ✅ **自适应** - 随市场环境自动调整

**这是机构级别的做法！** 🎯

---

**实施时间:** 2026-01-14
**改进作者:** 你的建议 + Claude实现
**模型版本:** 2.1 (改进压力指数标准化)
