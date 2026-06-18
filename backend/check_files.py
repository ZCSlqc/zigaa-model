#!/usr/bin/env python3
"""检查 original/ 目录与 msgs 的一致性，自动补全缺失记录。

用法:
    python check_files.py --model-id <id> --resource-type <good|defect|test|template>

只改 msgs、passed_count、failed_count；errors 不动。
"""
import argparse
import cv2
import os
import sys
import json
from datetime import datetime, timezone

# 把 backend 加入 path（运行时从 backend/ 目录执行）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from core.database import SessionLocal
from core.models import DataPackage
from core.config import UPLOAD_DIR, SUPPORTED_IMAGE_EXTS
from services.helper import is_supported_image


LAYERS = ("compress", "preview")


def collect_image_files(original_dir: str) -> set[str]:
    """递归遍历 original/，返回相对路径集合。"""
    files = set()
    for root, _dirs, filenames in os.walk(original_dir, followlinks=False):
        for fname in filenames:
            if is_supported_image(fname):
                rel = os.path.relpath(os.path.join(root, fname), original_dir)
                files.add(rel)
    return files


def read_image_info(rel_path: str, original_dir: str) -> dict | None:
    """用 cv2 读图获取宽高通道。失败返回 None。"""
    full = os.path.join(original_dir, rel_path)
    img = cv2.imread(full)
    if img is None:
        return None
    return {
        "width": int(img.shape[1]),
        "height": int(img.shape[0]),
        "channels": int(img.shape[2]) if len(img.shape) == 3 else 1,
    }


def has_compress_preview(rel_path: str, resource_dir: str) -> bool:
    """检查 compress/preview 层是否有对应文件（good 和 defect 类型都需要）。"""
    base_noext = os.path.splitext(rel_path)[0]
    for layer in LAYERS:
        target = os.path.realpath(os.path.join(resource_dir, layer, base_noext + ".jpg"))
        if not os.path.isfile(target):
            return False
    return True


def has_json_annotation(rel_path: str, original_dir: str) -> bool:
    """检查是否有 .json 标注文件（仅 defect 类型需要）。"""
    target = os.path.realpath(os.path.join(original_dir, os.path.splitext(rel_path)[0] + ".json"))
    return os.path.isfile(target)


def check_and_fix(model_id: str, resource_type: str):
    db = SessionLocal()
    try:
        resource_dir = os.path.join(UPLOAD_DIR, model_id, resource_type)
        original_dir = os.path.join(resource_dir, "original")

        # ── 收集 ──
        if not os.path.isdir(original_dir):
            print(f"original 目录不存在: {original_dir}")
            return

        disk_files = collect_image_files(original_dir)
        dp = db.query(DataPackage).filter(
            DataPackage.model_id == model_id,
            DataPackage.resource_type == resource_type,
        ).first()

        if not dp:
            print(f"未找到 DataPackage: model_id={model_id} type={resource_type}")
            return

        msgs = dict(dp.msgs or {})
        errors = dict(dp.errors or {})

        # ── 差异分析 ──
        in_disk_not_in_msgs = disk_files - set(msgs.keys())
        in_msgs_not_in_disk = set(msgs.keys()) - disk_files

        # ── compress/preview 一致性（good + defect 都要） ──
        missing_compress = []
        missing_preview = []
        for rel in sorted(disk_files):
            base_noext = os.path.splitext(rel)[0]
            if not os.path.isfile(os.path.join(resource_dir, "compress", base_noext + ".jpg")):
                missing_compress.append(rel)
            if not os.path.isfile(os.path.join(resource_dir, "preview", base_noext + ".jpg")):
                missing_preview.append(rel)

        report_lines = [
            f"=== 检查报告 ===",
            f"模型: {model_id}",
            f"类型: {resource_type}",
            f"original 下图片总数: {len(disk_files)}",
            f"msgs 记录总数: {len(msgs)}",
            f"errors 记录总数: {len(errors)}",
            f"compress 缺失: {len(missing_compress)}",
            f"preview 缺失: {len(missing_preview)}",
            f"----------------------------------------",
            f"磁盘有, msgs 无: {len(in_disk_not_in_msgs)}",
            f"msgs 有, 磁盘无: {len(in_msgs_not_in_disk)}",
        ]

        # ── JSON 标注一致性（仅 defect 类型） ──
        missing_json = []
        if resource_type == "defect":
            for rel in sorted(disk_files):
                if not has_json_annotation(rel, original_dir):
                    missing_json.append(rel)
            report_lines.append(f"JSON 标注缺失: {len(missing_json)}")
            report_lines.append(f"----------------------------------------")

        new_msgs = 0
        new_errors = 0
        corrupted_count = 0
        category_updated = 0

        # ── 补 msgs + 统一加 category ──
        if in_disk_not_in_msgs:
            report_lines.append(f"----------------------------------------")
            report_lines.append(f"=== 正在补全 {len(in_disk_not_in_msgs)} 条缺失 msg ...")
        for rel in sorted(disk_files):
            entry = msgs.get(rel)
            if entry and "category" not in entry:
                entry["category"] = "none"
                msgs[rel] = entry
                category_updated += 1
            elif not entry:
                info = read_image_info(rel, original_dir)
                if info:
                    msgs[rel] = {**info, "category": "none"}
                    new_msgs += 1
                else:
                    msgs[rel] = {"width": 0, "height": 0, "channels": 0, "category": "none"}
                    errors[rel] = {"type": "corrupted", "level": 1, "message": "无法读取图片"}
                    new_msgs += 1
                    new_errors += 1
                    corrupted_count += 1

        if not in_disk_not_in_msgs and category_updated > 0:
            report_lines.append(f"========================================")
            report_lines.append(f"=== 统一补 category 到 msgs ...")
            report_lines.append(f"========================================")

        # ── 计算统计 ──
        # unique error images: key 或 key 去掉 .json 后匹配
        error_images = set()
        for key in errors:
            base = os.path.splitext(key)[0]
            for ext in SUPPORTED_IMAGE_EXTS:
                error_images.add(base + ext)
                error_images.add(key)

        # defect 类型：缺失 json 也算 failed
        missing_json_images = set()
        if resource_type == "defect":
            for rel in missing_json:
                missing_json_images.add(rel)

        failed_set = (error_images & disk_files) | (missing_json_images if resource_type == "defect" else set())
        failed_count = len(failed_set)
        passed_count = len(disk_files) - failed_count

        report_lines.append(f"----------------------------------------")
        report_lines.append(f"=== 修复结果 ===")
        report_lines.append(f"新增 msg: {new_msgs}")
        report_lines.append(f"category 补全: {category_updated}")
        report_lines.append(f"新增 error: {new_errors}")
        if corrupted_count:
            report_lines.append(f"  损坏文件: {corrupted_count}")
        report_lines.append(f"passed_count: {dp.passed_count} → {passed_count}")
        report_lines.append(f"failed_count: {dp.failed_count} → {failed_count}")
        if resource_type == "defect":
            report_lines.append(f"  JSON 标注缺失计入 failed: {len(missing_json)}")
        report_lines.append(f"errors 未修改（原 {len(dp.errors or {})} 条）")
        report_lines.append("")

        # ── 写入 ──
        dp.msgs = msgs
        dp.errors = errors
        dp.passed_count = passed_count
        dp.failed_count = failed_count
        dp.uploaded_at = datetime.now(timezone.utc).isoformat()
        db.commit()

        print("\n".join(report_lines))
        print(f"✅ 已提交到数据库")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="检查 original/ 与 msgs 一致性")
    parser.add_argument("--model-id", required=True, help="模型 UUID")
    parser.add_argument("--resource-type", required=True, choices=["good", "defect", "test", "template"])
    args = parser.parse_args()
    check_and_fix(args.model_id, args.resource_type)
