/**
 * Screen: chat session list.
 *
 * The seeded conversation gives the list one row with its title, owner, and
 * message count.
 */
export default {
   id: "screen:chat-sessions",
   page: "08-chat-with-an-agent",
   stage: "configured",
   order: 80,
   slot: 1,
   goto: "/project/local/chats",
   steps: [
      {
         id: "chat-sessions",
         caption:
            "**Chats** lists every conversation in the project. Search by name, filter to your own sessions, or open one to continue it."
      }
   ]
};
