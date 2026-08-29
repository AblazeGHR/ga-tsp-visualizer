# -*- coding: utf-8 -*-
"""遗传算法解 TSP（旅行商问题）的最小演示实现。

模块提供:
- make_random_instance / distance_matrix / route_cost: 实例生成与路径评估
- tournament_select / order_crossover / swap_mutation: 遗传算子
- two_opt: 2-opt 局部搜索改进函数
- exhaustive_solve: 穷举法精确求解（小规模基准）
- solve_tsp: GA 主入口，返回 (best_cost, best_route, 收敛历史, cities, dist)
"""

import itertools
import math
import random


# ---------- 实例生成与路径评估 ----------

def make_random_instance(n, seed=None):
    """在 [0,1]^2 平面内随机生成 n 个城市的坐标 (x, y)。"""
    rng = random.Random(seed)
    return [(rng.random(), rng.random()) for _ in range(n)]


def distance_matrix(cities):
    """由城市坐标计算两两欧氏距离矩阵（对称）。"""
    n = len(cities)
    dist = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = math.hypot(cities[i][0] - cities[j][0],
                           cities[i][1] - cities[j][1])
            dist[i][j] = dist[j][i] = d
    return dist


def route_cost(route, dist):
    """计算一条回路的总长度（首尾相连，即回到起点）。"""
    n = len(route)
    return sum(dist[route[i]][route[(i + 1) % n]] for i in range(n))


# ---------- 遗传算子 ----------

def tournament_select(pop, costs, k=3):
    """锦标赛选择：随机抽 k 个个体，返回其中总路程最短的一个。"""
    best = None
    for _ in range(k):
        idx = random.randrange(len(pop))
        if best is None or costs[idx] < costs[best]:
            best = idx
    return list(pop[best])


def order_crossover(p1, p2):
    """顺序交叉 OX：保留 p1 中一段连续子路径，其余城市按 p2 中的顺序补全。"""
    n = len(p1)
    a, b = sorted(random.sample(range(n), 2))
    child = [None] * n
    child[a:b] = p1[a:b]
    keep = set(child[a:b])
    fill = [g for g in p2 if g not in keep]
    j = 0
    for i in range(n):
        if child[i] is None:
            child[i] = fill[j]
            j += 1
    return child


def swap_mutation(route, rate=0.1):
    """交换变异：对每个位置，以 rate 概率与随机位置交换基因。"""
    n = len(route)
    r = list(route)
    for i in range(n):
        if random.random() < rate:
            j = random.randrange(n)
            r[i], r[j] = r[j], r[i]
    return r


def two_opt(route, dist, max_passes=10):
    """2-opt 局部搜索：通过消除交叉边不断缩短回路。

    对每对边 (i, i+1) 与 (j, j+1)，若换成 (i, j) 与 (i+1, j+1) 更短，
    则反转 i+1..j 这一段路径。循环扫描，直到一轮内不再改进。
    """
    n = len(route)
    r = list(route)
    for _ in range(max_passes):
        improved = False
        for i in range(n - 1):
            for j in range(i + 1, n):
                i1 = (i + 1) % n
                j1 = (j + 1) % n
                old = dist[r[i]][r[i1]] + dist[r[j]][r[j1]]
                new = dist[r[i]][r[j]] + dist[r[i1]][r[j1]]
                if new < old - 1e-12:
                    r[i + 1:j + 1] = reversed(r[i + 1:j + 1])
                    improved = True
        if not improved:
            break
    return r


def exhaustive_solve(cities, dist):
    """穷举法求精确最优解（仅适合小规模，n <= 10）。固定起点 0，遍历其余全排列。"""
    n = len(cities)
    best_route, best_cost = None, float("inf")
    for tail in itertools.permutations(range(1, n)):
        route = [0] + list(tail)
        c = route_cost(route, dist)
        if c < best_cost:
            best_cost, best_route = c, route
    return best_cost, best_route


# ---------- 遗传算法主函数 ----------

def solve_tsp(n_nodes, seed=None, pop_size=100, generations=300,
              elite=2, tournament_k=3, crossover_rate=0.8,
              mutation_rate=0.1, use_2opt=False, two_opt_passes=10,
              cities=None):
    """遗传算法解 TSP 主函数。

    参数:
        n_nodes:       城市数量
        seed:          随机种子（保证可复现）
        pop_size:      种群大小
        generations:   进化代数
        elite:         精英保留数量
        tournament_k:  锦标赛选择参赛人数
        crossover_rate: 交叉概率
        mutation_rate: 变异概率（每个位置）
        use_2opt:      是否在进化过程中对每个个体施加 2-opt 局部搜索
        two_opt_passes: 2-opt 的最大扫描轮数
        cities:        可选，直接提供城市坐标（否则内部随机生成）

    返回:
        (best_cost, best_route, history, cities, dist)
        history: 每代最优成本的列表，用于画收敛曲线
    """
    random.seed(seed)                     # 统一种子，让整个进化过程可复现
    if cities is None:
        cities = make_random_instance(n_nodes, seed)
    dist = distance_matrix(cities)

    # 初始种群：n 个城市的随机排列
    pop = [random.sample(range(n_nodes), n_nodes) for _ in range(pop_size)]
    if use_2opt:
        pop = [two_opt(ind, dist, two_opt_passes) for ind in pop]

    best_cost, best_route = float("inf"), None
    history = []

    for gen in range(generations):
        costs = [route_cost(ind, dist) for ind in pop]
        ranked = sorted(range(pop_size), key=lambda i: costs[i])

        # 记录当代最优，并更新全局最优
        gen_best_idx = ranked[0]
        gen_best_cost = costs[gen_best_idx]
        gen_best_route = list(pop[gen_best_idx])
        history.append(gen_best_cost)
        if gen_best_cost < best_cost:
            best_cost, best_route = gen_best_cost, gen_best_route

        # 精英保留：最优的 elite 个个体直接进入下一代
        new_pop = [list(pop[i]) for i in ranked[:elite]]

        # 用选择 + 交叉 + 变异补充满下一代
        while len(new_pop) < pop_size:
            p1 = tournament_select(pop, costs, tournament_k)
            p2 = tournament_select(pop, costs, tournament_k)
            if random.random() < crossover_rate:
                child = order_crossover(p1, p2)
            else:
                child = list(p1)
            child = swap_mutation(child, mutation_rate)
            if use_2opt:
                child = two_opt(child, dist, two_opt_passes)
            new_pop.append(child)

        pop = new_pop

    return best_cost, best_route, history, cities, dist


# ---------- 追加：3-opt 与备选遗传算子（消融实验用，不改变原函数） ----------

def three_opt(route, dist, max_passes=10):
    """3-opt 局部搜索（two_opt 打底 + 方向保留段交换）。

    2-opt 每次反转一段，能消除「交叉型」缺陷；3-opt 进一步把环切成
    A/B/C 三段并尝试不同顺序重新拼接（方向保留），处理 2-opt 无能为力
    的「缠绕型」缺陷。实现上先跑 two_opt 再做段交换循环，因此结果
    必然不劣于 two_opt，代价是每轮扫描 O(n^3) 更慢。
    """
    r = two_opt(list(route), dist, max_passes)
    n = len(r)
    best_cost = route_cost(r, dist)
    for _ in range(max_passes):
        improved = False
        for a in range(1, n):
            for b in range(a + 1, n):
                for c in range(b + 1, n + 1):
                    if c - b < 1:
                        continue
                    A, B = r[a:b], r[b:c]
                    C = r[c:] + r[:a]
                    for cand in (A + C + B, B + A + C,
                                 B + C + A, C + A + B, C + B + A):
                        cc = route_cost(cand, dist)
                        if cc < best_cost - 1e-12:
                            r, best_cost = cand, cc
                            improved = True
        if not improved:
            break
    return r


def pmx_crossover(p1, p2):
    """部分匹配交叉（PMX，Partially Mapped Crossover）。

    继承 p1 中一段，其余位置按 p2 顺序填入；若与 p1 段冲突，则沿
    「p1 段元素 ↔ p2 段元素」的映射关系替换，保证子代仍是合法排列。
    """
    n = len(p1)
    a, b = sorted(random.sample(range(n), 2))
    child = [None] * n
    child[a:b] = p1[a:b]
    pmap = {p1[i]: p2[i] for i in range(a, b)}
    for i in range(n):
        if child[i] is None:
            v = p2[i]
            while v in pmap:
                v = pmap[v]
            child[i] = v
    return child


def cx_crossover(p1, p2):
    """循环交叉（CX，Cycle Crossover）。

    p1 与 p2 的排列可分解为若干不相交循环；不同循环交替继承 p1 / p2
    的绝对位置基因，不引入任何重复基因。
    """
    n = len(p1)
    child = [None] * n
    pos = {g: i for i, g in enumerate(p1)}
    visited = [False] * n
    use_p1 = True
    for i in range(n):
        if visited[i]:
            continue
        j = i
        while not visited[j]:
            visited[j] = True
            child[j] = p1[j] if use_p1 else p2[j]
            j = pos[p2[j]]
        use_p1 = not use_p1
    return child


def inversion_mutation(route, rate=0.1):
    """逆序变异：以 rate 概率反转一段连续子路径（与 2-opt 同源的破坏方式）。"""
    n = len(route)
    r = list(route)
    if random.random() < rate:
        a, b = sorted(random.sample(range(n), 2))
        r[a:b] = reversed(r[a:b])
    return r


def insertion_mutation(route, rate=0.1):
    """插入变异：以 rate 概率随机取出一个城市插入到随机位置。"""
    n = len(route)
    r = list(route)
    if random.random() < rate:
        i = random.randrange(n)
        g = r.pop(i)
        r.insert(random.randrange(n), g)
    return r
