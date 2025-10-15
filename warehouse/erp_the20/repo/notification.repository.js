// repo/notification.repository.js

const { Op } = require("sequelize");

module.exports = function createNotificationRepo({ Notification }) {
  async function createNotification({
    title,
    recipients = null,
    to_user = null,
    payload = null,
    object_type = "",
    object_id = "",
    channel = Notification.Channel?.INAPP ?? 0,
    delivered = true,
  }) {
    const now = new Date();
    return Notification.create({
      title,
      recipients: recipients ? [...recipients] : null,
      to_user,
      payload: payload || {},
      object_type,
      object_id,
      channel,
      delivered,
      delivered_at: delivered ? now : null,
      attempt_count: delivered ? 1 : 0,
    });
  }

  async function listByUser(user_id, limit = 200) {
    return Notification.findAll({
      where: {
        [Op.or]: [
          { to_user: user_id },
          // recipients: ARRAY<Integer> on Postgres
          { recipients: { [Op.contains]: [user_id] } },
        ],
      },
      order: [["created_at", "DESC"]],
      limit,
    });
  }

  return { createNotification, listByUser };
};