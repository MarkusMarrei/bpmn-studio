"""
BPMN 2.0 Engine и Auto-Layout Генератор.
Реализует официальную спецификацию организаторов хакатона («Пример API для BPMN.md»),
строит топологию процесса, рассчитывает визуальные координаты (BPMNDI) и сериализует
в 100% валидный OMG BPMN 2.0 XML, открывающийся и редактируемый в bpmn.io без ошибок.
"""

import difflib
import html
import re
import uuid
from typing import Dict, List, Optional, Tuple, Any


def make_id(prefix: str = "Activity") -> str:
    """Генерация уникального XML ID для элементов BPMN."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class BPMNNode:
    def __init__(self, node_id: str, node_type: str, name: str, parent_id: str = "Process_1"):
        self.id = node_id
        self.type = node_type  # startEvent, endEvent, task, userTask, scriptTask, exclusiveGateway, parallelGateway, inclusiveGateway, subProcess, group
        self.name = name
        self.parent_id = parent_id
        self.lane_id: Optional[str] = None
        self.incoming: List[str] = []
        self.outgoing: List[str] = []
        # Визуальные координаты (BPMNDI)
        self.x = 0
        self.y = 0
        self.width = 120
        self.height = 80

        # Подсветка статуса узла (bioc стандарт для спорных/неполных зон)
        self.is_warning = False
        self.color_stroke: Optional[str] = None
        self.color_fill: Optional[str] = None

        if self.type in ("startEvent", "endEvent"):
            self.width = 36
            self.height = 36
        elif "Gateway" in self.type or "gateway" in self.type:
            self.width = 50
            self.height = 50
        elif self.type == "subProcess":
            self.width = 180
            self.height = 100
        else:
            # Адаптивный размер блоков задач (Task / UserTask):
            # базовый размер увеличен, чтобы даже длинные названия на русском свободно помещались с запасом
            name_len = len(name) if name else 0
            if name_len > 55:
                self.width = 155
                self.height = 92
            elif name_len > 35:
                self.width = 145
                self.height = 86
            else:
                self.width = 135
                self.height = 82

    def check_warning_status(self, **kwargs):
        name_lower = self.name.lower()
        if (kwargs.get('warning') or kwargs.get('is_warning') or kwargs.get('is_unclear') 
            or '[?]' in self.name or '❓' in self.name 
            or 'уточн' in name_lower or 'не определ' in name_lower or 'не указан' in name_lower):
            self.is_warning = True
            self.color_stroke = kwargs.get('stroke', '#d97706') # Янтарный/оранжевый
            self.color_fill = kwargs.get('fill', '#fef3c7')     # Мягкий янтарный фон
        elif kwargs.get('color') == 'error':
            self.is_warning = True
            self.color_stroke = kwargs.get('stroke', '#dc2626') # Красный
            self.color_fill = kwargs.get('fill', '#fee2e2')     # Светло-красный
        elif kwargs.get('color') == 'success':
            self.color_stroke = kwargs.get('stroke', '#16a34a')
            self.color_fill = kwargs.get('fill', '#dcfce7')
        elif kwargs.get('stroke') or kwargs.get('fill'):
            self.color_stroke = kwargs.get('stroke')
            self.color_fill = kwargs.get('fill')


class BPMNFlow:
    def __init__(self, flow_id: str, source_id: str, target_id: str, name: str = ""):
        self.id = flow_id
        self.source_id = source_id
        self.target_id = target_id
        self.name = name
        self.waypoints: List[Tuple[int, int]] = []
        self.label_bounds: Optional[Tuple[int, int, int, int]] = None
        self.is_warning: bool = False


class BPMNLane:
    def __init__(self, lane_id: str, name: str, pool_id: str):
        self.id = lane_id
        self.name = name
        self.pool_id = pool_id
        self.node_ids: List[str] = []
        self.x = 0
        self.y = 0
        self.width = 0
        self.height = 180


class BPMNPool:
    def __init__(self, pool_id: str, name: str = "Основной процесс"):
        self.id = pool_id
        self.name = name
        self.lanes: List[BPMNLane] = []
        self.x = 160
        self.y = 80
        self.width = 0
        self.height = 0


class DiagramBuilder:
    """
    Класс реализации DIAGRAM согласно 'Пример API для BPMN.md'
    """
    def __init__(self, process_id: str = "Process_1"):
        self.process_id = process_id
        self.nodes: Dict[str, BPMNNode] = {}
        self.flows: Dict[str, BPMNFlow] = {}
        self.pools: Dict[str, BPMNPool] = {}
        self.lanes: Dict[str, BPMNLane] = {}
        self.groups: Dict[str, str] = {}
        
        # Корневые старт и стоп события
        self.start_id = "Event_start"
        self.end_id = "Event_end"
        
        self.nodes[self.start_id] = BPMNNode(self.start_id, "startEvent", "Старт", process_id)
        self.nodes[self.end_id] = BPMNNode(self.end_id, "endEvent", "Завершение", process_id)

    # 1. Генерация подпроцесса
    def create_subprocess(self, name: str, parent_id: str = "", *args, **kwargs) -> str:
        sub_id = make_id("SubProcess")
        node = BPMNNode(sub_id, "subProcess", str(name), parent_id or self.process_id)
        node.check_warning_status(**kwargs)
        self._assign_lane(node, parent_id)
        self.nodes[sub_id] = node
        return sub_id

    # 2. Генерация обычной задачи (чистый прямоугольник без пиктограмм)
    def add_task(self, name: str, parent_id: str = "", *args, **kwargs) -> str:
        task_id = make_id("Activity")
        node = BPMNNode(task_id, "task", str(name), parent_id or self.process_id)
        node.check_warning_status(**kwargs)
        self._assign_lane(node, parent_id)
        self.nodes[task_id] = node
        return task_id

    # 3. Генерация пользовательской задачи (чистый прямоугольник без наезжающих иконок-человечков)
    def add_user_task(self, name: str, parent_id: str = "", *args, **kwargs) -> str:
        task_id = make_id("Activity")
        node = BPMNNode(task_id, "task", str(name), parent_id or self.process_id)
        node.check_warning_status(**kwargs)
        self._assign_lane(node, parent_id)
        self.nodes[task_id] = node
        return task_id

    # 4. Генерация скриптовой задачи
    def add_script_task(self, name: str, parent_id: str = "", *args, **kwargs) -> str:
        task_id = make_id("Activity")
        node = BPMNNode(task_id, "task", str(name), parent_id or self.process_id)
        node.check_warning_status(**kwargs)
        self._assign_lane(node, parent_id)
        self.nodes[task_id] = node
        return task_id

    # 4.1 Генерация сервисной задачи (системной)
    def add_service_task(self, name: str, parent_id: str = "", *args, **kwargs) -> str:
        task_id = make_id("Activity")
        node = BPMNNode(task_id, "task", str(name), parent_id or self.process_id)
        node.check_warning_status(**kwargs)
        self._assign_lane(node, parent_id)
        self.nodes[task_id] = node
        return task_id

    # 5. Создание пула и дорожек
    def add_pool(self, parent_id: str, lane_names_list: List[str], *args, **kwargs) -> Tuple[str, List[str]]:
        pool_id = make_id("Participant")
        pool = BPMNPool(pool_id, name="Энергетический процесс")
        self.pools[pool_id] = pool
        
        lane_ids = []
        for name in lane_names_list:
            lane_id = make_id("Lane")
            lane = BPMNLane(lane_id, str(name), pool_id)
            self.lanes[lane_id] = lane
            pool.lanes.append(lane)
            lane_ids.append(lane_id)
            
        return pool_id, lane_ids

    # 6. Генерация связи (стрелки) между узлами
    def add_link(self, task_id_parent: str, task_id_child: str, name: Optional[str] = "", *args, **kwargs) -> str:
        safe_name = str(name).strip() if (name is not None and str(name).strip() != "None") else ""
        flow_id = make_id("Flow")
        flow = BPMNFlow(flow_id, task_id_parent, task_id_child, safe_name)
        if kwargs.get('warning') or '?' in safe_name or '[?]' in safe_name:
            flow.is_warning = True
        self.flows[flow_id] = flow
        
        if task_id_parent in self.nodes:
            self.nodes[task_id_parent].outgoing.append(flow_id)
        if task_id_child in self.nodes:
            self.nodes[task_id_child].incoming.append(flow_id)
            
        return flow_id

    # 7. Генерация эксклюзивного шлюза (XOR)
    def add_exclusive_gateway(self, name: str, parent_id: str = "", *args, **kwargs) -> str:
        gw_id = make_id("Gateway_xor")
        node = BPMNNode(gw_id, "exclusiveGateway", str(name), parent_id or self.process_id)
        node.check_warning_status(**kwargs)
        self._assign_lane(node, parent_id)
        self.nodes[gw_id] = node
        return gw_id

    # 8. Генерация параллельного шлюза (AND)
    def add_parallel_gateway(self, name: str, parent_id: str = "", *args, **kwargs) -> str:
        gw_id = make_id("Gateway_and")
        node = BPMNNode(gw_id, "parallelGateway", str(name), parent_id or self.process_id)
        node.check_warning_status(**kwargs)
        self._assign_lane(node, parent_id)
        self.nodes[gw_id] = node
        return gw_id

    # 9. Генерация инклюзивного шлюза (OR)
    def add_inclusive_gateway(self, name: str, parent_id: str = "", *args, **kwargs) -> str:
        gw_id = make_id("Gateway_or")
        node = BPMNNode(gw_id, "inclusiveGateway", str(name), parent_id or self.process_id)
        node.check_warning_status(**kwargs)
        self._assign_lane(node, parent_id)
        self.nodes[gw_id] = node
        return gw_id

    # 10. Генерация группы
    def add_group(self, name: str, parent_id: str = "", *args, **kwargs) -> str:
        grp_id = make_id("Group")
        self.groups[grp_id] = str(name)
        return grp_id

    def _assign_lane(self, node: BPMNNode, parent_id: str):
        if parent_id in self.lanes:
            node.lane_id = parent_id
            self.lanes[parent_id].node_ids.append(node.id)

    def clear_all_warnings(self):
        """Снимает все предупреждающие маркеры и цвета, приводя схему к чистому виду согласованного процесса."""
        for node in self.nodes.values():
            node.is_warning = False
            node.color_stroke = None
            node.color_fill = None
            if '[?]' in node.name or '❓' in node.name:
                node.name = node.name.replace('[?]', '').replace('❓', '').replace('[]', '').strip()
        for flow in self.flows.values():
            flow.is_warning = False
            flow.color_stroke = None

    # =========================================================================
    # АВТО-ЛЕЙАУТ (РАСЧЕТ КООРДИНАТ BPMNDI)
    # =========================================================================
    def compute_layout(self):
        """
        Топологический расчет визуальных координат для предотвращения наложения
        узлов и формирования читаемой схемы BPMN.
        """
        # Автоматическая детекция незавершенных/обрываемых ветвей в режиме черновика:
        # Если узел (не Start и не End) не имеет исходящих связей к концу процесса,
        # он помечается цветом предупреждения (bioc amber #d97706) для явной подсветки открытых вопросов.
        for node_id, node in self.nodes.items():
            if node_id != self.start_id and node_id != self.end_id:
                if len(node.outgoing) == 0:
                    node.is_warning = True
                    node.color_stroke = "#d97706"
                    node.color_fill = "#fef3c7"

        # Синхронизируем подсветку стрелок к/от предупреждающих узлов
        for flow in self.flows.values():
            tgt_node = self.nodes.get(flow.target_id)
            src_node = self.nodes.get(flow.source_id)
            if (tgt_node and tgt_node.is_warning) or (src_node and src_node.is_warning):
                flow.color_stroke = "#d97706"

        has_lanes = len(self.lanes) > 0
        lane_indices: Dict[str, int] = {}
        lane_order: List[str] = []

        if has_lanes:
            for pool in self.pools.values():
                for idx, lane in enumerate(pool.lanes):
                    lane_order.append(lane.id)
                    lane_indices[lane.id] = idx

        # Привязка Start/End к профильным дорожкам (где реально начинается и завершается процесс)
        if has_lanes:
            if not self.nodes[self.start_id].lane_id and lane_order:
                first_lane = lane_order[0]
                if self.nodes[self.start_id].outgoing:
                    out_fid = self.nodes[self.start_id].outgoing[0]
                    tgt = self.nodes.get(self.flows[out_fid].target_id) if out_fid in self.flows else None
                    if tgt and tgt.lane_id in self.lanes:
                        first_lane = tgt.lane_id
                self.nodes[self.start_id].lane_id = first_lane
                if self.start_id not in self.lanes[first_lane].node_ids:
                    self.lanes[first_lane].node_ids.insert(0, self.start_id)

            if not self.nodes[self.end_id].lane_id and lane_order:
                inc_lanes = [
                    self.nodes[self.flows[fid].source_id].lane_id
                    for fid in self.nodes[self.end_id].incoming
                    if fid in self.flows and self.nodes[self.flows[fid].source_id].lane_id in self.lanes
                ]
                if inc_lanes:
                    best_lane = max(set(inc_lanes), key=inc_lanes.count)
                else:
                    best_lane = lane_order[-1]
                self.nodes[self.end_id].lane_id = best_lane
                if self.end_id not in self.lanes[best_lane].node_ids:
                    self.lanes[best_lane].node_ids.append(self.end_id)

        # Вычисление рангов (колонок) для каждого узла с помощью строгого BFS
        levels: Dict[str, int] = {self.start_id: 0}
        queue = [self.start_id]
        visited = {self.start_id}

        while queue:
            curr_id = queue.pop(0)
            curr_level = levels.get(curr_id, 0)
            node = self.nodes.get(curr_id)
            if not node:
                continue

            for flow_id in node.outgoing:
                flow = self.flows.get(flow_id)
                if flow and flow.target_id in self.nodes:
                    target_id = flow.target_id
                    if target_id not in visited:
                        visited.add(target_id)
                        levels[target_id] = curr_level + 1
                        queue.append(target_id)
                    elif levels[target_id] > curr_level:
                        # Прямое схождение путей (не цикл назад!)
                        levels[target_id] = max(levels[target_id], curr_level + 1)

        # Для не привязанных связями узлов (если такие есть)
        max_level = max(levels.values()) if levels else 0
        for node_id in self.nodes:
            if node_id not in levels:
                max_level += 1
                levels[node_id] = max_level

        # Предварительный подсчет количества узлов в каждой ячейке (level, lane)
        cell_node_counts: Dict[Tuple[int, Optional[str]], int] = {}
        for node_id, node in self.nodes.items():
            lvl = levels.get(node_id, 0)
            cell_node_counts[(lvl, node.lane_id)] = cell_node_counts.get((lvl, node.lane_id), 0) + 1

        lane_max_overlap: Dict[str, int] = {}
        for (lvl, lid), count in cell_node_counts.items():
            if lid:
                lane_max_overlap[lid] = max(lane_max_overlap.get(lid, 1), count)

        # Базовая сетка:
        # col_width = 240px: гарантирует 95-100px свободного воздуха между блоками
        base_x = 310 if has_lanes else 80
        col_width = 240
        pool_y_start = 80
        pool_x_start = 160

        # Высота дорожек: адаптивная, минимум 230px, а при ветвлении в колонке — 275px
        lane_heights: Dict[str, int] = {}
        if has_lanes:
            current_y = pool_y_start
            for lane_id in lane_order:
                lane = self.lanes[lane_id]
                has_branch = lane_max_overlap.get(lane_id, 1) >= 2
                l_h = 275 if has_branch else 230
                lane_heights[lane_id] = l_h
                lane.x = pool_x_start + 30
                lane.y = current_y
                lane.height = l_h
                current_y += l_h

        # Размещение узлов
        cell_occupancy: Dict[Tuple[int, Optional[str]], int] = {}

        for node_id, node in self.nodes.items():
            lvl = levels.get(node_id, 0)
            lane_id = node.lane_id
            key = (lvl, lane_id)
            sub_index = cell_occupancy.get(key, 0)
            cell_occupancy[key] = sub_index + 1
            total_in_cell = cell_node_counts.get(key, 1)

            # Координата X
            node.x = base_x + (lvl * col_width) + (10 if node.type in ("startEvent", "endEvent") else 0)

            # Координата Y (с защитой от наложений)
            if has_lanes and lane_id in self.lanes:
                lane = self.lanes[lane_id]
                center_lane_y = lane.y + (lane.height // 2) - (node.height // 2)
                if total_in_cell == 1:
                    if lane_id == lane_order[0]:
                        node.y = max(center_lane_y, lane.y + 60)
                    elif lane_id == lane_order[-1]:
                        node.y = min(center_lane_y, lane.y + lane.height - node.height - 60)
                    else:
                        node.y = center_lane_y
                elif total_in_cell == 2:
                    if sub_index == 0:
                        node.y = lane.y + (55 if lane_id == lane_order[0] else 35)
                    else:
                        node.y = lane.y + lane.height - node.height - (55 if lane_id == lane_order[-1] else 35)
                else:
                    step = (lane.height - node.height - 60) // max(1, total_in_cell - 1)
                    node.y = lane.y + 30 + (sub_index * step)
            else:
                base_y = 180
                node.y = base_y + (sub_index * 130)

        # Обновляем габариты Pool и Lane
        total_width = max([node.x + node.width for node in self.nodes.values()] + [800]) + 120
        total_pool_h = sum(lane_heights.values()) if has_lanes else 600
        for pool in self.pools.values():
            pool.x = pool_x_start
            pool.y = pool_y_start
            pool.width = total_width - pool_x_start + 40
            pool.height = total_pool_h
            for lane in pool.lanes:
                lane.width = pool.width - 30

        # Группируем исходящие стрелки по источникам
        outgoing_by_src: Dict[str, List[BPMNFlow]] = {}
        for f in self.flows.values():
            outgoing_by_src.setdefault(f.source_id, []).append(f)

        pool = list(self.pools.values())[0] if self.pools else None
        pool_top = (pool.y if pool else min(n.y for n in self.nodes.values()))
        pool_bottom = ((pool.y + pool.height) if pool else max(n.y + n.height for n in self.nodes.values()))

        def check_collision(wps: List[Tuple[int, int]], margin: int = 15, ignore_nodes=()) -> bool:
            for i in range(len(wps) - 1):
                x1, y1 = wps[i]
                x2, y2 = wps[i+1]
                min_x, max_x = min(x1, x2), max(x1, x2)
                min_y, max_y = min(y1, y2), max(y1, y2)
                for nid, n in self.nodes.items():
                    if nid in ignore_nodes:
                        continue
                    nx1, nx2 = n.x - margin, n.x + n.width + margin
                    ny1, ny2 = n.y - margin, n.y + n.height + margin
                    if abs(y1 - y2) < 2:  # горизонтальный отрезок
                        if ny1 < y1 < ny2 and max_x > nx1 and min_x < nx2:
                            return True
                    elif abs(x1 - x2) < 2:  # вертикальный отрезок
                        if nx1 < x1 < nx2 and max_y > ny1 and min_y < ny2:
                            return True
            return False

        # Расчет точек изломов стрелок (Waypoints) и координат подписей (BPMNLabel)
        for flow in self.flows.values():
            src = self.nodes.get(flow.source_id)
            tgt = self.nodes.get(flow.target_id)
            if not src or not tgt:
                continue

            is_src_gateway = "gateway" in src.type.lower()
            is_tgt_gateway = "gateway" in tgt.type.lower()
            sibling_flows = outgoing_by_src.get(flow.source_id, [])

            src_cy = src.y + (src.height // 2)
            tgt_cy = tgt.y + (tgt.height // 2)

            # -----------------------------------------------------------------
            # 1. ПРЯМЫЕ ПЕРЕХОДЫ ВПЕРЕД (src.x < tgt.x)
            # -----------------------------------------------------------------
            if src.x < tgt.x:
                delta_y = tgt_cy - src_cy
                exit_dir = "east"

                if is_src_gateway and len(sibling_flows) > 1:
                    # Разделяем ветви шлюза по разным сторонам ромба
                    if delta_y < -25:
                        # Ветка идет вверх — North vertex ромба
                        start_x = src.x + (src.width // 2)
                        start_y = src.y
                        exit_dir = "north"
                    elif delta_y > 25:
                        # Проверяем, есть ли другая ветка, идущая прямо
                        has_straight = any(abs((self.nodes[f.target_id].y + self.nodes[f.target_id].height // 2) - src_cy) <= 25 for f in sibling_flows if f.target_id in self.nodes and f.id != flow.id)
                        if has_straight:
                            # Прямая ветка займет East порт, поэтому нижняя ветка выходит из South порта
                            start_x = src.x + (src.width // 2)
                            start_y = src.y + src.height
                            exit_dir = "south"
                        else:
                            start_x = src.x + src.width
                            start_y = src_cy
                            exit_dir = "east"
                    else:
                        start_x = src.x + src.width
                        start_y = src_cy
                        exit_dir = "east"
                else:
                    start_x = src.x + src.width
                    start_y = src_cy

                end_x = tgt.x
                end_y = tgt_cy

                if exit_dir == "north":
                    flow.waypoints = [
                        (start_x, start_y),
                        (start_x, end_y),
                        (end_x, end_y)
                    ]
                elif exit_dir == "south":
                    flow.waypoints = [
                        (start_x, start_y),
                        (start_x, end_y),
                        (end_x, end_y)
                    ]
                else:
                    if abs(start_y - end_y) < 10:
                        cand_direct = [(start_x, start_y), (end_x, end_y)]
                        if not check_collision(cand_direct, margin=15, ignore_nodes=(src.id, tgt.id)):
                            flow.waypoints = cand_direct
                        else:
                            src_lane = self.lanes.get(src.lane_id) if has_lanes else None
                            by = (src_lane.y + 20) if src_lane else (src.y - 45)
                            flow.waypoints = [
                                (start_x, start_y),
                                (start_x + 18, start_y),
                                (start_x + 18, by),
                                (end_x - 22, by),
                                (end_x - 22, end_y),
                                (end_x, end_y)
                            ]
                    else:
                        mid_x = start_x + (end_x - start_x) // 2
                        cand_z = [
                            (start_x, start_y),
                            (mid_x, start_y),
                            (mid_x, end_y),
                            (end_x, end_y)
                        ]
                        if not check_collision(cand_z, ignore_nodes=(src.id, tgt.id)):
                            flow.waypoints = cand_z
                        else:
                            x_out = start_x + 25
                            x_in = max(x_out + 20, end_x - 25)
                            p_bot = (pool_bottom - 26) if has_lanes else (pool_bottom + 30)
                            flow.waypoints = [
                                (start_x, start_y),
                                (x_out, start_y),
                                (x_out, p_bot),
                                (x_in, p_bot),
                                (x_in, end_y),
                                (end_x, end_y)
                            ]

            # -----------------------------------------------------------------
            # 2. ОБРАТНЫЕ ПЕТЛИ И ЦИКЛЫ (Loop back: src.x >= tgt.x)
            # -----------------------------------------------------------------
            else:
                # Если цель в верхних дорожках — обходим по внутреннему верхнему коридору пула;
                # если в нижних — по внутреннему нижнему коридору пула
                go_top = (tgt.y <= src.y and (tgt.y - pool_top) <= (pool_bottom - src.y))

                if go_top:
                    # Внутренний коридор верхней дорожки (строго внутри дорожки и пула!)
                    loop_y = (pool_top + 26) if has_lanes else (pool_top - 30)
                    x_src_col = src.x + (src.width // 2)
                    col_top_cand = [(x_src_col, src.y), (x_src_col, loop_y)]
                    if not check_collision(col_top_cand, margin=10, ignore_nodes=(src.id, tgt.id)):
                        p_exit = (x_src_col, src.y)
                        x_out = x_src_col
                    else:
                        x_out = src.x + src.width + 20
                        p_exit = (src.x + src.width, src_cy)

                    if is_tgt_gateway:
                        p_entry = (tgt.x + (tgt.width // 2), tgt.y)
                        x_in = tgt.x + (tgt.width // 2)
                    else:
                        x_tgt_col = tgt.x + (tgt.width // 2)
                        col_in_cand = [(x_tgt_col, loop_y), (x_tgt_col, tgt.y)]
                        if not check_collision(col_in_cand, margin=10, ignore_nodes=(src.id, tgt.id)):
                            p_entry = (x_tgt_col, tgt.y)
                            x_in = x_tgt_col
                        else:
                            x_in = tgt.x - 25
                            p_entry = (tgt.x, tgt_cy)

                    wps = [p_exit]
                    if p_exit[0] != x_out:
                        wps.append((x_out, p_exit[1]))
                    wps.append((x_out, loop_y))
                    wps.append((x_in, loop_y))
                    if p_entry[0] != x_in:
                        wps.append((x_in, p_entry[1]))
                    wps.append(p_entry)
                    flow.waypoints = wps

                else:
                    # Внутренний коридор нижней дорожки (строго внутри дорожки и пула!)
                    loop_y = (pool_bottom - 26) if has_lanes else (pool_bottom + 30)
                    x_out = src.x + src.width + 20  # Всегда через свободный межколоночный желоб справа!
                    p_exit = (src.x + src.width, src_cy)

                    if is_tgt_gateway:
                        x_in = tgt.x + (tgt.width // 2)
                        p_entry = (x_in, tgt.y + tgt.height)  # Южный порт шлюза
                    else:
                        x_tgt_col = tgt.x + (tgt.width // 2)
                        col_in_cand = [(x_tgt_col, loop_y), (x_tgt_col, tgt.y + tgt.height)]
                        if not check_collision(col_in_cand, margin=10, ignore_nodes=(src.id, tgt.id)):
                            p_entry = (x_tgt_col, tgt.y + tgt.height)
                            x_in = x_tgt_col
                        else:
                            x_in = tgt.x - 25
                            p_entry = (tgt.x, tgt_cy)

                    wps = [p_exit]
                    if p_exit[0] != x_out:
                        wps.append((x_out, p_exit[1]))
                    wps.append((x_out, loop_y))
                    wps.append((x_in, loop_y))
                    if p_entry[0] != x_in:
                        wps.append((x_in, p_entry[1]))
                    wps.append(p_entry)
                    flow.waypoints = wps

            # -----------------------------------------------------------------
            # 3. РАСЧЕТ ПОДПИСИ (BPMNLabel) БЕЗ НАЛОЖЕНИЯ НА ЛИНИИ И БЛОКИ
            # -----------------------------------------------------------------
            if flow.name and flow.name.strip():
                label_text = flow.name.strip()
                is_short = len(label_text) <= 10 and ' ' not in label_text
                label_w = min(max(70, len(label_text) * 7 + 14), 130) if not is_short else max(60, len(label_text) * 8 + 10)
                label_h = 16 if is_short else 28

                if src.x >= tgt.x:
                    # Обратный цикл: подпись на самом длинном горизонтальном сегменте
                    best_seg = None
                    max_len = -1
                    for i in range(len(flow.waypoints) - 1):
                        p1, p2 = flow.waypoints[i], flow.waypoints[i+1]
                        if abs(p1[1] - p2[1]) < 2 and abs(p1[0] - p2[0]) > max_len:
                            max_len = abs(p1[0] - p2[0])
                            best_seg = (p1, p2)

                    if best_seg:
                        p1, p2 = best_seg
                        mid_x = (p1[0] + p2[0]) // 2
                        label_x = mid_x - (label_w // 2)
                        # Если по верхнему коридору: размещаем ПОД линией (там свободный запас до блоков задач)
                        if abs(p1[1] - (pool_top + 26)) < 10:
                            label_y = p1[1] + 8
                        elif p1[1] <= pool_top:
                            label_y = p1[1] - label_h - 10
                        # Если по нижнему коридору: размещаем НАД линией, чтобы оставаться внутри пула
                        elif abs(p1[1] - (pool_bottom - 26)) < 10:
                            label_y = p1[1] - label_h - 8
                        else:
                            label_y = p1[1] - label_h - 8
                    else:
                        label_x = src.x - 60
                        label_y = src.y - label_h - 10

                elif is_src_gateway:
                    wps = flow.waypoints
                    if exit_dir == "north":
                        if len(wps) >= 3:
                            seg_mid_x = (wps[1][0] + wps[2][0]) // 2
                            label_x = max(wps[1][0] + 15, seg_mid_x - (label_w // 2))
                            label_y = wps[1][1] - label_h - 10
                        else:
                            label_x = wps[0][0] + 15
                            label_y = wps[0][1] - label_h - 10
                    elif exit_dir == "south":
                        if len(wps) >= 3 and abs(wps[1][1] - wps[2][1]) < 2:
                            seg_mid_x = (wps[1][0] + wps[2][0]) // 2
                            label_x = max(wps[1][0] + 15, seg_mid_x - (label_w // 2))
                            label_y = wps[1][1] - label_h - 10
                        else:
                            label_x = wps[0][0] + 15
                            label_y = wps[0][1] + 15
                    else:
                        if len(wps) >= 4 and abs(wps[0][1] - wps[1][1]) < 2:
                            seg_len = abs(wps[1][0] - wps[0][0])
                            if seg_len >= label_w + 10:
                                label_x = wps[0][0] + (seg_len - label_w) // 2
                            else:
                                label_x = wps[0][0] + 10
                            label_y = wps[0][1] - label_h - 10
                        else:
                            seg_mid_x = (wps[0][0] + wps[1][0]) // 2
                            label_x = seg_mid_x - (label_w // 2)
                            label_y = wps[0][1] - label_h - 10

                else:
                    # Обычные переходы между задачами: на самом длинном горизонтальном сегменте
                    best_seg = None
                    max_len = -1
                    for i in range(len(flow.waypoints) - 1):
                        p1, p2 = flow.waypoints[i], flow.waypoints[i+1]
                        if abs(p1[1] - p2[1]) < 2 and abs(p1[0] - p2[0]) > max_len:
                            max_len = abs(p1[0] - p2[0])
                            best_seg = (p1, p2)
                    if best_seg:
                        p1, p2 = best_seg
                        mid_x = (p1[0] + p2[0]) // 2
                        label_x = mid_x - (label_w // 2)
                        label_y = p1[1] - label_h - 10
                    else:
                        label_x = flow.waypoints[0][0] + 15
                        label_y = flow.waypoints[0][1] - label_h - 10

                flow.label_bounds = (int(label_x), int(label_y), int(label_w), int(label_h))

    def _compute_gateway_label_bounds(self, node: BPMNNode) -> Tuple[int, int, int, int]:
        """
        Динамический расчет координат подписи шлюза (BPMNLabel).
        Автоматически проверяет занятость портов шлюза (North, South, East, West)
        и выбирает бесконфликтное положение без пересечения с соединительными линиями и узлами.
        """
        name_clean = node.name.strip() if node.name else ""
        lbl_w = min(max(70, len(name_clean) * 6 + 10), 95)
        lbl_h = 38 if len(name_clean) > 20 else (28 if len(name_clean) > 12 else 14)

        gw_cx = node.x + (node.width // 2)

        candidates = [
            # 1. Север по центру (если северный порт свободен)
            (gw_cx - (lbl_w // 2), node.y - lbl_h - 10),
            # 2. Юг по центру (если южный порт свободен)
            (gw_cx - (lbl_w // 2), node.y + node.height + 10),
            # 3. Юг со смещением вправо (если южный порт занят вертикальной линией по центру)
            (gw_cx + 10, node.y + node.height + 10),
            # 4. Север со смещением влево (свободный левый верхний квадрант)
            (gw_cx - lbl_w - 10, node.y - lbl_h - 10),
            # 5. Юг со смещением влево
            (gw_cx - lbl_w - 10, node.y + node.height + 10),
            # 6. Север со смещением вправо
            (gw_cx + 10, node.y - lbl_h - 10),
        ]

        def line_rect_intersect(p1: Tuple[int, int], p2: Tuple[int, int], rx: int, ry: int, rw: int, rh: int, margin: int = 2) -> bool:
            rx -= margin
            ry -= margin
            rw += 2 * margin
            rh += 2 * margin
            x1, y1 = p1
            x2, y2 = p2
            if max(x1, x2) < rx or min(x1, x2) > rx + rw:
                return False
            if max(y1, y2) < ry or min(y1, y2) > ry + rh:
                return False
            if x1 == x2:
                return rx <= x1 <= rx + rw and not (max(y1, y2) < ry or min(y1, y2) > ry + rh)
            if y1 == y2:
                return ry <= y1 <= ry + rh and not (max(x1, x2) < rx or min(x1, x2) > rx + rw)
            return True

        best_c = candidates[0]
        min_cost = 999999

        for cand_x, cand_y in candidates:
            line_colls = 0
            for fl in self.flows.values():
                for i in range(len(fl.waypoints) - 1):
                    p1, p2 = fl.waypoints[i], fl.waypoints[i+1]
                    if line_rect_intersect(p1, p2, cand_x, cand_y, lbl_w, lbl_h, margin=2):
                        line_colls += 1

            node_colls = 0
            for onid, onode in self.nodes.items():
                if onid == node.id:
                    continue
                if not (cand_x + lbl_w < onode.x or cand_x > onode.x + onode.width or
                        cand_y + lbl_h < onode.y or cand_y > onode.y + onode.height):
                    node_colls += 1

            cost = (line_colls * 1000) + (node_colls * 1000)
            if cost < min_cost:
                min_cost = cost
                best_c = (cand_x, cand_y)
                if cost == 0:
                    break

        return int(best_c[0]), int(best_c[1]), int(lbl_w), int(lbl_h)

    # =========================================================================
    # СЕРИАЛИЗАЦИЯ В BPMN 2.0.2 XML
    # =========================================================================
    def to_xml(self) -> str:
        """
        Генерирует строго валидный XML по схеме BPMN 2.0.2 с разделом BPMNDI.
        """
        self.compute_layout()
        
        has_pools = len(self.pools) > 0
        has_lanes = len(self.lanes) > 0
        collab_id = "Collaboration_1"
        
        xml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"',
            '                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"',
            '                  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"',
            '                  xmlns:di="http://www.omg.org/spec/DD/20100524/DI"',
            '                  xmlns:bioc="http://bpmn.io/schema/bpmn/biocolor/1.0"',
            '                  xmlns:color="http://www.omg.org/spec/BPMN/non-normative/color/1.0"',
            '                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
            '                  id="Definitions_Energy_BPMN"',
            '                  targetNamespace="http://bpmn.io/schema/bpmn"',
            '                  exporter="AI Assistant Energy Inter RAO"',
            '                  exporterVersion="2.0">'
        ]

        # Collaboration (если есть пулы или дорожки)
        if has_pools:
            xml_lines.append(f'  <bpmn:collaboration id="{collab_id}">')
            for pool in self.pools.values():
                safe_name = html.escape(pool.name)
                xml_lines.append(f'    <bpmn:participant id="{pool.id}" name="{safe_name}" processRef="{self.process_id}" />')
            xml_lines.append('  </bpmn:collaboration>')

        # Process
        xml_lines.append(f'  <bpmn:process id="{self.process_id}" isExecutable="false">')

        # Laneset
        if has_lanes:
            xml_lines.append('    <bpmn:laneSet id="LaneSet_1">')
            for lane in self.lanes.values():
                safe_name = html.escape(lane.name)
                xml_lines.append(f'      <bpmn:lane id="{lane.id}" name="{safe_name}">')
                for node_id in lane.node_ids:
                    xml_lines.append(f'        <bpmn:flowNodeRef>{node_id}</bpmn:flowNodeRef>')
                xml_lines.append('      </bpmn:lane>')
            xml_lines.append('    </bpmn:laneSet>')

        # Узлы (Start, End, Task, Gateway)
        for node in self.nodes.values():
            safe_name = html.escape(node.name)
            tag = node.type
            if tag == "exclusiveGateway":
                xml_lines.append(f'    <bpmn:exclusiveGateway id="{node.id}" name="{safe_name}">')
            elif tag == "parallelGateway":
                xml_lines.append(f'    <bpmn:parallelGateway id="{node.id}" name="{safe_name}">')
            elif tag == "inclusiveGateway":
                xml_lines.append(f'    <bpmn:inclusiveGateway id="{node.id}" name="{safe_name}">')
            elif tag == "userTask":
                xml_lines.append(f'    <bpmn:userTask id="{node.id}" name="{safe_name}">')
            elif tag == "scriptTask":
                xml_lines.append(f'    <bpmn:scriptTask id="{node.id}" name="{safe_name}">')
            elif tag == "serviceTask":
                xml_lines.append(f'    <bpmn:serviceTask id="{node.id}" name="{safe_name}">')
            elif tag == "subProcess":
                xml_lines.append(f'    <bpmn:subProcess id="{node.id}" name="{safe_name}">')
            elif tag == "startEvent":
                xml_lines.append(f'    <bpmn:startEvent id="{node.id}" name="{safe_name}">')
            elif tag == "endEvent":
                xml_lines.append(f'    <bpmn:endEvent id="{node.id}" name="{safe_name}">')
            else:
                xml_lines.append(f'    <bpmn:task id="{node.id}" name="{safe_name}">')

            for in_f in node.incoming:
                xml_lines.append(f'      <bpmn:incoming>{in_f}</bpmn:incoming>')
            for out_f in node.outgoing:
                xml_lines.append(f'      <bpmn:outgoing>{out_f}</bpmn:outgoing>')

            xml_lines.append(f'    </bpmn:{tag}>')

        # Связи (Sequence Flows)
        for flow in self.flows.values():
            safe_name = html.escape(flow.name) if flow.name else ""
            name_attr = f' name="{safe_name}"' if safe_name else ""
            xml_lines.append(f'    <bpmn:sequenceFlow id="{flow.id}" sourceRef="{flow.source_id}" targetRef="{flow.target_id}"{name_attr} />')

        xml_lines.append('  </bpmn:process>')

        # Секция визуализации BPMNDI
        target_plane_id = collab_id if has_pools else self.process_id
        xml_lines.append('  <bpmndi:BPMNDiagram id="BPMNDiagram_1">')
        xml_lines.append(f'    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="{target_plane_id}">')

        # Формы пулов и дорожек
        if has_pools:
            for pool in self.pools.values():
                xml_lines.append(f'      <bpmndi:BPMNShape id="{pool.id}_di" bpmnElement="{pool.id}" isHorizontal="true">')
                xml_lines.append(f'        <dc:Bounds x="{pool.x}" y="{pool.y}" width="{pool.width}" height="{pool.height}" />')
                xml_lines.append('      </bpmndi:BPMNShape>')
            for lane in self.lanes.values():
                xml_lines.append(f'      <bpmndi:BPMNShape id="{lane.id}_di" bpmnElement="{lane.id}" isHorizontal="true">')
                xml_lines.append(f'        <dc:Bounds x="{lane.x}" y="{lane.y}" width="{lane.width}" height="{lane.height}" />')
                xml_lines.append('      </bpmndi:BPMNShape>')

        # Формы узлов (Shapes)
        for node in self.nodes.values():
            color_attrs = ""
            if node.is_warning or node.color_stroke:
                stroke = node.color_stroke or "#d97706"
                fill = node.color_fill or "#fef3c7"
                color_attrs = f' bioc:stroke="{stroke}" bioc:fill="{fill}" color:background-color="{fill}" color:border-color="{stroke}"'

            xml_lines.append(f'      <bpmndi:BPMNShape id="{node.id}_di" bpmnElement="{node.id}"{color_attrs}>')
            xml_lines.append(f'        <dc:Bounds x="{node.x}" y="{node.y}" width="{node.width}" height="{node.height}" />')

            # Для событий и шлюзов (у которых надписи располагаются снаружи под фигурой)
            # формируем явный BPMNLabel с комфортным отступом 16px для событий, чтобы текст не прилипал к кругу
            is_external_label_node = node.type in ("startEvent", "endEvent") or "gateway" in node.type.lower()
            if is_external_label_node and node.name and node.name.strip():
                name_clean = node.name.strip()
                if node.type in ("startEvent", "endEvent"):
                    lbl_w = max(60, len(name_clean) * 8 + 14)
                    lbl_h = 14
                    lbl_y = int(node.y + node.height + 16)  # Увеличенный отступ 16px от границы круга события
                    lbl_x = int(node.x + (node.width // 2) - (lbl_w // 2))
                else:
                    lbl_x, lbl_y, lbl_w, lbl_h = self._compute_gateway_label_bounds(node)

                xml_lines.append('        <bpmndi:BPMNLabel>')
                xml_lines.append(f'          <dc:Bounds x="{lbl_x}" y="{lbl_y}" width="{lbl_w}" height="{lbl_h}" />')
                xml_lines.append('        </bpmndi:BPMNLabel>')

            xml_lines.append('      </bpmndi:BPMNShape>')

        # Линии связей (Edges)
        for flow in self.flows.values():
            edge_color = ""
            tgt_node = self.nodes.get(flow.target_id)
            if flow.is_warning or (tgt_node and tgt_node.is_warning):
                edge_color = ' bioc:stroke="#d97706" color:border-color="#d97706"'

            xml_lines.append(f'      <bpmndi:BPMNEdge id="{flow.id}_di" bpmnElement="{flow.id}"{edge_color}>')
            for wp in flow.waypoints:
                xml_lines.append(f'        <di:waypoint x="{wp[0]}" y="{wp[1]}" />')
            if flow.name and flow.label_bounds:
                lx, ly, lw, lh = flow.label_bounds
                xml_lines.append('        <bpmndi:BPMNLabel>')
                xml_lines.append(f'          <dc:Bounds x="{lx}" y="{ly}" width="{lw}" height="{lh}" />')
                xml_lines.append('        </bpmndi:BPMNLabel>')
            xml_lines.append('      </bpmndi:BPMNEdge>')

        xml_lines.append('    </bpmndi:BPMNPlane>')
        xml_lines.append('  </bpmndi:BPMNDiagram>')
        xml_lines.append('</bpmn:definitions>')

        return '\n'.join(xml_lines)


class AutoScope(dict):
    """
    Интеллектуальная среда исполнения DSL, устойчивая к опечаткам и галлюцинациям LLM.
    Если нейросеть ссылается на необъявленную переменную (например, t_notify_supply вместо t_notify_delay),
    AutoScope автоматически:
    1. Находит наиболее похожую объявленную переменную (нечеткий поиск difflib).
    2. Если точных совпадений нет, автоматически регистрирует новую задачу в DIAGRAM.
    Это на 100% предотвращает NameError при построении схемы.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        import builtins
        self['__builtins__'] = builtins

    def __missing__(self, key):
        if key.startswith('__'):
            raise KeyError(key)

        # 1. Поиск наиболее близкой переменной среди уже созданных (узлы, шлюзы, дорожки)
        candidates = [k for k in self.keys() if isinstance(k, str) and not k.startswith('__') and k not in ('DIAGRAM', 'Diagram', 'diagram')]
        matches = difflib.get_close_matches(key, candidates, n=1, cutoff=0.35)
        if matches:
            matched_val = self[matches[0]]
            self[key] = matched_val
            return matched_val

        # 2. Если кандидата нет, но есть DIAGRAM — динамически создаем узел
        if 'DIAGRAM' in self and hasattr(self['DIAGRAM'], 'add_task'):
            clean_name = re.sub(r'^(?:t_|task_|gw_|gateway_)', '', key)
            clean_name = clean_name.replace('_', ' ').strip().capitalize()
            node_id = self['DIAGRAM'].add_task(clean_name)
            self[key] = node_id
            return node_id

        raise KeyError(key)


def execute_dsl_code(code_str: str) -> str:
    """
    Выполняет Python-код по спецификации организаторов хакатона
    в изолированной безопасной среде и возвращает готовый XML.
    """
    diagram = DiagramBuilder(process_id="Process_Energy_1")
    
    # Среда окружения согласно документу 'Пример API для BPMN.md'
    scope = AutoScope({
        'DIAGRAM': diagram,
        'Diagram': diagram,
        'diagram': diagram,
        'DIagram': diagram,
        'ROOT_START_TASK_ID': diagram.start_id,
        'ROOT_START_TASK': diagram.start_id,
        'ROOT_START_ID': diagram.start_id,
        'START_TASK_ID': diagram.start_id,
        'START_ID': diagram.start_id,
        'START_EVENT_ID': diagram.start_id,
        'ROOT_END_TASK_ID': diagram.end_id,
        'ROOT_END_TASK': diagram.end_id,
        'ROOT_END_ID': diagram.end_id,
        'END_TASK_ID': diagram.end_id,
        'END_ID': diagram.end_id,
        'END_EVENT_ID': diagram.end_id,
        'ROOT_PROCESS_ID': diagram.process_id,
        'PROCESS_ID': diagram.process_id,
    })
    
    # Очищаем код от возможных маркеров ```python ... ```
    cleaned_code = code_str.strip()
    lines = []
    for line in cleaned_code.splitlines():
        trimmed = line.strip()
        # Пропускаем маркеры кода markdown
        if trimmed.startswith('```'):
            continue
        # Заменяем случайные вариации регистра diagram. -> DIAGRAM.
        trimmed = re.sub(r'\b[Dd][Ii][Aa][Gg][Rr][Aa][Mm]\.', 'DIAGRAM.', trimmed)
        lines.append(trimmed)
    
    final_code = '\n'.join(lines)
    
    try:
        exec(final_code, scope)
    except Exception as e:
        # Если при выполнении всего блока произошла непредвиденная ошибка,
        # выполняем скрипт построчно для максимальной устойчивости
        for line in lines:
            if not line or line.startswith('#'):
                continue
            try:
                exec(line, scope)
            except Exception as line_err:
                m = re.search(r"name '(\w+)' is not defined", str(line_err))
                if m:
                    missing_var = m.group(1)
                    scope[missing_var] = diagram.add_task(missing_var.replace('_', ' ').title())
                    try:
                        exec(line, scope)
                    except Exception:
                        pass
                else:
                    pass

    return diagram.to_xml()


def execute_dsl_with_audit(code_str: str, force_complete: bool = False) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Выполняет DSL-код и проводит строгий топологический аудит диаграммы.
    Возвращает кортеж:
      xml: сгенерированный OMG BPMN 2.0 XML
      issues: список обнаруженных коллизий (тупики, разрывы, незамкнутые развилки)
    """
    diagram = DiagramBuilder(process_id="Process_Energy_1")
    scope = AutoScope({
        'DIAGRAM': diagram,
        'Diagram': diagram,
        'diagram': diagram,
        'DIagram': diagram,
        'ROOT_START_TASK_ID': diagram.start_id,
        'ROOT_START_TASK': diagram.start_id,
        'ROOT_START_ID': diagram.start_id,
        'ROOT_END_TASK_ID': diagram.end_id,
        'ROOT_END_TASK': diagram.end_id,
        'ROOT_END_ID': diagram.end_id,
        'ROOT_PROCESS_ID': diagram.process_id,
        'PROCESS_ID': diagram.process_id,
    })

    cleaned_code = code_str.strip()
    lines = []
    for line in cleaned_code.splitlines():
        trimmed = line.strip()
        if trimmed.startswith('```'):
            continue
        trimmed = re.sub(r'\b[Dd][Ii][Aa][Gg][Rr][Aa][Mm]\.', 'DIAGRAM.', trimmed)
        lines.append(trimmed)
    final_code = '\n'.join(lines)

    try:
        exec(final_code, scope)
    except Exception:
        for line in lines:
            if not line or line.startswith('#'):
                continue
            try:
                exec(line, scope)
            except Exception as line_err:
                m = re.search(r"name '(\w+)' is not defined", str(line_err))
                if m:
                    missing_var = m.group(1)
                    scope[missing_var] = diagram.add_task(missing_var.replace('_', ' ').title())
                    try:
                        exec(line, scope)
                    except Exception:
                        pass

    detected_issues = []
    for node_id, node in diagram.nodes.items():
        if node_id != diagram.start_id and node_id != diagram.end_id:
            if len(node.outgoing) == 0:
                clean_name = node.name.replace('[❓]', '').strip()
                detected_issues.append({
                    "element": clean_name,
                    "description": f"Ветка операции «{clean_name}» обрывается (тупиковый шаг): в регламенте не указано дальнейшее действие или завершение процесса.",
                    "question": f"Что происходит после шага «{clean_name}»?",
                    "quick_replies": [
                        "Клиент устраняет замечания и подает повторно (цикл)",
                        "Процесс окончательно завершается отказом",
                        "Заявка аннулируется"
                    ]
                })

    if not detected_issues or force_complete:
        diagram.clear_all_warnings()
        if force_complete:
            detected_issues = []

    xml = diagram.to_xml()
    return xml, detected_issues
