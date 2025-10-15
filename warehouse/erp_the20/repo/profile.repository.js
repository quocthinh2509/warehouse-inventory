// repo/profile.repository.js
// EmployeeProfile: get / getOrCreate / save / list with search & pagination

const { Op } = require("sequelize");

module.exports = function createProfileRepo({ EmployeeProfile }) {
  async function get(user_id) {
    return EmployeeProfile.findOne({ where: { user_id } });
  }

  async function getOrCreate(user_id) {
    const [obj] = await EmployeeProfile.findOrCreate({ where: { user_id } });
    return obj;
  }

  async function saveProfile(user_id, fields) {
    const obj = await getOrCreate(user_id);
    Object.assign(obj, fields);
    await obj.save();
    return obj;
  }

  async function listProfiles({ q = null, limit = 50, offset = 0 } = {}) {
    const where = {};
    if (q) {
      const like = { [Op.iLike]: `%${q}%` };
      Object.assign(where, {
        [Op.or]: [
          { full_name: like },
          { email: like },
          { phone: like },
          { cccd: like },
        ],
      });
    }
    const { rows, count } = await EmployeeProfile.findAndCountAll({
      where,
      order: [["updated_at", "DESC"]],
      limit,
      offset,
    });
    return { total: count, items: rows };
  }

  return { get, getOrCreate, saveProfile, listProfiles };
};