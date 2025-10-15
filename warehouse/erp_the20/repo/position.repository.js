// repo/position.repository.js

module.exports = function createPositionRepo({ Position, Department }) {
    async function getById(id) {
      return Position.findByPk(id);
    }
  
    async function getByCode(code) {
      return Position.findOne({ where: { code } });
    }
  
    async function listAll() {
      return Position.findAll({
        include: [{ model: Department, as: "department" }],
        order: [["name", "ASC"]],
      });
    }
  
    async function create(data) {
      return Position.create(data);
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
        if ("updated_at" in Position.rawAttributes) fields.push("updated_at");
        await obj.save({ fields });
      }
      return obj;
    }
  
    async function remove(obj) {
      await obj.destroy();
    }
  
    return { getById, getByCode, listAll, create, saveFields, remove };
  };