// repo/shift.repository.js
// ShiftTemplate: base queries, versioned update, soft delete, saveFields

const { Op } = require("sequelize");

const ACTIVE_FIELDS = ["code", "name", "start_time", "end_time", "break_minutes", "overnight", "pay_factor"];

module.exports = function createShiftRepo({ ShiftTemplate, sequelize }) {
  function baseQuery({ include_deleted = false } = {}) {
    const where = {};
    if (!include_deleted) where.deleted_at = null;
    return { where };
  }

  async function getById(pk, { include_deleted = false } = {}) {
    const { where } = baseQuery({ include_deleted });
    where.id = pk;
    return ShiftTemplate.findOne({ where });
  }

  async function getByCode(code, { include_deleted = false } = {}) {
    const { where } = baseQuery({ include_deleted });
    where.code = code;
    return ShiftTemplate.findOne({ where });
  }

  function listShiftTemplates({ q = null, overnight = null, ordering = null, include_deleted = false } = {}) {
    const { where } = baseQuery({ include_deleted });
    if (q) where[Op.or] = [{ name: { [Op.iLike]: `%${q}%` } }, { code: { [Op.iLike]: `%${q}%` } }];
    if (overnight != null) where.overnight = !!overnight;

    const order = ordering ? [[ordering, "ASC"]] : undefined;
    return ShiftTemplate.findAll({ where, order });
  }

  function listAllOrderedByStartTime({ include_deleted = false } = {}) {
    const { where } = baseQuery({ include_deleted });
    return ShiftTemplate.findAll({ where, order: [["start_time", "ASC"]] });
  }

  async function create(data) {
    return ShiftTemplate.create(data);
  }

  async function updateVersioned(instance, data) {
    return sequelize.transaction(async (t) => {
      if (instance.deleted_at == null) {
        instance.deleted_at = new Date();
        await instance.save({ transaction: t, fields: ["deleted_at"] });
      }

      const payload = {};
      for (const f of ACTIVE_FIELDS) payload[f] = instance[f];
      Object.assign(payload, data);

      try {
        return await ShiftTemplate.create(payload, { transaction: t });
      } catch (err) {
        // Unique constraint (e.g., uniq_active_shifttemplate_code)
        err.message = err.message || "Unique constraint error on code";
        throw err;
      }
    });
  }

  async function softDelete(instance) {
    if (instance.deleted_at == null) {
      instance.deleted_at = new Date();
      await instance.save({ fields: ["deleted_at"] });
    }
  }

  async function saveFields(obj, patch, allowed = null) {
    const fields = [];
    for (const [k, v] of Object.entries(patch)) {
      if (!allowed || allowed.has?.(k) || allowed.includes?.(k)) {
        obj[k] = v;
        fields.push(k);
      }
    }
    if (fields.length) {
      fields.push("updated_at");
      await obj.save({ fields });
    }
    return obj;
  }

  return {
    baseQuery,
    getById,
    getByCode,
    listShiftTemplates,
    listAllOrderedByStartTime,
    create,
    updateVersioned,
    softDelete,
    saveFields,
  };
};