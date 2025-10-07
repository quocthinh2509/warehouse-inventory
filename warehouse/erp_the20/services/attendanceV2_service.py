# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional, List, Tuple
from datetime import datetime, timedelta, date
from decimal import Decimal

from django.db import transaction, router
from django.utils import timezone
from django.db.models import Q

from erp_the20.models import AttendanceSummaryV2, ShiftInstance, ShiftTemplate


# =========================
# Cấu hình / Hằng số
# =========================

# Trạng thái được coi là "đang hoạt động" để kiểm tra chồng giờ
ACTIVE_STATUSES = {
    AttendanceSummaryV2.Status.PENDING,
    AttendanceSummaryV2.Status.APPROVED,
}

# Cho phép đăng ký/sửa/xoá trong các ngày: Thứ Năm (3) -> Thứ Bảy (5)
ALLOWED_REGISTER_WEEKDAYS = {0, 1, 2, 3, 4, 5}  # Mon=0 ... Sun=6  (VN: Thứ 5=3, Thứ 6=4, Thứ 7=5)

# =========================
# Helper về thời gian ca
# =========================

def _aware(dt: datetime) -> datetime:
    """Đưa datetime naive về aware theo TZ hiện tại (zoneinfo compatible)."""
    if timezone.is_aware(dt):
        return dt
    return timezone.make_aware(dt, timezone.get_current_timezone())


def _shift_window(si: ShiftInstance) -> Tuple[datetime, datetime]:
    """
    Tính khoảng thời gian [start_dt, end_dt) (aware) cho ShiftInstance, hỗ trợ ca qua đêm.
    """
    tmpl: ShiftTemplate = si.template
    start_naive = datetime.combine(si.date, tmpl.start_time)
    end_naive = datetime.combine(si.date, tmpl.end_time)

    # Nếu template đánh dấu overnight hoặc giờ kết thúc <= giờ bắt đầu -> cộng qua ngày hôm sau
    if tmpl.overnight or tmpl.end_time <= tmpl.start_time:
        end_naive = end_naive + timedelta(days=1)

    start_dt = _aware(start_naive)
    end_dt = _aware(end_naive)
    return start_dt, end_dt

def _windows_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    """
    Kiểm tra overlap 2 đoạn thời gian nửa-mở [start, end).
    Chồng nếu: start < other_end và other_start < end.
    """
    return a_start < b_end and b_start < a_end

def _candidate_date_span(si: ShiftInstance) -> Tuple[date, date]:
    """
    Khoanh vùng ngày để query trước khi so overlap:
    - Nếu ca không qua đêm: chỉ cần ngày của shift.
    - Nếu qua đêm: cần cả ngày trước/sau để bắt các ca chồng.
    """
    tmpl = si.template
    d0 = si.date
    if tmpl.overnight or tmpl.end_time <= tmpl.start_time:
        return (d0 - timedelta(days=1), d0 + timedelta(days=1))
    return (d0, d0)

def _is_registration_open_today() -> bool:
    """Kiểm tra có trong khung ngày cho phép đăng ký/sửa/xoá (Thứ Năm→Thứ Bảy) theo giờ VN không."""
    wd = timezone.localdate().weekday()
    return wd in ALLOWED_REGISTER_WEEKDAYS

def _db_alias_for_write():
    """Lấy đúng DB alias theo router cho model AttendanceSummaryV2."""
    return router.db_for_write(AttendanceSummaryV2)

def _db_alias_for_read():
    return router.db_for_read(AttendanceSummaryV2)

# =========================
# Kiểm tra chồng ca
# =========================

def _find_conflicts(
    employee_id: int,
    target_si: ShiftInstance,
    exclude_summary_id: Optional[int] = None
) -> List[AttendanceSummaryV2]:
    """
    Tìm các summary đang hoạt động (pending/approved) bị chồng thời gian với target_si.
    exclude_summary_id: bỏ qua 1 bản ghi (khi update).
    """
    target_start, target_end = _shift_window(target_si)
    d_from, d_to = _candidate_date_span(target_si)

    qs = AttendanceSummaryV2.objects.select_related("shift_instance", "shift_instance__template").filter(
        employee_id=employee_id,
        status__in=ACTIVE_STATUSES,
        shift_instance__date__gte=d_from,
        shift_instance__date__lte=d_to,
    )
    if exclude_summary_id:
        qs = qs.exclude(id=exclude_summary_id)

    conflicts: List[AttendanceSummaryV2] = []
    for s in qs:
        s_start, s_end = _shift_window(s.shift_instance)
        if _windows_overlap(target_start, target_end, s_start, s_end):
            conflicts.append(s)
    return conflicts

def _ensure_no_conflict_or_raise(
    employee_id: int,
    target_si: ShiftInstance,
    exclude_summary_id: Optional[int] = None,
    when: str = "register"
) -> None:
    conflicts = _find_conflicts(employee_id, target_si, exclude_summary_id=exclude_summary_id)
    if conflicts:
        # Ghép message rõ ràng
        details = []
        for c in conflicts:
            c_start, c_end = _shift_window(c.shift_instance)
            details.append(
                f"[#{c.id}] {c.shift_instance.template.code} {c_start.strftime('%Y-%m-%d %H:%M')}→{c_end.strftime('%Y-%m-%d %H:%M')} (status={c.status})"
            )
        joined = "; ".join(details)
        raise ValueError(f"Đăng ký bị trùng thời gian với các ca khác: {joined} (tại bước {when}).")


# =========================
# Quyền thời điểm thao tác
# =========================

def _require_registration_window_or_raise(actor_is_manager: bool) -> None:
    """
    Chỉ cho phép đăng ký/sửa/xoá trong Thứ Năm→Thứ Bảy.
    Quản lý có thể override.
    """
    if actor_is_manager:
        return
    if not _is_registration_open_today():
        raise PermissionError("Chỉ được đăng ký/sửa/xoá ca từ Thứ Năm đến Thứ Bảy.")


# =========================
# Dịch vụ cho NHÂN VIÊN
# =========================

def register_shift(employee_id: int, shift_instance_id: int, requested_by: Optional[int] = None,
                   actor_is_manager: bool = False) -> AttendanceSummaryV2:
    _require_registration_window_or_raise(actor_is_manager=actor_is_manager)

    db = _db_alias_for_write()
    # đọc SI trên alias đọc (hoặc cũng dùng write cho đơn giản)
    si = ShiftInstance.objects.using(db).select_related("template").get(id=shift_instance_id)
    _ensure_no_conflict_or_raise(employee_id, si, when="register")

    with transaction.atomic(using=db):                    # ✅ mở txn trên đúng alias
        obj, created = AttendanceSummaryV2.objects.using(db).get_or_create(
            employee_id=employee_id,
            shift_instance=si,
            defaults={
                "requested_by": requested_by or employee_id,
                "status": AttendanceSummaryV2.Status.PENDING,
                "is_valid": False,
            },
        )
        if not created:
            obj.status = AttendanceSummaryV2.Status.PENDING
            obj.is_valid = False
            obj.requested_by = requested_by or employee_id
            obj.reject_reason = ""
            obj.save(using=db, update_fields=["status","is_valid","requested_by","reject_reason","updated_at"])
        return obj

def update_registration(employee_id: int, summary_id: int, new_shift_instance_id: int,
                        requested_by: Optional[int] = None, actor_is_manager: bool = False) -> AttendanceSummaryV2:
    _require_registration_window_or_raise(actor_is_manager=actor_is_manager)

    db = _db_alias_for_write()
    # khóa bản ghi cần sửa
    with transaction.atomic(using=db):                    # ✅ alias đúng
        obj = (AttendanceSummaryV2.objects.using(db)
               .select_for_update()
               .select_related("shift_instance", "shift_instance__template")
               .get(id=summary_id))

        if not actor_is_manager and obj.employee_id != employee_id:
            raise PermissionError("Bạn không có quyền sửa đăng ký này.")

        new_si = ShiftInstance.objects.using(db).select_related("template").get(id=new_shift_instance_id)
        _ensure_no_conflict_or_raise(employee_id, new_si, exclude_summary_id=obj.id, when="update")

        obj.shift_instance = new_si

        if not actor_is_manager and obj.status == AttendanceSummaryV2.Status.APPROVED:
            obj.status = AttendanceSummaryV2.Status.PENDING
            obj.is_valid = False
            obj.approved_by = None
            obj.approved_at = None
            obj.reject_reason = ""

        if requested_by:
            obj.requested_by = requested_by

        obj.save(using=db, update_fields=[
            "shift_instance","status","is_valid","approved_by","approved_at","reject_reason","requested_by","updated_at"
        ])
        return obj

def delete_registration(employee_id: int, summary_id: int, actor_is_manager: bool = False) -> None:
    _require_registration_window_or_raise(actor_is_manager=actor_is_manager)

    db = _db_alias_for_write()
    with transaction.atomic(using=db):                    # ✅
        obj = AttendanceSummaryV2.objects.using(db).select_for_update().get(id=summary_id)

        if not actor_is_manager and obj.employee_id != employee_id:
            raise PermissionError("Bạn không có quyền xoá đăng ký này.")
        if obj.status == AttendanceSummaryV2.Status.APPROVED and not actor_is_manager:
            raise PermissionError("Không thể xoá bản ghi đã được duyệt. Vui lòng liên hệ quản lý để huỷ.")
        if (obj.ts_in or obj.ts_out) and not actor_is_manager:
            raise PermissionError("Không thể xoá bản ghi đã có dữ liệu chấm công.")

        obj.delete(using=db)

def cancel_registration(actor_user_id: int, summary_id: int, actor_is_manager: bool = False) -> AttendanceSummaryV2:
    _require_registration_window_or_raise(actor_is_manager=actor_is_manager)

    db = _db_alias_for_write()
    with transaction.atomic(using=db):                    # ✅
        obj = AttendanceSummaryV2.objects.using(db).select_for_update().get(id=summary_id)

        if not actor_is_manager and obj.employee_id != actor_user_id:
            raise PermissionError("Bạn không có quyền huỷ bản ghi này.")
        if obj.status == AttendanceSummaryV2.Status.APPROVED and not actor_is_manager:
            raise PermissionError("Bản ghi đã duyệt, vui lòng liên hệ quản lý để huỷ.")

        obj.status = AttendanceSummaryV2.Status.CANCELED
        obj.is_valid = False
        obj.approved_by = None
        obj.approved_at = None
        obj.save(using=db, update_fields=["status","is_valid","approved_by","approved_at","updated_at"])
        return obj

# =========================
# Dịch vụ cho QUẢN LÝ
# =========================

def approve_summary(manager_user_id: int, summary_id: int, override_overlap: bool = False) -> AttendanceSummaryV2:
    db = _db_alias_for_write()
    with transaction.atomic(using=db):                    # ✅
        obj = (AttendanceSummaryV2.objects.using(db)
               .select_for_update()
               .select_related("shift_instance","shift_instance__template")
               .get(id=summary_id))

        if not override_overlap:
            _ensure_no_conflict_or_raise(obj.employee_id, obj.shift_instance, exclude_summary_id=obj.id, when="approve")

        obj.approve(manager_user_id)
        obj.save(using=db, update_fields=["status","is_valid","approved_by","approved_at","updated_at"])
        return obj

def reject_summary(manager_user_id: int, summary_id: int, reason: str = "") -> AttendanceSummaryV2:
    db = _db_alias_for_write()
    with transaction.atomic(using=db):                    # ✅
        obj = AttendanceSummaryV2.objects.using(db).select_for_update().get(id=summary_id)
        obj.reject(manager_user_id, reason)
        obj.save(using=db, update_fields=["status","is_valid","approved_by","approved_at","reject_reason","updated_at"])
        return obj

def manager_cancel_summary(manager_user_id: int, summary_id: int, reason: str = "") -> AttendanceSummaryV2:
    db = _db_alias_for_write()
    with transaction.atomic(using=db):                    # ✅
        obj = AttendanceSummaryV2.objects.using(db).select_for_update().get(id=summary_id)
        obj.status = AttendanceSummaryV2.Status.CANCELED
        obj.is_valid = False
        obj.approved_by = None
        obj.approved_at = None
        if reason:
            obj.reject_reason = reason
        obj.save(using=db, update_fields=["status","is_valid","approved_by","approved_at","reject_reason","updated_at"])
        return obj
    

# =========================
# Đăng ký ca hàng loạt (tuần tới)
# =========================

def _next_week_window():
    """
    Trả về (start_date, end_date) cho TUẦN TỚI:
    - start: thứ Hai tuần sau
    - end  : Chủ Nhật tuần sau
    """
    today = timezone.localdate()
    # Monday=0..Sunday=6
    days_to_next_monday = (7 - today.weekday()) % 7
    if days_to_next_monday == 0:
        days_to_next_monday = 7  # nếu hôm nay là Monday -> tuần tới là +7
    start = today + timedelta(days=days_to_next_monday)
    end = start + timedelta(days=6)
    return start, end




def register_shifts_bulk_for_next_week(
    employee_id: int,
    shift_instance_ids: List[int],
    requested_by: Optional[int] = None,
    actor_is_manager: bool = False,
) -> dict:
    """
    Đăng ký ca hàng loạt cho TUẦN TỚI (thứ Hai→Chủ Nhật kế tiếp).

    Input:
      - employee_id: NV đăng ký
      - shift_instance_ids: danh sách id của ShiftInstance
      - requested_by: ai gửi (mặc định employee_id)
      - actor_is_manager: nếu True thì bỏ qua hạn chế cửa sổ đăng ký

    Return (dict):
    {
      "week_start": "YYYY-MM-DD",
      "week_end": "YYYY-MM-DD",
      "total_input": N,
      "created": [summary_id,...],
      "updated": [summary_id,...],
      "skipped": [{"shift_instance_id": x, "reason": "..."}],
      "errors":  [{"shift_instance_id": x, "error": "..."}],
    }
    """
    _require_registration_window_or_raise(actor_is_manager=actor_is_manager)

    week_start, week_end = _next_week_window()

    # Chuẩn hoá danh sách id, loại trùng
    try:
        si_ids = [int(x) for x in shift_instance_ids]
    except Exception:
        raise ValueError("shift_instance_ids phải là danh sách số nguyên.")

    si_ids = list(dict.fromkeys(si_ids))  # unique, giữ thứ tự đầu tiên

    db = _db_alias_for_write()

    # Lấy các ShiftInstance tương ứng
    si_qs = (
        ShiftInstance.objects.using(db)
        .select_related("template")
        .filter(id__in=si_ids)
    )
    si_map = {si.id: si for si in si_qs}

    results = {
        "week_start": str(week_start),
        "week_end": str(week_end),
        "total_input": len(si_ids),
        "created": [],
        "updated": [],
        "skipped": [],
        "errors": [],
    }

    # 1) Lọc những ca không thuộc tuần tới
    valid_si_ids: List[int] = []
    for _id in si_ids:
        si = si_map.get(_id)
        if not si:
            results["errors"].append({"shift_instance_id": _id, "error": "ShiftInstance không tồn tại."})
            continue
        if not (week_start <= si.date <= week_end):
            results["skipped"].append({"shift_instance_id": _id, "reason": "Ngoài tuần cho phép (tuần tới)."})
            continue
        valid_si_ids.append(_id)

    # 2) Kiểm tra trùng giờ giữa các ca trong cùng request
    #    (độc lập với trùng giờ với DB)
    windows = {}
    for _id in valid_si_ids:
        s = si_map[_id]
        windows[_id] = _shift_window(s)

    # cặp đôi O(n^2) — danh sách tuần thường nhỏ nên OK
    conflicted_in_request: set[int] = set()
    for i in range(len(valid_si_ids)):
        a = valid_si_ids[i]
        for j in range(i + 1, len(valid_si_ids)):
            b = valid_si_ids[j]
            a_start, a_end = windows[a]
            b_start, b_end = windows[b]
            if _windows_overlap(a_start, a_end, b_start, b_end):
                conflicted_in_request.add(b)

    truly_valid_ids = []
    for _id in valid_si_ids:
        if _id in conflicted_in_request:
            results["skipped"].append({"shift_instance_id": _id, "reason": "Trùng giờ với ca khác trong yêu cầu."})
        else:
            truly_valid_ids.append(_id)

    # 3) Ghi DB trong 1 transaction + check trùng với DB
    with transaction.atomic(using=db):
        for _id in truly_valid_ids:
            si = si_map[_id]
            try:
                # Trùng giờ với DB (pending/approved khác)
                _ensure_no_conflict_or_raise(employee_id, si, when="bulk_register")

                obj, created = (
                    AttendanceSummaryV2.objects.using(db)
                    .get_or_create(
                        employee_id=employee_id,
                        shift_instance=si,
                        defaults={
                            "requested_by": requested_by or employee_id,
                            "status": AttendanceSummaryV2.Status.PENDING,
                            "is_valid": False,
                        },
                    )
                )

                if created:
                    results["created"].append(obj.id)
                else:
                    # reset về PENDING giống logic register_shift đơn lẻ
                    obj.status = AttendanceSummaryV2.Status.PENDING
                    obj.is_valid = False
                    obj.requested_by = requested_by or employee_id
                    obj.reject_reason = ""
                    obj.save(
                        using=db,
                        update_fields=["status", "is_valid", "requested_by", "reject_reason", "updated_at"],
                    )
                    results["updated"].append(obj.id)

            except Exception as ex:
                results["errors"].append({"shift_instance_id": _id, "error": str(ex)})

    return results
