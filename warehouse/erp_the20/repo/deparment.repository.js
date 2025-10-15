// repo/department.repository.js
// Migration of department_repository.py (Django) to Node + Sequelize

module.exports = function createDepartmentRepo({ Department }) {
    async function getById(id) {
      return Department.findByPk(id);
    }
  
    async function getByCode(code) {
      return Department.findOne({ where: { code } });
    }
  
    async function listAll() {
      return Department.findAll({ order: [["name", "ASC"]] });
    }
  
    async function create(data) {
      return Department.create(data);
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
        if ("updated_at" in Department.rawAttributes) fields.push("updated_at");
        await obj.save({ fields });
      }
      return obj;
    }
  
    async function remove(obj) {
      await obj.destroy();
    }
  
    return { getById, getByCode, listAll, create, saveFields, remove };
  };