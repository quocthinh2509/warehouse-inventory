// repo/handover.repository.js
// list/get/create/update status, add item, set item status with handover status sync

module.exports = function createHandoverRepo({ Handover, HandoverItem, sequelize }) {
    function listHandover(filters = {}) {
      const where = {};
      if (filters.employee_id != null) where.employee_id = filters.employee_id;
      if (filters.manager_id != null) where.manager_id = filters.manager_id;
      if (filters.receiver_employee_id != null) where.receiver_employee_id = filters.receiver_employee_id;
      if (filters.status != null) where.status = filters.status;
  
      return Handover.findAll({
        where,
        order: [["created_at", "DESC"]],
        include: [{ model: HandoverItem, as: "items" }],
      });
    }
  
    async function getHandover(id) {
      const one = await Handover.findByPk(id, { include: [{ model: HandoverItem, as: "items" }] });
      if (!one) throw new Error("Handover not found");
      return one;
    }
  
    async function getItem(itemId) {
      const one = await HandoverItem.findByPk(itemId);
      if (!one) throw new Error("HandoverItem not found");
      return one;
    }
  
    async function createHandover(data) {
      return sequelize.transaction(async (t) => Handover.create(data, { transaction: t }));
    }
  
    async function updateHandoverStatus(handoverId, status) {
      return sequelize.transaction(async (t) => {
        const ho = await Handover.findByPk(handoverId, { transaction: t, lock: t.LOCK.UPDATE });
        if (!ho) throw new Error("Handover not found");
        ho.status = status;
        await ho.save({ transaction: t, fields: ["status", "updated_at"] });
        return ho;
      });
    }
  
    async function addItem(handoverId, { title, detail = "", assignee_id = null }) {
      return sequelize.transaction(async (t) => {
        const item = await HandoverItem.create(
          {
            handover_id: handoverId,
            title,
            detail: detail || "",
            assignee_id,
            status: HandoverItem.ItemStatus?.PENDING ?? 0,
          },
          { transaction: t }
        );
  
        try {
          const ho = await Handover.findByPk(handoverId, { transaction: t, lock: t.LOCK.UPDATE });
          if (ho && ho.status === (Handover.Status?.OPEN ?? 0)) {
            ho.status = Handover.Status?.IN_PROGRESS ?? 1;
            await ho.save({ transaction: t, fields: ["status", "updated_at"] });
          }
        } catch (_) {}
  
        return item;
      });
    }
  
    async function setItemStatus(itemId, status) {
      return sequelize.transaction(async (t) => {
        const item = await HandoverItem.findByPk(itemId, {
          include: [{ model: Handover, as: "handover" }],
          transaction: t,
          lock: t.LOCK.UPDATE,
        });
        if (!item) throw new Error("HandoverItem not found");
  
        item.status = status;
        item.done_at = status === (HandoverItem.ItemStatus?.DONE ?? 1) ? new Date() : null;
        await item.save({ transaction: t, fields: ["status", "done_at", "updated_at"] });
  
        const ho = item.handover;
        const total = await HandoverItem.count({ where: { handover_id: ho.id }, transaction: t });
        const done = await HandoverItem.count({ where: { handover_id: ho.id, status: (HandoverItem.ItemStatus?.DONE ?? 1) }, transaction: t });
  
        if (total && done === total) {
          if (ho.status !== (Handover.Status?.DONE ?? 2)) {
            ho.status = Handover.Status?.DONE ?? 2;
            await ho.save({ transaction: t, fields: ["status", "updated_at"] });
          }
        } else {
          if (ho.status === (Handover.Status?.OPEN ?? 0)) {
            ho.status = Handover.Status?.IN_PROGRESS ?? 1;
            await ho.save({ transaction: t, fields: ["status", "updated_at"] });
          }
        }
  
        return item;
      });
    }
  
    return { listHandover, getHandover, getItem, createHandover, updateHandoverStatus, addItem, setItemStatus };
  };