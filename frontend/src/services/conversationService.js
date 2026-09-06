import api from "./api";

/* =========================
   GET CONVERSATIONS
========================= */

export const getConversations = async () => {
  const response = await api.get(
    "/chats/conversations/"
  );

  return response.data;
};


/* =========================
   SEARCH USERS
========================= */

export const searchUsers = async (query) => {
  const response = await api.get(
    "/accounts/users/search/",
    {
      params: {
        q: query,
      },
    }
  );

  return response.data;
};


/* =========================
   CREATE / GET ONE-TO-ONE
   CONVERSATION
========================= */

export const createOneToOneConversation = async (
  userId
) => {
  const response = await api.post(
    "/chats/conversations/one-to-one/",
    {
      user_id: userId,
    }
  );

  return response.data;
};


/* =========================
   GET MESSAGES
========================= */

export const getMessages = async (
  conversationId,
  cursor = null
) => {
  let url =
    `/chats/conversations/${conversationId}/messages/`;

  if (cursor) {
    try {
      // Supports DRF's complete "next" URL
      const cursorUrl = new URL(cursor);

      const cursorValue =
        cursorUrl.searchParams.get("cursor");

      if (cursorValue) {
        url +=
          `?cursor=${encodeURIComponent(
            cursorValue
          )}`;
      }

    } catch (error) {
      // Supports cursor token directly
      url +=
        `?cursor=${encodeURIComponent(
          cursor
        )}`;
    }
  }

  console.log(
    "Fetching messages:",
    url
  );

  const response =
    await api.get(url);

  return response.data;
};


/* =========================
   SEND MESSAGE
========================= */

export const sendMessage = async (
  conversationId,
  content
) => {
  const response = await api.post(
    "/chats/messages/send/",
    {
      conversation_id:
        conversationId,
      content: content,
    }
  );

  return response.data;
};