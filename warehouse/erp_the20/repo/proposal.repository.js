// repo/proposal.repository.js

const { Op } = require("sequelize");

module.exports = function createProposalRepo({ Proposal, sequelize }) {
  function filterProposals({ employee_id = null, manager_id = null, status = null, type_ = null } = {}) {
    const where = {};
    if (employee_id != null) where.employee_id = employee_id;
    if (manager_id != null) where.manager_id = manager_id;
    if (status != null) where.status = status;
    if (type_ != null) where.type = type_;

    return Proposal.findAll({ where, order: [["created_at", "DESC"]] });
  }

  async function createProposal(fields) {
    return Proposal.create(fields);
  }

  async function getProposal(pk) {
    const obj = await Proposal.findByPk(pk);
    if (!obj) throw new Error("Proposal not found");
    return obj;
  }

  async function setStatus(proposal_id, status, note = "") {
    return sequelize.transaction(async (t) => {
      const obj = await Proposal.findByPk(proposal_id, { transaction: t, lock: t.LOCK.UPDATE });
      if (!obj) throw new Error("Proposal not found");
      obj.status = status;
      obj.decision_note = note || "";
      await obj.save({ transaction: t, fields: ["status", "decision_note", "updated_at"] });
      return obj;
    });
  }

  async function updateDecisionNote(proposal_id, note) {
    return sequelize.transaction(async (t) => {
      const obj = await Proposal.findByPk(proposal_id, { transaction: t, lock: t.LOCK.UPDATE });
      if (!obj) throw new Error("Proposal not found");
      obj.decision_note = note || "";
      await obj.save({ transaction: t, fields: ["decision_note", "updated_at"] });
      return obj;
    });
  }

  return { filterProposals, createProposal, getProposal, setStatus, updateDecisionNote };
};