"""
游戏数据管理模块
支持大量图片的懒加载和分页
"""

import json
import random
import os
import re
import glob
from typing import List, Dict, Optional
from datetime import datetime
import re
import math
from collections import defaultdict

# ==================== 配置 ====================
ICON_DATA_FILE = "icon_data.json"
LABEL_FOLDER = "label"
IMAGES_FOLDER = "static/images"
ANNOTATION_FOLDER = "annotations"

# ==================== 缓存 ====================
_cached_icon_count = None
_cached_icon_ids = None
_cached_icons = {}
_meaning_map = None
_meaning_map_loaded = False


# ==================== 图标管理 ====================

def get_total_icon_count() -> int:
    """快速获取图标总数"""
    global _cached_icon_count
    
    if _cached_icon_count is not None:
        return _cached_icon_count
    
    if not os.path.exists(IMAGES_FOLDER):
        _cached_icon_count = 0
        return 0
    
    count = 0
    try:
        for filename in os.listdir(IMAGES_FOLDER):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                count += 1
    except Exception as e:
        print(f"统计图片文件失败: {e}")
        count = 0
    
    _cached_icon_count = count
    print(f"检测到 {count} 个图片文件")
    return count


# ==================== 图标管理 ====================

# 缓存有含义标注的图标ID列表
_cached_valid_icon_ids = None
_cached_meaning_ids = None  # 缓存从含义文件加载的ID集合

def load_meaning_ids() -> set:
    """加载所有有含义标注的图标ID集合"""
    global _cached_meaning_ids
    
    if _cached_meaning_ids is not None:
        return _cached_meaning_ids
    
    meaning_map = load_meaning_map()
    # 从含义映射中提取所有有标注的ID
    meaning_ids = set()
    for key in meaning_map.keys():
        # 处理可能的多种ID格式（带前导零的6位数字）
        if isinstance(key, str):
            meaning_ids.add(key)
            # 如果是纯数字，也添加带前导零的版本
            if key.isdigit():
                meaning_ids.add(f"{int(key):06d}")
            # 尝试去掉前导零
            try:
                meaning_ids.add(str(int(key)))
            except:
                pass
    
    _cached_meaning_ids = meaning_ids
    print(f"加载了 {len(meaning_ids)} 个有含义标注的图标ID")
    return meaning_ids


def get_all_icon_ids() -> List[str]:
    """获取所有有含义标注的图标ID列表（过滤掉无标注的图标）"""
    global _cached_icon_ids
    
    if _cached_icon_ids is not None:
        return _cached_icon_ids
    
    if not os.path.exists(IMAGES_FOLDER):
        _cached_icon_ids = []
        return []
    
    # 获取有含义标注的ID集合
    valid_ids = load_meaning_ids()
    
    ids = []
    try:
        for filename in os.listdir(IMAGES_FOLDER):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                file_id = os.path.splitext(filename)[0]
                # 只保留有含义标注的图标
                if file_id in valid_ids:
                    ids.append(file_id)
                # 也尝试匹配带不同格式的ID
                elif file_id.lstrip('0') in valid_ids:
                    ids.append(file_id)
    except Exception as e:
        print(f"读取图片目录失败: {e}")
        ids = []
    
    def sort_key(x):
        if x.isdigit():
            return (0, int(x))
        return (1, x)
    
    ids.sort(key=sort_key)
    _cached_icon_ids = ids
    print(f"获取到 {len(ids)} 个有含义标注的图标ID（总图片 {len(os.listdir(IMAGES_FOLDER)) if os.path.exists(IMAGES_FOLDER) else 0}）")
    return ids


def get_total_icon_count() -> int:
    """快速获取有含义标注的图标总数"""
    global _cached_icon_count
    
    if _cached_icon_count is not None:
        return _cached_icon_count
    
    all_ids = get_all_icon_ids()
    _cached_icon_count = len(all_ids)
    return _cached_icon_count


def load_meaning_map() -> Dict:
    """加载图标含义映射（直接从标注文件读取）"""
    global _meaning_map, _meaning_map_loaded
    
    if _meaning_map_loaded:
        return _meaning_map
    
    _meaning_map = {}
    
    # 先尝试从预生成的文件加载
    map_file = "icon_meanings.json"
    if os.path.exists(map_file):
        try:
            with open(map_file, "r", encoding="utf-8") as f:
                _meaning_map = json.load(f)
            print(f"从 {map_file} 加载了 {len(_meaning_map)} 条含义映射")
            _meaning_map_loaded = True
            return _meaning_map
        except:
            pass
    
    # 如果预生成文件不存在，直接从标注文件夹读取
    if os.path.exists(ANNOTATION_FOLDER):
        from convert_annotations import convert_annotations_to_icon_meaning
        _meaning_map = convert_annotations_to_icon_meaning()
    
    _meaning_map_loaded = True
    return _meaning_map


def get_icon_meaning(icon_id: str) -> Optional[str]:
    """获取图标含义，如果没有标注则返回 None"""
    meaning_map = load_meaning_map()
    
    # 直接匹配
    if icon_id in meaning_map:
        return meaning_map[icon_id]
    
    # 尝试去掉前导零匹配
    try:
        num = int(icon_id)
        for key in meaning_map:
            if key.isdigit() and int(key) == num:
                return meaning_map[key]
    except:
        pass
    
    # 没有标注则返回 None（表示此图标不可用）
    return None


def get_icon_by_id(icon_id: str) -> Optional[Dict]:
    """根据ID获取图标，只返回有含义标注的图标"""
    # 先检查是否有含义标注
    common_meaning = get_icon_meaning(icon_id)
    if not common_meaning:
        return None  # 无标注，不返回此图标
    
    if icon_id in _cached_icons:
        return _cached_icons[icon_id]
    
    extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    icon_url = None
    
    for ext in extensions:
        full_path = os.path.join(IMAGES_FOLDER, f"{icon_id}{ext}")
        if os.path.exists(full_path):
            icon_url = f"/static/images/{icon_id}{ext}"
            break
    
    if not icon_url:
        return None
    
    icon = {
        "id": icon_id,
        "icon_url": icon_url,
        "filename": f"{icon_id}.jpg",
        "name": common_meaning[:20] if common_meaning else f"图标{icon_id}",
        "tags": [],
        "common_meaning": common_meaning,
        "icon": "🖼️"
    }
    
    _cached_icons[icon_id] = icon
    return icon


def get_random_start_icon() -> Dict:
    """获取随机起始图标（仅从有含义标注的图标中选取）"""
    all_ids = get_all_icon_ids()  # 现在只返回有效ID
    if not all_ids:
        # 如果没有任何有效图标，返回一个默认的
        return {"id": "000001", "icon_url": "", "name": "开始", "tags": [], "common_meaning": "开始游戏", "icon": "🎲"}
    
    import random
    icon_id = random.choice(all_ids)
    icon = get_icon_by_id(icon_id)
    
    if icon:
        return icon
    
    # 如果获取失败，尝试第一个
    if all_ids:
        icon = get_icon_by_id(all_ids[0])
        if icon:
            return icon
    
    return {"id": "000001", "icon_url": "", "name": "开始", "tags": [], "common_meaning": "开始游戏", "icon": "🎲"}


def get_icon_by_id(icon_id: str) -> Optional[Dict]:
    """根据ID获取图标"""
    if icon_id in _cached_icons:
        return _cached_icons[icon_id]
    
    extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    icon_url = None
    
    for ext in extensions:
        full_path = os.path.join(IMAGES_FOLDER, f"{icon_id}{ext}")
        if os.path.exists(full_path):
            icon_url = f"/static/images/{icon_id}{ext}"
            break
    
    if not icon_url:
        return None
    
    common_meaning = get_icon_meaning(icon_id)
    
    icon = {
        "id": icon_id,
        "icon_url": icon_url,
        "filename": f"{icon_id}.jpg",
        "name": common_meaning[:20] if common_meaning else f"图标{icon_id}",
        "tags": [],
        "common_meaning": common_meaning,
        "icon": "🖼️"
    }
    
    _cached_icons[icon_id] = icon
    return icon


def get_random_start_icon() -> Dict:
    """获取随机起始图标"""
    all_ids = get_all_icon_ids()
    if not all_ids:
        return {"id": "000001", "icon_url": "", "name": "开始", "tags": [], "common_meaning": "开始游戏", "icon": "🎲"}
    
    icon_id = random.choice(all_ids)
    icon = get_icon_by_id(icon_id)
    
    if icon:
        return icon
    
    icon = get_icon_by_id(all_ids[0])
    if icon:
        return icon
    
    return {"id": "000001", "icon_url": "", "name": "开始", "tags": [], "common_meaning": "开始游戏", "icon": "🎲"}


def get_random_icons(count: int = 4, exclude_ids: List[str] = None) -> List[Dict]:
    """完全随机获取有含义标注的图标"""
    exclude_ids = exclude_ids or []
    exclude_set = set(exclude_ids)
    
    all_ids = get_all_icon_ids()  # 现在只返回有效ID
    if not all_ids:
        return []
    
    available_ids = [aid for aid in all_ids if aid not in exclude_set]
    
    if len(available_ids) < count:
        available_ids = all_ids
    
    selected_ids = random.sample(available_ids, min(count, len(available_ids)))
    
    result = []
    for sid in selected_ids:
        icon = get_icon_by_id(sid)
        if icon:
            result.append(icon)
    
    # 如果还不够，从所有有效ID中再找
    if len(result) < count:
        remaining = count - len(result)
        for aid in all_ids:
            if aid not in [r['id'] for r in result] and aid not in exclude_set:
                icon = get_icon_by_id(aid)
                if icon:
                    result.append(icon)
                if len(result) >= count:
                    break
    
    random.shuffle(result)
    return result


# ==================== 工具函数 ====================

def preprocess_meaning(text: str) -> str:
    """预处理含义文本，提取关键词"""
    if not text or text.startswith('图标'):
        return ''
    # 去除标点符号
    text = re.sub(r'[^\w\u4e00-\u9fff]', ' ', text)
    # 去除常见无意义词
    stopwords = {'的', '了', '是', '在', '和', '有', '我', '他', '她', '它', '这', '那', '也', '就', '都', '说', '去', '来', '到', '看', '走', '想', '上', '下', '过', '会', '能', '可以', '一个', '这个', '那个', '然后', '之后', '后来', '看到', '看见', '想要', '并且', '还是', '于是', '但是', '因为', '所以', '虽然', '如果', '的话', '人', '又', '还', '把', '给', '让', '被'}
    words = []
    # 简单分词（按字符，中文不需要复杂分词）
    for i in range(len(text)):
        char = text[i]
        if len(char.strip()) > 0 and char not in stopwords and not char.isdigit():
            words.append(char)
    return ' '.join(words)


# ==================== 事件逻辑规则 ====================

EVENT_LOGIC = {
    # 因果关系
    'cause': [
        ('想上厕所', '去厕所'),
        ('去厕所', '上厕所'),
        ('上厕所', '小便'),
        ('上厕所', '大便'),
        ('上厕所', '舒服了'),
        ('饿了', '吃饭'),
        ('吃饭', '吃面'),
        ('吃饭', '饱了'),
        ('口渴', '喝水'),
        ('困了', '睡觉'),
        ('睡觉', '睡着'),
        ('睡着', '做梦'),
        ('做梦', '醒来'),
        ('醒来', '起床'),
        ('起床', '上班'),
        ('上班', '工作'),
        ('工作', '加班'),
        ('加班', '下班'),
        ('下班', '回家'),
    ],
    # 时序关系
    'sequence': [
        ('早上', '中午'),
        ('中午', '下午'),
        ('下午', '晚上'),
        ('晚上', '半夜'),
        ('半夜', '凌晨'),
        ('凌晨', '早上'),
        ('开始', '进行中'),
        ('进行中', '结束'),
    ],
    # 情感转化
    'emotion': [
        ('开心', '笑'),
        ('开心', '高兴'),
        ('笑', '大笑'),
        ('伤心', '哭泣'),
        ('哭泣', '悲伤'),
        ('紧张', '心跳'),
        ('害怕', '惊慌'),
        ('尴尬', '脸红'),
    ],
    # 动作延续
    'action': [
        ('走路', '继续走'),
        ('走路', '跑步'),
        ('跑步', '快跑'),
        ('跑步', '奔跑'),
        ('看', '盯着'),
        ('听', '听见'),
        ('说', '说话'),
        ('说话', '大喊'),
    ],
    # 交通工具
    'transport': [
        ('打车', '出租车'),
        ('出租车', '上车'),
        ('上车', '坐车'),
        ('坐车', '下车'),
        ('地铁', '坐地铁'),
        ('公交', '坐公交'),
        ('开车', '驾驶'),
    ],
    # 常见场景
    'scene': [
        ('公司', '办公'),
        ('办公室', '工位'),
        ('家', '回家'),
        ('医院', '看病'),
        ('厕所', '卫生间'),
        ('酒吧', '喝酒'),
        ('餐厅', '吃饭'),
    ],
}


def get_logic_recommendations(icon_id: str, count: int = 4, used_ids: List[str] = None) -> List[Dict]:
    """基于事件逻辑规则推荐相关图标"""
    used_ids = used_ids or []
    result = []
    seen_ids = set()
    
    current_meaning = get_icon_meaning(icon_id)
    if not current_meaning or current_meaning.startswith('图标'):
        return result
    
    # 遍历所有规则，查找匹配
    for category, rules in EVENT_LOGIC.items():
        for from_text, to_text in rules:
            # 检查当前含义是否包含规则中的源文本
            if from_text in current_meaning or current_meaning in from_text:
                # 查找目标文本相关的图标
                all_ids = get_all_icon_ids()
                for cand_id in all_ids:
                    if cand_id in used_ids or cand_id in seen_ids or cand_id == icon_id:
                        continue
                    cand_meaning = get_icon_meaning(cand_id)
                    if not cand_meaning:
                        continue
                    # 检查候选含义是否包含目标文本
                    if to_text in cand_meaning:
                        icon = get_icon_by_id(cand_id)
                        if icon:
                            result.append(icon)
                            seen_ids.add(cand_id)
                            if len(result) >= count:
                                return result
    
    return result[:count]


# ==================== 用户历史学习算法 ====================

class RelationLearner:
    """基于用户选择的关联学习器"""
    
    def __init__(self, relation_file="user_choices.json"):
        self.relation_file = relation_file
        self.relations = self._load_relations()
        self.total_choices = sum(self.relations.values()) if self.relations else 0
    
    def _load_relations(self):
        if os.path.exists(self.relation_file):
            try:
                with open(self.relation_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def get_weight(self, from_id: str, to_id: str) -> float:
        """获取两个图标之间的关联权重"""
        key = f"{from_id}->{to_id}"
        count = self.relations.get(key, 0)
        if count > 0 and self.total_choices > 0:
            # 使用对数平滑
            return math.log(count + 1) / math.log(self.total_choices + 1)
        return 0
    
    def get_recommendations(self, current_id: str, count: int = 4, 
                           used_ids: List[str] = None) -> List[Dict]:
        """基于历史用户选择获取推荐"""
        used_ids = used_ids or []
        exclude_set = set(used_ids + [current_id])
        
        # 找出所有从 current_id 出发的历史记录
        candidates = []
        for key, weight in self.relations.items():
            if key.startswith(f"{current_id}->"):
                to_id = key.split('->')[1]
                if to_id not in exclude_set:
                    candidates.append((weight, to_id))
        
        # 按权重排序
        candidates.sort(reverse=True, key=lambda x: x[0])
        
        # 获取推荐
        result = []
        for _, to_id in candidates[:count]:
            icon = get_icon_by_id(to_id)
            if icon:
                result.append(icon)
        
        return result





# ==================== 全局学习器实例 ====================

_relation_learner = None

def get_relation_learner():
    global _relation_learner
    if _relation_learner is None:
        _relation_learner = RelationLearner()
    return _relation_learner


# ==================== 主推荐函数 ====================

def get_next_icons(icon_id: str, count: int = 4, 
                   used_ids: List[str] = None) -> List[Dict]:
    """
    混合推荐算法：结合多种策略
    优先级：逻辑规则 > 用户历史 > 语义相似 > 随机
    """
    used_ids = used_ids or []
    current_meaning = get_icon_meaning(icon_id)
    
    result = []
    seen_ids = set()
    
    # 策略1: 事件逻辑推荐 (最高优先级)
    logic_icons = get_logic_recommendations(icon_id, count, used_ids)
    for icon in logic_icons:
        if icon and icon['id'] not in seen_ids and icon['id'] not in used_ids:
            result.append(icon)
            seen_ids.add(icon['id'])
    
    # 策略2: 用户历史学习推荐
    if len(result) < count:
        learner = get_relation_learner()
        history_icons = learner.get_recommendations(icon_id, count - len(result), 
                                                     list(seen_ids) + used_ids)
        for icon in history_icons:
            if icon and icon['id'] not in seen_ids and icon['id'] not in used_ids:
                result.append(icon)
                seen_ids.add(icon['id'])
    
    
    # 策略4: 随机推荐 (兜底)
    if len(result) < count:
        remaining = count - len(result)
        random_icons = get_random_icons(remaining, list(seen_ids) + used_ids)
        for icon in random_icons:
            if icon and icon['id'] not in seen_ids:
                result.append(icon)
                seen_ids.add(icon['id'])
    
    # 打乱顺序，避免位置偏见
    random.shuffle(result)
    
    return result


def update_relation_weight(icon_from: str, icon_to: str):
    """记录用户选择"""
    relation_file = "user_choices.json"
    try:
        if os.path.exists(relation_file):
            with open(relation_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}
        
        key = f"{icon_from}->{icon_to}"
        data[key] = data.get(key, 0) + 1
        
        if len(data) > 5000:
            sorted_items = sorted(data.items(), key=lambda x: x[1], reverse=True)
            data = dict(sorted_items[:3000])
        
        with open(relation_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        pass


def load_icon_data() -> List[Dict]:
    """加载图标数据"""
    ids = get_all_icon_ids()
    return [{"id": icon_id} for icon_id in ids[:100]]


def save_icon_data(icons: List[Dict]):
    """保存图标数据"""
    pass


def clear_cache():
    """清除缓存"""
    global _cached_icons, _meaning_map, _meaning_map_loaded
    _cached_icons = {}
    _meaning_map = None
    _meaning_map_loaded = False


# ==================== 游戏会话管理 ====================

class GameSession:
    def __init__(self, username: str, total_rounds: int):
        self.username = username
        self.total_rounds = total_rounds
        self.current_round = 0
        self.chain = []
        self.used_icon_ids = set()
        self.start_time = None
        self.end_time = None
        self.is_active = True
    
    def start_game(self) -> Dict:
        start_icon = get_random_start_icon()
        self.chain = [start_icon]
        self.used_icon_ids = {start_icon["id"]}
        self.current_round = 1
        self.start_time = datetime.now()
        return {
            "current_icon": start_icon,
            "round": self.current_round,
            "total_rounds": self.total_rounds,
            "chain": self.chain
        }
    
    def make_choice(self, selected_icon_id: str) -> Dict:
        if not self.is_active:
            return {"game_over": True, "message": "游戏已结束"}
        
        selected_icon = get_icon_by_id(selected_icon_id)
        if not selected_icon:
            return {"error": "无效的图标选择"}
        
        self.chain.append(selected_icon)
        self.used_icon_ids.add(selected_icon_id)
        
        if len(self.chain) >= 2:
            prev_icon_id = self.chain[-2]["id"]
            update_relation_weight(prev_icon_id, selected_icon_id)
        
        if self.current_round >= self.total_rounds:
            self.end_game()
            return {
                "game_complete": True,
                "chain": self.chain,
                "total_rounds": self.total_rounds,
                "message": f"🎉 恭喜！你完成了 {self.total_rounds} 回合的接龙！"
            }
        
        self.current_round += 1
        next_options = get_next_icons(selected_icon_id, 4, list(self.used_icon_ids))
        
        return {
            "current_icon": selected_icon,
            "options": next_options,
            "round": self.current_round,
            "total_rounds": self.total_rounds,
            "chain": self.chain,
            "game_over": False
        }
    
    def end_game(self):
        self.is_active = False
        self.end_time = datetime.now()
    
    def get_game_summary(self) -> Dict:
        return {
            "chain": self.chain,
            "chain_length": len(self.chain),
            "total_rounds": self.total_rounds,
            "completed": len(self.chain) >= self.total_rounds,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None
        }


active_games = {}


def create_game_session(username: str, total_rounds: int) -> str:
    import uuid
    session_id = str(uuid.uuid4())[:8]
    active_games[session_id] = GameSession(username, total_rounds)
    return session_id


def get_game_session(session_id: str):
    return active_games.get(session_id)


def end_game_session(session_id: str):
    if session_id in active_games:
        del active_games[session_id]


