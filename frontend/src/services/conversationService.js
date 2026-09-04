import api from "./api";

export const getConversations = async () => {
  const response = await api.get(
    "/chats/conversations/"
  );

  return response.data;
};

export const getMessages = async (
  conversationId
) => {
  const response = await api.get(
    `/chats/conversations/${conversationId}/messages/`
  );

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
      conversation_id: conversationId,
      content: content,
    }
  );

  return response.data;
};