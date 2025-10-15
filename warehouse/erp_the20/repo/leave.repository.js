// repo/leave.repository.js
// Supports: base queries, filter, approve/reject/cancel with attendance link/unlink, alias-aware tx

const { Op } = require("sequelize");

module.exports = function createLeaveRepo({ LeaveRequest, Attendance, sequelize }) {
  // ===== Queries =====
  async function getById(id) {
    const obj = await LeaveRequest.findByPk(id);
    if (!obj) throw new Error("LeaveRequest not found");
    return obj;
  }

  async function getOrNone(id) {
    return LeaveRequest.findByPk(id);
  }

  function listMy(employee_id, statuses = null) {
    const where = { employee_id };
    if (Array.isArray(statuses) && statuses.length) where.status = { [Op.in]: statuses };
    return LeaveRequest.findAll({ where, order: [["created_at", "DESC"]] });
  }

  function listPendingForManager(date_from = null, date_to = null) {
    const where = { status: LeaveRequest.Status?.SUBMITTED };
    if (date_from) where.start_date = { ...(where.start_date || {}), [Op.gte]: date_from };
    if (date_to) where.end_date = { ...(where.end_date || {}), [Op.lte]: date_to };
    return LeaveRequest.findAll({ where, order: [["start_date", "ASC"], ["employee_id", "ASC"]] });
  }

  function filterLeaves(filters = {}, order_by = null) {
    const where = {};
    if (filters.employee_id) where.employee_id = { [Op.in]: [].concat(filters.employee_id) };
    if (filters.status) where.status = { [Op.in]: [].concat(filters.status) };
    if (filters.leave_type) where.leave_type = { [Op.in]: [].concat(filters.leave_type) };
    if (filters.handover_to_employee_id) where.handover_to_employee_id = { [Op.in]: [].concat(filters.handover_to_employee_id) };
    if (filters.decided_by) where.decided_by = { [Op.in]: [].concat(filters.decided_by) };
    if (filters.start_from) where.start_date = { ...(where.start_date || {}), [Op.gte]: filters.start_from };
    if (filters.start_to) where.start_date = { ...(where.start_date || {}), [Op.lte]: filters.start_to };
    if (filters.end_from) where.end_date = { ...(where.end_date || {}), [Op.gte]: filters.end_from };
    if (filters.end_to) where.end_date = { ...(where.end_date || {}), [Op.lte]: filters.end_to };
    if ((filters.q || "").trim()) where.reason = { [Op.iLike]: `%${filters.q.trim()}%` };

    const order = order_by?.length ? order_by.map((f) => [f, "ASC"]) : [["created_at", "DESC"]];
    return LeaveRequest.findAll({ where, order });
  }

  // ===== Mutations =====
  async function create(data) {
    return sequelize.transaction(async (t) => LeaveRequest.create(data, { transaction: t }));
  }

  async function saveFields(obj, patch, allowed = null) {
    return sequelize.transaction(async (t) => {
      const fields = [];
      for (const [k, v] of Object.entries(patch)) {
        if (!allowed || allowed.has?.(k) || allowed.includes?.(k)) {
          obj[k] = v;
          fields.push(k);
        }
      }
      if (fields.length) {
        fields.push("updated_at");
        await obj.save({ transaction: t, fields });
      }
      return obj;
    });
  }

  // ===== Attendance linking helpers =====
  async function _unlinkAttendancesForLeave(leave) {
    return sequelize.transaction(async (t) => {
      await Attendance.update(
        { on_leave: null },
        { where: { on_leave: leave.id }, transaction: t }
      );
    });
  }

  async function _linkLeaveToAttendanceOnApprove(leave) {
    return sequelize.transaction(async (t) => {
      await Attendance.update(
        { on_leave: leave.id },
        {
          where: {
            employee_id: leave.employee_id,
            date: { [Op.gte]: leave.start_date, [Op.lte]: leave.end_date },
          },
          transaction: t,
        }
      );

      const rows = await Attendance.findAll({
        where: {
          employee_id: leave.employee_id,
          date: { [Op.gte]: leave.start_date, [Op.lte]: leave.end_date },
          on_leave: leave.id,
        },
        transaction: t,
        lock: t.LOCK.UPDATE,
      });

      for (const att of rows) {
        if (att.status === Attendance.Status?.PENDING || att.status === Attendance.Status?.APPROVED) {
          att.status = Attendance.Status?.CANCELED;
          att.is_valid = false;
          att.approved_by = null;
          att.approved_at = null;
          await att.save({ transaction: t, fields: ["status", "is_valid", "approved_by", "approved_at", "updated_at"] });
        }
      }
    });
  }

  async function approveAndLink(leave_id, manager_id, do_link_attendance) {
    const leave = await sequelize.transaction(async (t) => {
      const obj = await LeaveRequest.findByPk(leave_id, { transaction: t, lock: t.LOCK.UPDATE });
      if (!obj) throw new Error("LeaveRequest not found");
      obj.status = LeaveRequest.Status?.APPROVED;
      obj.decision_ts = new Date();
      obj.decided_by = manager_id;
      await obj.save({ transaction: t, fields: ["status", "decision_ts", "decided_by", "updated_at"] });
      return obj;
    });

    if (do_link_attendance) await _linkLeaveToAttendanceOnApprove(leave);
    return leave;
  }

  async function reject(leave_id, manager_id) {
    return sequelize.transaction(async (t) => {
      const obj = await LeaveRequest.findByPk(leave_id, { transaction: t, lock: t.LOCK.UPDATE });
      if (!obj) throw new Error("LeaveRequest not found");
      obj.status = LeaveRequest.Status?.REJECTED;
      obj.decision_ts = new Date();
      obj.decided_by = manager_id;
      await obj.save({ transaction: t, fields: ["status", "decision_ts", "decided_by", "updated_at"] });
      return obj;
    });
  }

  async function cancel(leave_id, actor_employee_id) {
    const leave = await sequelize.transaction(async (t) => {
      const obj = await LeaveRequest.findByPk(leave_id, { transaction: t, lock: t.LOCK.UPDATE });
      if (!obj) throw new Error("LeaveRequest not found");
      obj.status = LeaveRequest.Status?.CANCELLED;
      obj.decision_ts = new Date();
      obj.decided_by = actor_employee_id;
      await obj.save({ transaction: t, fields: ["status", "decision_ts", "decided_by", "updated_at"] });
      return obj;
    });

    await _unlinkAttendancesForLeave(leave);
    return leave;
  }

  async function deleteLeave(obj) {
    await _unlinkAttendancesForLeave(obj);
    await obj.destroy();
  }

  return {
    getById,
    getOrNone,
    listMy,
    listPendingForManager,
    filterLeaves,
    create,
    saveFields,
    approveAndLink,
    reject,
    cancel,
    deleteLeave,
  };
};