import api from "./api";

export const getConversations = async () => {
  const response = await api.get("/chats/conversations/");

  return response.data;
};


/* =========================
   GET MESSAGES
========================= */

export const getMessages = async (
  conversationId,
  cursor = null
) => {
  let url = `/chats/conversations/${conversationId}/messages/`;

  /*
   * DRF CursorPagination returns `next` as a complete URL.
   *
   * Example:
   * http://127.0.0.1:8000/api/v1/chats/conversations/ID/messages/?cursor=xxxxx
   *
   * We only need the cursor value.
   */
  if (cursor) {
    try {
      const cursorUrl = new URL(cursor);

      const cursorValue =
        cursorUrl.searchParams.get("cursor");

      if (cursorValue) {
        url += `?cursor=${encodeURIComponent(cursorValue)}`;
      }
    } catch (error) {
      /*
       * If cursor is already just the cursor token,
       * use it directly.
       */
      url += `?cursor=${encodeURIComponent(cursor)}`;
    }
  }

  console.log("Fetching messages:", url);

  const response = await api.get(url);

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