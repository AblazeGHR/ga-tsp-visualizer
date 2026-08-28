# GA-TSP-Visualizer

> 遗传算法解 TSP（旅行商问题）的最小可复现演示：纯 GA vs GA+2-opt 局部搜索，附收敛曲线、最优路径、2-opt 改进前后对比共五张图。

## 一句话介绍

用遗传算法（锦标赛选择 + 顺序交叉 OX + 交换变异 + 精英保留）解小规模 TSP（Traveling Salesman Problem，旅行商问题），对比纯 GA 与 GA+2-opt 的差距。

## 方法说明

### 1. TSP 编码
- 个体 = 城市的一个排列，路径 = 个体首尾相连
- 适应度 = 回路总长度（欧氏距离，越短越好）

### 2. 遗传算子
- **选择**：锦标赛选择（k=3），从种群中随机抽 3 个取最优
- **交叉**：顺序交叉 OX（Order Crossover），保留父本 1 的一段连续子路径，其余按父本 2 的顺序填入
- **变异**：交换变异，每个位置以 0.1 概率与随机位置交换
- **精英保留**：最优的 2 个个体直接进入下一代

### 3. 2-opt 局部搜索
对路径上两对边 (i,i+1) 与 (j,j+1)，若换成 (i,j) 与 (i+1,j+1) 更短，则反转 i+1..j 这一段。循环扫描直到一轮内不再改进。本项目支持两种使用方式：
- **GA+2-opt（进化期使用）**：每个新生个体都过一次 2-opt
- **后处理 2-opt**：对纯 GA 的最终结果跑一次 2-opt

### 4. 基准
- n ≤ 10：穷举所有排列求精确最优解
- n = 20：调用 OR-Tools（约束规划库，10s 时限）求精确/近优解

## 快速开始

**完整运行命令**（E 盘 miniforge 环境）：

```bash
# 1) 安装基础依赖（必需）
E:/software/miniforge/python.exe -m pip install -r requirements.txt

# 2) 可选：装 OR-Tools 让 n=20 也有精确/近优基准（不装则 n=20 gap 字段不显示）
E:/software/miniforge/python.exe -m pip install ortools

# 3) 跑演示
cd "D:/notes/Ablaze/pages/理工/计算机/申请导师快速练习项目/ga-tsp-visualizer"
E:/software/miniforge/python.exe main.py
```

可选参数：
- `--seed 42`        随机种子（默认 42）
- `--n1 10`          小规模城市数（≤ 10 走穷举基准）
- `--n2 20`          大规模城市数（> 10 走 OR-Tools 基准）
- `--pop-size 100`   种群大小
- `--generations 300` 进化代数

脚本会依次跑两个规模的随机 TSP 实例（同一随机种子，保证对比公平），在 `results/` 目录下生成 5 张图：
- `convergence_n10.png` / `convergence_n20.png`：收敛曲线（最优成本 vs 代数，纯 GA 与 GA+2-opt 对比）
- `best_route_n10.png` / `best_route_n20.png`：GA+2-opt 最优路径图
- `two_opt_compare_n20.png`：n=20 纯 GA 与施加 2-opt 后回路并排对比

## 运行结果（seed=42, pop_size=100, generations=300, mutation_rate=0.1）

| 实例规模 | 基准（来源） | 纯 GA 成本 | 纯 GA gap | GA+2-opt 成本 | GA+2-opt gap | 纯 GA + 后处理 2-opt | 后处理 gap |
| --- | --- | --- | --- | --- | --- | --- | --- |
| n=10 | 2.6414（穷举精确解） | 2.6414 | **0.00%** | 2.6414 | **0.00%** | 2.6414 | **0.00%** |
| n=20 | 3.5232（OR-Tools） | 4.4582 | **26.54%** | 3.5232 | **0.00%** | 3.6271 | **2.95%** |

**收敛速度（首次达到终代最优的代数）**：

| 实例规模 | 纯 GA | GA+2-opt |
| --- | --- | --- |
| n=10 | 第 22 代 | 第 0 代（2-opt 在初始种群即达到） |
| n=20 | 第 278 代 | 第 0 代 |

**耗时**（E 盘 miniforge / pop=100 / gen=300）：

| 实例规模 | 纯 GA | GA+2-opt |
| --- | --- | --- |
| n=10 | 0.2 s | 0.8 s |
| n=20 | 0.2 s | 4.8 s |

### 一句话结论
- 小规模（n=10）下纯 GA 在 22 代即稳定收敛到精确最优。
- 中等规模（n=20）下纯 GA 距最优仍有 **26.5%** gap；每代施加 2-opt 后立即达到 OR-Tools 同等解（0% gap）。
- 仅对终解做一次 2-opt 后处理也可将 gap 从 26.5% 压到 2.95%——印证 **GA 负责全局探索、2-opt 负责局部精修** 的经典思路。

## 文件结构

```
ga-tsp-visualizer/
├── main.py              # 命令行入口与作图
├── tsp_ga.py            # 遗传算子、2-opt、solve_tsp 复用接口
├── requirements.txt     # numpy / matplotlib / (可选) ortools
├── README.md
└── results/             # 运行后生成
    ├── convergence_n10.png
    ├── convergence_n20.png
    ├── best_route_n10.png
    ├── best_route_n20.png
    └── two_opt_compare_n20.png
```

## 复现建议

`tsp_ga.py` 的 `solve_tsp` 接口是解耦的，便于在 Notebook 或其他项目里复用：

```python
import tsp_ga
cost, route, history, cities, dist = tsp_ga.solve_tsp(
    n_nodes=20, seed=42, pop_size=100, generations=300, use_2opt=True)
```

调高 `pop_size` / `generations` / `two_opt_passes` 可继续逼近 n=20 的真实最优。

## 可选 OR-Tools 基准

`requirements.txt` 中 ortools 默认注释。若已安装，main.py 会自动用 OR-Tools（10s 时限）对 n>10 的实例求近最优基准；未安装时 n=20 的 `gap` 字段不显示，但 GA 与 GA+2-opt 成本仍可正常输出。安装命令：

```bash
E:/software/miniforge/python.exe -m pip install ortools
```
