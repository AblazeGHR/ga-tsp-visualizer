# -*- coding: utf-8 -*-
"""GA-TSP 路径去重版入口（新增脚本，不改动 main.py / tsp_ga.py）。

与原版 main.py 的唯一区别：种群维护按「路径等价类」去重——
把一条闭合回路的所有旋转与反向旋转归一化成规范形（canonical form），
同一等价类的多个个体只保留一个，避免种群被重复路径占据。

用法:
    E:/software/miniforge/python.exe main_dedup.py            # 默认 n=10, 20
    E:/software/miniforge/python.exe main_dedup.py --seed 1
"""

import argparse
import os
import random
import time

import matplotlib.pyplot as plt

import tsp_ga
import main as base                       # 复用基准求解 / 收敛曲线 / 结果格式化

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(HERE, "results")


# ---------- 路径等价类（canonical form） ----------

def canonical(route):
    """把一条闭合回路归一化为规范形：所有旋转 + 反向旋转中取最小字典序。

    用于识别「同一条路径」：起点不同（旋转）或走向相反（反转）的排列，
    只要对应同一回路，就归入同一个等价类。
    """
    n = len(route)
    r = tuple(route)
    rev = r[::-1]
    return min(
        min(r[k:] + r[:k] for k in range(n)),
        min(rev[k:] + rev[:k] for k in range(n)),
    )


# ---------- 去重版遗传算法 ----------

def dedup_solve_tsp(n_nodes, seed=None, pop_size=100, generations=300,
                    elite=2, tournament_k=3, crossover_rate=0.8,
                    mutation_rate=0.1, use_2opt=False, two_opt_passes=10,
                    cities=None):
    """与 tsp_ga.solve_tsp 等价的去重版主函数。

    初始种群与每代繁殖时都按 canonical 等价类去重：重复路径直接丢弃并重新生成，
    凑满 pop_size 个不同路径为止。2-opt 会把等价类压缩到很少，此时最多尝试
    max_tries 次，凑不满就接受较小的实际种群规模继续进化（这本身反映了去重后
    多样性受限的真实情况）。
    返回额外附上每代的 (实际种群规模, 唯一回路数) 序列 uniq_hist。
    """
    random.seed(seed)
    if cities is None:
        cities = tsp_ga.make_random_instance(n_nodes, seed)
    dist = tsp_ga.distance_matrix(cities)

    max_tries = pop_size * 10 if use_2opt else pop_size * 50

    # 初始种群：随机排列，按等价类去重
    pop, seen = [], set()
    tries = 0
    while len(pop) < pop_size and tries < max_tries:
        tries += 1
        ind = random.sample(range(n_nodes), n_nodes)
        c = canonical(ind)
        if c not in seen:
            seen.add(c)
            pop.append(ind)
    if use_2opt:
        pop = [tsp_ga.two_opt(ind, dist, two_opt_passes) for ind in pop]

    best_cost, best_route = float("inf"), None
    history, uniq_hist = [], []

    for _ in range(generations):
        costs = [tsp_ga.route_cost(ind, dist) for ind in pop]
        ranked = sorted(range(len(pop)), key=lambda i: costs[i])

        gen_best_cost = costs[ranked[0]]
        history.append(gen_best_cost)
        if gen_best_cost < best_cost:
            best_cost = gen_best_cost
            best_route = list(pop[ranked[0]])
        uniq_hist.append((len(pop), len({canonical(x) for x in pop})))

        # 精英保留（去重）
        new_pop, seen_new = [], set()
        for i in ranked[:elite]:
            ind = list(pop[i])
            c = canonical(ind)
            if c not in seen_new:
                seen_new.add(c)
                new_pop.append(ind)

        # 选择 + 交叉 + 变异补充满下一代，孩子重复则丢弃重新生成
        tries = 0
        while len(new_pop) < pop_size and tries < max_tries:
            tries += 1
            p1 = tsp_ga.tournament_select(pop, costs, tournament_k)
            p2 = tsp_ga.tournament_select(pop, costs, tournament_k)
            if random.random() < crossover_rate:
                child = tsp_ga.order_crossover(p1, p2)
            else:
                child = list(p1)
            child = tsp_ga.swap_mutation(child, mutation_rate)
            if use_2opt:
                child = tsp_ga.two_opt(child, dist, two_opt_passes)
            c = canonical(child)
            if c not in seen_new:
                seen_new.add(c)
                new_pop.append(child)

        pop = new_pop

    return best_cost, best_route, history, cities, dist, uniq_hist


# ---------- 主流程 ----------

def run_instance(n, seed, pop_size, generations):
    """跑单个规模 n 的去重版实验，返回结果字典。"""
    cities = tsp_ga.make_random_instance(n, seed)

    t0 = time.time()
    cost_ga, route_ga, hist_ga, _, dist, uniq_ga = dedup_solve_tsp(
        n, seed=seed, pop_size=pop_size, generations=generations, use_2opt=False)
    t_ga = time.time() - t0

    t0 = time.time()
    cost_ga2, route_ga2, hist_ga2, _, _, uniq_ga2 = dedup_solve_tsp(
        n, seed=seed, pop_size=pop_size, generations=generations, use_2opt=True)
    t_ga2 = time.time() - t0

    baseline, baseline_src = base.baseline_for(cities, dist, n)
    gap = lambda c: (c - baseline) / baseline * 100 if baseline else None

    return {
        "n": n, "cities": cities, "dist": dist,
        "cost_ga": cost_ga, "route_ga": route_ga, "hist_ga": hist_ga, "t_ga": t_ga,
        "cost_ga2": cost_ga2, "route_ga2": route_ga2, "hist_ga2": hist_ga2, "t_ga2": t_ga2,
        "baseline": baseline, "baseline_src": baseline_src,
        "gap_ga": gap(cost_ga), "gap_ga2": gap(cost_ga2),
        "conv_ga": base.converged_gen(hist_ga, cost_ga),
        "conv_ga2": base.converged_gen(hist_ga2, cost_ga2),
        "uniq_init": uniq_ga[0][1], "uniq_end": uniq_ga[-1][1],
        "uniq_init2": uniq_ga2[0][1], "uniq_end2": uniq_ga2[-1][1],
        "size_init": uniq_ga[0][0], "size_end": uniq_ga[-1][0],
        "size_init2": uniq_ga2[0][0], "size_end2": uniq_ga2[-1][0],
    }


def plot_orig_vs_dedup(pairs, path):
    """原版 vs 去重版（纯 GA）收敛曲线对比，多个规模并排子图。

    pairs: [(n, hist_orig, hist_dedup), ...]
    """
    n_sub = len(pairs)
    fig, axes = plt.subplots(1, n_sub, figsize=(6.5 * n_sub, 4.4), squeeze=False)
    for ax, (n, h_orig, h_dedup) in zip(axes[0], pairs):
        ax.plot(h_orig, label="纯GA 原版", linestyle="--", color="#9a9a9a")
        ax.plot(h_dedup, label="纯GA 去重", color="#d62728")
        ax.set_title(f"n={n} 收敛曲线对比")
        ax.set_xlabel("代数")
        ax.set_ylabel("最优路径长度")
        ax.legend()
        ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_gap_compare(gaps_orig, gaps_dedup, ns, path):
    """纯 GA 原版 vs 去重版的 gap 柱状对比（n1 / n2 两组）。"""
    import numpy as np
    x = np.arange(len(ns))
    w = 0.35
    fig, ax = plt.subplots(figsize=(6, 4.2))
    b1 = ax.bar(x - w / 2, gaps_orig, w, label="原版", color="#9a9a9a")
    b2 = ax.bar(x + w / 2, gaps_dedup, w, label="去重版", color="#d62728")
    ax.set_xticks(x)
    ax.set_xticklabels([f"n={n}" for n in ns])
    ax.set_ylabel("gap (%)")
    ax.set_title("纯 GA gap：原版 vs 去重版")
    ax.legend()
    for bars in (b1, b2):
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height(),
                    f"{b.get_height():.2f}%", ha="center", va="bottom", fontsize=9)
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="遗传算法解 TSP 演示（路径去重版）")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--n1", type=int, default=10, help="小规模城市数")
    parser.add_argument("--n2", type=int, default=20, help="大规模城市数")
    parser.add_argument("--pop-size", type=int, default=100, help="种群大小")
    parser.add_argument("--generations", type=int, default=300, help="进化代数")
    args = parser.parse_args()

    os.makedirs(RESULTS_DIR, exist_ok=True)
    print(f"随机种子 seed = {args.seed}  pop_size = {args.pop_size}  generations = {args.generations}")
    print("=" * 78)

    rows = []
    for n in (args.n1, args.n2):
        r = run_instance(n, args.seed, args.pop_size, args.generations)
        rows.append(r)
        src = r["baseline_src"] or "无基准"
        bv = f"{r['baseline']:.4f}" if r["baseline"] else "—"
        print(f"n={n:>2}  基准({src}) = {bv}")
        print("   纯GA(去重)      " + base.fmt_result(r, "ga"))
        print("   GA+2-opt(去重)  " + base.fmt_result(r, "ga2"))
        print(f"   种群(纯GA):     实际规模 {r['size_init']}→{r['size_end']}  唯一回路 {r['uniq_init']}→{r['uniq_end']}")
        print(f"   种群(GA+2-opt): 实际规模 {r['size_init2']}→{r['size_end2']}  唯一回路 {r['uniq_init2']}→{r['uniq_end2']}")
        print("-" * 78)

    # 去重版收敛曲线（GA 与 GA+2-opt）
    p1 = os.path.join(RESULTS_DIR, f"dedup_convergence_n{rows[0]['n']}.png")
    p2 = os.path.join(RESULTS_DIR, f"dedup_convergence_n{rows[1]['n']}.png")
    base.plot_convergence(rows[0]["hist_ga"], rows[0]["hist_ga2"], rows[0]["n"], p1)
    base.plot_convergence(rows[1]["hist_ga"], rows[1]["hist_ga2"], rows[1]["n"], p2)

    # 原版纯 GA 数据（同一实例重跑，用于对比）
    orig_hists, orig_costs = [], []
    for r in rows:
        cost, _, hist, _, _ = tsp_ga.solve_tsp(
            r["n"], seed=args.seed, pop_size=args.pop_size,
            generations=args.generations, use_2opt=False)
        orig_hists.append(hist)
        orig_costs.append(cost)

    # ① 原版 vs 去重版收敛对比（纯 GA，n1/n2 并排）
    pairs = [(rows[i]["n"], orig_hists[i], rows[i]["hist_ga"]) for i in range(2)]
    p3 = os.path.join(RESULTS_DIR, "dedup_vs_orig.png")
    plot_orig_vs_dedup(pairs, p3)

    # ② gap 柱状对比（纯 GA）
    p4 = os.path.join(RESULTS_DIR, "dedup_gap_compare.png")
    gaps_orig = [((c - r["baseline"]) / r["baseline"] * 100)
                 if r["baseline"] else None for c, r in zip(orig_costs, rows)]
    gaps_dedup = [r["gap_ga"] for r in rows]
    plot_gap_compare(gaps_orig, gaps_dedup, [rows[0]["n"], rows[1]["n"]], p4)

    print("已生成图片:")
    for p in (p1, p2, p3, p4):
        print(f"  {p}")


if __name__ == "__main__":
    main()
