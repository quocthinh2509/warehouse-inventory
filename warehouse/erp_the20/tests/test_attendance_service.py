# -*- coding: utf-8 -*-
from datetime import date, datetime, time, timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from erp_the20.models import (
    ShiftTemplate, ShiftInstance,
    AttendanceEvent, AttendanceSummary, LeaveRequest
)
from erp_the20.services.attendance_service import (
    build_daily_summary, rebuild_summaries_for_date
)

def aware(dt: datetime) -> datetime:
    tz = timezone.get_current_timezone()
    return timezone.make_aware(dt, tz) if timezone.is_naive(dt) else dt


@override_settings(USE_TZ=True, TIME_ZONE="Asia/Ho_Chi_Minh")
class AttendanceServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.EID = 117
        cls.EID2 = 222
        cls.d = date(2025, 10, 2)

        # Shift templates
        cls.tpl_day = ShiftTemplate.objects.create(
            code="D1", name="Day",
            start_time=time(9, 0), end_time=time(18, 0),
            break_minutes=0, overnight=False
        )
        cls.tpl_am = ShiftTemplate.objects.create(
            code="AM", name="Morning",
            start_time=time(9, 0), end_time=time(13, 0),
            break_minutes=0, overnight=False
        )
        cls.tpl_pm = ShiftTemplate.objects.create(
            code="PM", name="Afternoon",
            start_time=time(14, 0), end_time=time(18, 0),
            break_minutes=0, overnight=False
        )
        cls.tpl_night = ShiftTemplate.objects.create(
            code="N1", name="Night",
            start_time=time(22, 0), end_time=time(6, 0),
            break_minutes=0, overnight=True
        )

    # ---------- helpers ----------
    def _mk_si(self, tpl: ShiftTemplate, d: date) -> ShiftInstance:
        return ShiftInstance.objects.create(template=tpl, date=d, status="planned")

    def _ev(self, eid: int, dt: datetime, typ: str, si: ShiftInstance | None = None):
        return AttendanceEvent.objects.create(
            employee_id=eid, event_type=typ, ts=aware(dt),
            shift_instance=si, is_valid=True, source="web"
        )

    # ---------- tests ----------
    def test_single_shift_present(self):
        si = self._mk_si(self.tpl_day, self.d)
        self._ev(self.EID, datetime.combine(self.d, time(9, 0)), "in", si)
        self._ev(self.EID, datetime.combine(self.d, time(18, 0)), "out", si)

        s = build_daily_summary(self.EID, self.d)
        self.assertEqual(s.planned_minutes, 9*60)
        self.assertEqual(s.worked_minutes, 9*60)
        self.assertEqual(s.late_minutes, 0)
        self.assertEqual(s.early_leave_minutes, 0)
        self.assertEqual(s.overtime_minutes, 0)
        self.assertEqual(s.status, "present")

    def test_single_shift_late_10min(self):
        si = self._mk_si(self.tpl_day, self.d)
        # GRACE = 5' => vào 09:15 -> late = 10'
        self._ev(self.EID, datetime.combine(self.d, time(9, 15)), "in", si)
        self._ev(self.EID, datetime.combine(self.d, time(18, 0)), "out", si)

        s = build_daily_summary(self.EID, self.d)
        self.assertEqual(s.late_minutes, 10)
        self.assertEqual(s.early_leave_minutes, 0)
        # worked = 8h45, planned = 9h -> overtime = 0 (service trừ break=0)
        self.assertEqual(s.worked_minutes, (8*60 + 45))
        self.assertEqual(s.overtime_minutes, 0)
        self.assertEqual(s.status, "late")

    def test_single_shift_early_leave_15min(self):
        si = self._mk_si(self.tpl_day, self.d)
        # OUT 17:40 ; grace_end = 17:55 => early = 15'
        self._ev(self.EID, datetime.combine(self.d, time(9, 0)), "in", si)
        self._ev(self.EID, datetime.combine(self.d, time(17, 40)), "out", si)

        s = build_daily_summary(self.EID, self.d)
        self.assertEqual(s.early_leave_minutes, 15)
        self.assertEqual(s.late_minutes, 0)
        self.assertEqual(s.status, "early_leave")

    def test_overnight_shift_with_carry_in_and_out_after_midnight(self):
        # Ca 22:00 -> 06:00 (overnight) tính cho ngày bắt đầu self.d
        si = self._mk_si(self.tpl_night, self.d)
        # IN trước win_start 10' (21:50) => carry-in; OUT sau win_end 5' (06:05) => coi như làm đủ
        self._ev(self.EID, datetime.combine(self.d, time(21, 50)), "in", si)
        self._ev(self.EID, datetime.combine(self.d + timedelta(days=1), time(6, 5)), "out", si)

        s = build_daily_summary(self.EID, self.d)
        self.assertEqual(s.planned_minutes, 8*60)
        self.assertEqual(s.worked_minutes, 8*60)
        self.assertEqual(s.late_minutes, 0)
        self.assertEqual(s.early_leave_minutes, 0)
        self.assertEqual(s.overtime_minutes, 0)
        self.assertEqual(s.status, "present")

    def test_two_shifts_in_one_day_sum_up(self):
        si1 = self._mk_si(self.tpl_am, self.d)   # 09:00-13:00
        si2 = self._mk_si(self.tpl_pm, self.d)   # 14:00-18:00

        # Ca 1: đủ
        self._ev(self.EID, datetime.combine(self.d, time(9, 0)), "in", si1)
        self._ev(self.EID, datetime.combine(self.d, time(13, 0)), "out", si1)

        # Ca 2: đến 14:07 (> grace 5') => late 2'
        self._ev(self.EID, datetime.combine(self.d, time(14, 7)), "in", si2)
        self._ev(self.EID, datetime.combine(self.d, time(18, 0)), "out", si2)

        s = build_daily_summary(self.EID, self.d)
        self.assertEqual(s.planned_minutes, 8*60)
        # worked = 4h + 3h53 = 7h53 = 473'
        self.assertEqual(s.worked_minutes, 4*60 + 3*60 + 53)
        self.assertEqual(s.late_minutes, 2)          # chỉ ca 2 trễ 2'
        self.assertEqual(s.early_leave_minutes, 0)
        self.assertEqual(s.overtime_minutes, 0)
        self.assertEqual(s.status, "late")

    def test_no_shift_but_has_events_counts_as_overtime(self):
        # Không tạo ShiftInstance
        self._ev(self.EID, datetime.combine(self.d, time(10, 0)), "in", None)
        self._ev(self.EID, datetime.combine(self.d, time(15, 0)), "out", None)

        s = build_daily_summary(self.EID, self.d)
        self.assertEqual(s.planned_minutes, 0)
        self.assertEqual(s.worked_minutes, 5*60)
        self.assertEqual(s.overtime_minutes, 5*60)  # toàn bộ coi như ngoài kế hoạch
        self.assertEqual(s.status, "present")

    def test_approved_leave_no_events(self):
        # Nghỉ phép phủ ngày, không event -> status 'absent' nhưng có on_leave
        LeaveRequest.objects.create(
            employee_id=self.EID, leave_type="annual",
            start_date=self.d, end_date=self.d,
            status="approved"
        )

        s = build_daily_summary(self.EID, self.d)
        self.assertEqual(s.status, "absent")
        self.assertIsNotNone(s.on_leave)

    def test_rebuild_summaries_for_date_auto_picks_employees(self):
        # NV1: có event
        si = self._mk_si(self.tpl_day, self.d)
        self._ev(self.EID, datetime.combine(self.d, time(9, 0)), "in", si)
        self._ev(self.EID, datetime.combine(self.d, time(18, 0)), "out", si)

        # NV2: không event nhưng có leave approved
        LeaveRequest.objects.create(
            employee_id=self.EID2, leave_type="annual",
            start_date=self.d, end_date=self.d,
            status="approved"
        )

        n = rebuild_summaries_for_date(self.d)
        self.assertGreaterEqual(n, 2)

        self.assertTrue(
            AttendanceSummary.objects.filter(employee_id=self.EID, date=self.d).exists()
        )
        self.assertTrue(
            AttendanceSummary.objects.filter(employee_id=self.EID2, date=self.d).exists()
        )
