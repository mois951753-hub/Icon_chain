# convert_annotations_fixed.py
"""
将标注JSON文件转换为图标ID到含义的映射
"""

import json
import os
import glob
import re
from collections import defaultdict

def safe_json_load(filepath):
    """安全地加载JSON文件"""
    encodings = ['utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'latin-1']
    
    for encoding in encodings:
        try:
            with open(filepath, "r", encoding=encoding) as f:
                content = f.read()
                if content.startswith('\ufeff'):
                    content = content[1:]
                content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', content)
                return json.loads(content)
        except Exception as e:
            continue
    return None


def extract_meanings_from_annotations(data):
    """
    从标注数据中提取含义映射
    
    数据结构：
    - groups: 定义了分组（图形组）
    - annotations: 标注数据，target_id可以是grp_xxx或seg_xxx
    - task_id: 标注类型（literal_gloss, free_translation, pragmatic_meaning等）
    - value: 标注值（字符串或列表）
    """
    meanings = {}
    
    # 方法1：直接获取所有literal_gloss标注
    annotations = data.get("annotations", [])
    
    for ann in annotations:
        target_id = ann.get("target_id")
        task_id = ann.get("task_id", "")
        value = ann.get("value")
        
        # 只处理文本含义类型的标注
        if task_id not in ["literal_gloss", "free_translation", "pragmatic_meaning", "event_description"]:
            continue
        
        # 获取含义文本
        meaning = None
        if isinstance(value, str):
            # 排除明显不是含义的值
            if len(value) > 1 and value not in ['。', '，', '？', '！', '、']:
                meaning = value
        elif isinstance(value, list):
            # 如果是列表，取第一个非空字符串
            for v in value:
                if isinstance(v, str) and len(v) > 1:
                    meaning = v
                    break
        
        if not meaning:
            continue
        
        # 尝试从target_id中提取数字作为图标ID
        # target_id格式: grp_352525_48 或 seg_010996
        
        # 提取数字
        numbers = re.findall(r'\d+', target_id)
        if numbers:
            # 取第一个6位数字（seg_后面的数字）
            for num in numbers:
                if len(num) >= 4:  # 至少4位数字
                    # 转换为6位格式
                    icon_id = f"{int(num):06d}"
                    
                    # 存储含义，优先使用literal_gloss
                    current_key = f"{task_id}_{icon_id}"
                    if icon_id not in meanings:
                        meanings[icon_id] = {}
                    
                    if task_id not in meanings[icon_id]:
                        meanings[icon_id][task_id] = meaning
                    
                    break
    
    # 转换为简单的映射：取优先级最高的含义
    # 优先级: literal_gloss > pragmatic_meaning > free_translation > event_description
    priority = ["literal_gloss", "pragmatic_meaning", "free_translation", "event_description"]
    
    simple_meanings = {}
    for icon_id, meaning_dict in meanings.items():
        for task in priority:
            if task in meaning_dict:
                simple_meanings[icon_id] = meaning_dict[task]
                break
    
    return simple_meanings


def extract_from_groups(data):
    """从groups结构提取信息"""
    meanings = {}
    groups = data.get("groups", [])
    
    for group in groups:
        group_id = group.get("id", "")
        
        # 从group_id提取数字
        numbers = re.findall(r'\d+', group_id)
        if numbers:
            for num in numbers:
                if len(num) >= 4:
                    icon_id = f"{int(num):06d}"
                    
                    # 可以尝试从children推断含义
                    # 这里简化处理，主要是通过annotations
                    break
    
    return meanings


def convert_annotations_to_icon_meaning():
    """将标注数据转换为图标ID到含义的映射"""
    
    annotation_folder = "annotations"
    output_file = "icon_meanings.json"
    
    all_meanings = {}
    success_count = 0
    
    if not os.path.exists(annotation_folder):
        print(f"文件夹不存在: {annotation_folder}")
        return
    
    all_files = glob.glob(os.path.join(annotation_folder, "*.txt")) + \
                glob.glob(os.path.join(annotation_folder, "*.json"))
    
    print(f"找到 {len(all_files)} 个标注文件")
    
    for filepath in all_files:
        try:
            data = safe_json_load(filepath)
            if data is None:
                print(f"无法加载: {filepath}")
                continue
            
            # 提取含义
            extracted = extract_meanings_from_annotations(data)
            
            # 合并
            for icon_id, meaning in extracted.items():
                if icon_id not in all_meanings:
                    all_meanings[icon_id] = meaning
                else:
                    # 如果已有，保留较长的含义（通常更完整）
                    if len(meaning) > len(all_meanings[icon_id]):
                        all_meanings[icon_id] = meaning
            
            success_count += 1
            
            # 打印调试信息
            if extracted:
                print(f"从 {os.path.basename(filepath)} 提取到 {len(extracted)} 条")
                
        except Exception as e:
            print(f"处理 {filepath} 时出错: {e}")
    
    print(f"\n处理完成: 成功 {success_count} 个文件")
    print(f"提取到 {len(all_meanings)} 条图标含义映射")
    
    # 保存映射
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_meanings, f, ensure_ascii=False, indent=2)
    
    # 打印示例
    print("\n示例映射:")
    for i, (k, v) in enumerate(list(all_meanings.items())[:20]):
        print(f"  {k} -> {v[:80]}...")
    
    return all_meanings


def inspect_annotation_file(filepath):
    """检查单个标注文件的结构"""
    data = safe_json_load(filepath)
    if not data:
        print(f"无法加载: {filepath}")
        return
    
    print(f"\n=== 检查文件: {os.path.basename(filepath)} ===")
    
    # 查看顶层结构
    print(f"顶层键: {list(data.keys())}")
    
    # 查看annotations结构
    annotations = data.get("annotations", [])
    print(f"annotations数量: {len(annotations)}")
    
    if annotations:
        print("\n前3条annotations示例:")
        for ann in annotations[:3]:
            print(f"  target_id: {ann.get('target_id')}")
            print(f"  task_id: {ann.get('task_id')}")
            print(f"  value: {ann.get('value')}")
            print()
    
    # 查看groups结构
    groups = data.get("groups", [])
    print(f"groups数量: {len(groups)}")
    
    if groups:
        print("\n前3条groups示例:")
        for grp in groups[:3]:
            print(f"  id: {grp.get('id')}")
            print(f"  children数量: {len(grp.get('children', []))}")
            print()


if __name__ == "__main__":
    # 先检查一个文件的结构
    sample_files = glob.glob(os.path.join("annotations", "*.txt"))
    if sample_files:
        inspect_annotation_file(sample_files[0])
    
    # 运行转换
    convert_annotations_to_icon_meaning()
