// repo/attendance.repository.js
// Attendance repository migrated from Django-style repository.
// Features:
// - get/create/update
// - punch in/out (updates raw_payload.remote_id/pass/note when provided)
// - recompute minutes (work/late/early/overtime) with break + overnight handling
// - simple status helpers (PENDING/APPROVED/CANCELED)
// - safe transactions + row locks (Postgres)

const { Op } = require("sequelize");

// Small time helpers
function toMinutes(ms) { return Math.max(0, Math.round(ms / 60000)); }
function pad(n) { return String(n).padStart(2, "0"); }
function parseHHMM(value) {
  // Accepts "HH:MM" or "HH:MM:SS" or Date
  if (!value) return null;
  if (value instanceof Date) return { h: value.getHours(), m: value.getMinutes() };
  const s = String(value);
  const parts = s.split(":");
  const h = parseInt(parts[0] || 0, 10);
  const m = parseInt(parts[1] || 0, 10);
  return { h, m };
}
function combineDateTime(d, hhmm, addDay = 0) {
  const dt = new Date(d.getFullYear(), d.getMonth(), d.getDate() + addDay, hhmm.h, hhmm.m, 0, 0);
  return dt;
}

/**
 * Compute planned vs actual minutes for one attendance row.
 * Required fields on att:
 *   - date (Date only), ts_in (Date|null), ts_out (Date|null)
 *   - break_minutes (number), plus shift_template fields:
 *       start_time (HH:MM or Date), end_time (HH:MM or Date), overnight (bool)
 * Returns an object with minutes: { work_minutes, late_minutes, early_minutes, overtime_minutes }
 */
function computeMinutes(att, shift) {
  const result = { work_minutes: 0, late_minutes: 0, early_minutes: 0, overtime_minutes: 0 };
  if (!att || !shift) return result;

  const date = att.date instanceof Date ? att.date : new Date(att.date);
  const st = parseHHMM(shift.start_time);
  const et = parseHHMM(shift.end_time);
  if (!st || !et) return result;

  const startPlan = combineDateTime(date, st, 0);
  const endPlan = shift.overnight ? combineDateTime(date, et, 1) : combineDateTime(date, et, 0);

  const tsIn = att.ts_in ? new Date(att.ts_in) : null;
  const tsOut = att.ts_out ? new Date(att.ts_out) : null;

  // Late / Early / Overtime only when we have at least one bound
  if (tsIn) {
    if (tsIn > startPlan) result.late_minutes = toMinutes(tsIn - startPlan);
    else if (tsIn < startPlan) result.overtime_minutes += toMinutes(startPlan - tsIn); // early arrival counts as overtime
  }
  if (tsOut) {
    if (tsOut < endPlan) result.early_minutes = toMinutes(endPlan - tsOut);
    else if (tsOut > endPlan) result.overtime_minutes += toMinutes(tsOut - endPlan);
  }

  // Work minutes only when both in & out
  if (tsIn && tsOut && tsOut > tsIn) {
    let minutes = toMinutes(tsOut - tsIn);
    const breakMin = Number(att.break_minutes || shift.break_minutes || 0);
    if (breakMin > 0 && minutes > breakMin) minutes -= breakMin; // deduct break only if duration exceeds break
    result.work_minutes = Math.max(0, minutes);
  }

  return result;
}

module.exports = function createAttendanceRepo({ Attendance, ShiftTemplate, sequelize }) {
  async function getById(id, { includeShift = true } = {}) {
    const include = includeShift ? [{ model: ShiftTemplate, as: "shift_template" }] : undefined;
    const obj = await Attendance.findByPk(id, { include });
    if (!obj) throw new Error("Attendance not found");
    return obj;
  }

  async function create(data) {
    return sequelize.transaction(async (t) => Attendance.create(data, { transaction: t }));
  }

  async function saveFields(obj, patch, allowed = null) {
    const fields = [];
    for (const [k, v] of Object.entries(patch)) {
      if (!allowed || allowed.has?.(k) || allowed.includes?.(k)) { obj[k] = v; fields.push(k); }
    }
    if (fields.length) { fields.push("updated_at"); await obj.save({ fields }); }
    return obj;
  }

  /**
   * Punch helper
   * direction: "in" | "out"
   * raw_payload: { remote_id?, pass?, note? } will be merged into JSONB raw_payload
   */
  async function punch(attendance_id, { when = new Date(), direction = "in", raw_payload = null, recalc = true }) {
    return sequelize.transaction(async (t) => {
      const att = await Attendance.findByPk(attendance_id, { transaction: t, lock: t.LOCK.UPDATE, include: [{ model: ShiftTemplate, as: "shift_template" }] });
      if (!att) throw new Error("Attendance not found");

      if (direction === "in") att.ts_in = when;
      else if (direction === "out") att.ts_out = when;
      else throw new Error("direction must be 'in' or 'out'");

      if (raw_payload && typeof raw_payload === "object") {
        const current = (att.raw_payload && typeof att.raw_payload === "object") ? att.raw_payload : {};
        att.raw_payload = { ...current, ...raw_payload };
      }

      if (recalc) {
        const m = computeMinutes(att, att.shift_template || {});
        att.work_minutes = m.work_minutes;
        att.late_minutes = m.late_minutes;
        att.early_minutes = m.early_minutes;
        att.overtime_minutes = m.overtime_minutes;
      }

      await att.save({ transaction: t });
      return att;
    });
  }

  /**
   * Recompute stats for a record (e.g., after manual edit)
   */
  async function recompute(attendance_id) {
    return sequelize.transaction(async (t) => {
      const att = await Attendance.findByPk(attendance_id, { transaction: t, lock: t.LOCK.UPDATE, include: [{ model: ShiftTemplate, as: "shift_template" }] });
      if (!att) throw new Error("Attendance not found");
      const m = computeMinutes(att, att.shift_template || {});
      att.work_minutes = m.work_minutes;
      att.late_minutes = m.late_minutes;
      att.early_minutes = m.early_minutes;
      att.overtime_minutes = m.overtime_minutes;
      await att.save({ transaction: t, fields: ["work_minutes", "late_minutes", "early_minutes", "overtime_minutes", "updated_at"] });
      return att;
    });
  }

  // Status helpers (optional, align with your enum mapping)
  async function markApproved(attendance_id, manager_id = null) {
    return sequelize.transaction(async (t) => {
      const att = await Attendance.findByPk(attendance_id, { transaction: t, lock: t.LOCK.UPDATE });
      if (!att) throw new Error("Attendance not found");
      if (Attendance.Status?.APPROVED != null) att.status = Attendance.Status.APPROVED;
      att.is_valid = true;
      att.approved_by = manager_id;
      att.approved_at = new Date();
      await att.save({ transaction: t, fields: ["status", "is_valid", "approved_by", "approved_at", "updated_at"] });
      return att;
    });
  }

  async function markPending(attendance_id) {
    return sequelize.transaction(async (t) => {
      const att = await Attendance.findByPk(attendance_id, { transaction: t, lock: t.LOCK.UPDATE });
      if (!att) throw new Error("Attendance not found");
      if (Attendance.Status?.PENDING != null) att.status = Attendance.Status.PENDING;
      att.is_valid = true;
      att.approved_by = null;
      att.approved_at = null;
      await att.save({ transaction: t, fields: ["status", "is_valid", "approved_by", "approved_at", "updated_at"] });
      return att;
    });
  }

  async function markCanceled(attendance_id) {
    return sequelize.transaction(async (t) => {
      const att = await Attendance.findByPk(attendance_id, { transaction: t, lock: t.LOCK.UPDATE });
      if (!att) throw new Error("Attendance not found");
      if (Attendance.Status?.CANCELED != null) att.status = Attendance.Status.CANCELED;
      att.is_valid = false;
      att.approved_by = null;
      att.approved_at = null;
      await att.save({ transaction: t, fields: ["status", "is_valid", "approved_by", "approved_at", "updated_at"] });
      return att;
    });
  }

  /**
   * Batch create shift registrations (example)
   * items: [{ employee_id, date, shift_template_id, break_minutes? }]
   */
  async function batchRegister(items = []) {
    if (!Array.isArray(items) || !items.length) return [];
    return sequelize.transaction(async (t) => {
      const rows = await Attendance.bulkCreate(items, { transaction: t, returning: true });
      return rows;
    });
  }

  return {
    getById,
    create,
    saveFields,
    punch,
    recompute,
    markApproved,
    markPending,
    markCanceled,
    batchRegister,
    // exposed to allow reuse in services (optional):
    computeMinutes,
  };
};